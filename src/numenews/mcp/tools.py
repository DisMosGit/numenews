"""The nine MCP tools, one plain function each.

A tool is an ordinary function: its name is the tool name, its docstring the description the model
reads, its type hints the input schema, and its return annotation the output schema (``MCPServer``
derives all four). The body is a thin wrapper — the work belongs to the layers below, and the only
things that happen here are the conversions of :mod:`numenews.mcp.schemas`, the
:func:`~numenews.mcp.context.AppContext` lookup that supplies the collaborators, and the
:func:`~numenews.mcp.errors.tool_errors` translation that turns an expected failure into a message
the model can act on.

The functions take a ``ctx: Context[AppContext]`` parameter, which the SDK injects and hides
from the schema; the lifespan object it carries is read with :func:`context_of`. They stay plain
callables —
:func:`numenews.mcp.server.build_server` registers them with ``MCPServer.add_tool`` — so a unit test
can import and call the ones that need no context directly.

``TOOLS`` is the registry the server iterates; it grows with roadmap 6.2-6.10, one tool per task.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import date
from typing import Annotated
from uuid import UUID

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from numenews.mcp.context import AppContext
from numenews.mcp.errors import tool_errors
from numenews.mcp.schemas import (
    CollectionName,
    CollectionQueryResult,
    DateRangeInput,
    NewsFilterInput,
    PatternInput,
)
from numenews.models import (
    ExtractedNumbers,
    Forecast,
    MasterCheckResult,
    NewsId,
    NewsItem,
    NumberActivation,
    NumerologyResult,
    Pattern,
    Topic,
)
from numenews.numerology import check_master_numbers as master_check
from numenews.numerology import compute_numerology as read_numerology
from numenews.vector import find_similar_patterns, hybrid_search_news
from numenews.vector import get_history as history_in_store
from numenews.vector import save_pattern as store_pattern


def context_of(ctx: Context[AppContext]) -> AppContext:
    """Return the lifespan object the server handed this request.

    ``Context`` is the SDK's per-request object; the collaborators built once at startup live on the
    lifespan result it exposes. Every tool that needs one starts here, so the indirection is written
    down in one place.
    """
    return ctx.request_context.lifespan_context


async def fetch_news(
    topic: str,
    date_range: DateRangeInput,
    ctx: Context[AppContext],
) -> list[NewsItem]:
    """Fetch the news of a topic in an inclusive date range from every configured source.

    The five feeds run in parallel and the result is merged, de-duplicated and filtered to the
    range. A source that fails is skipped with a warning, so a broken feed thins the result instead
    of failing the call; if no source is configured at all (no GDELT, which needs no key) the call
    is a tool error.
    """
    with tool_errors():
        aggregator = await context_of(ctx).news()
        return await aggregator.fetch_all(Topic(query=topic), date_range.to_domain())


async def extract_numbers(text: str, ctx: Context[AppContext]) -> ExtractedNumbers:
    """Read the numbers, dates and symbols out of a text with the extraction agent.

    The model's reading is combined with the deterministic regex pass, so a mention the model
    formats differently ("eleven" beside "11") is still found, and a model that cannot answer at all
    degrades to the regex reading instead of failing. ``sources`` says which strategies contributed.
    Needs an LLM endpoint (``OPENAI_API_KEY`` or ``OPENAI_BASE_URL``).
    """
    with tool_errors():
        reader = await context_of(ctx).extract()
        return await reader.extract(text)


def compute_numerology(text: str) -> NumerologyResult:
    """Reduce a text to its numerological value.

    Returns the raw gematria sum, the digit-reduced value (``11``, ``22`` and ``33`` are master
    numbers and are not reduced further), whether the value is master, and the rendered calculation
    steps. Pure logic: no Qdrant, no model, no configuration.
    """
    return read_numerology(text)


async def find_patterns(news_ids: list[UUID], ctx: Context[AppContext]) -> list[Pattern]:
    """Find the connections among the stored news items with these ids, save them and return them.

    The ids come from an earlier ``fetch_news``/ingest run or from ``query_qdrant``. An id that is
    not in the store is skipped rather than refused, and an empty list answers ``[]`` without asking
    the model — "nothing connects" and "nothing to look at" stay tellable apart. Each returned
    pattern carries the ``discovered_at`` timestamp ``save_pattern`` stamped. Needs Qdrant and an
    LLM endpoint.
    """
    with tool_errors():
        pipeline = await context_of(ctx).pipeline()
        run = await pipeline.analyze(tuple(NewsId(value) for value in news_ids))
        return list(run.patterns)


def check_master_numbers(numbers: list[int]) -> MasterCheckResult:
    """Report the master numbers (11, 22, 33) among a list of numbers.

    ``master_numbers`` lists the distinct master numbers found, ascending, and ``count`` how many
    occurrences there were: ``[11, 11]`` gives ``has_master=True``, ``master_numbers=(11,)`` and
    ``count=2``. An empty list is a valid input and reports no master number. Pure logic: no
    configuration, no service.
    """
    return master_check(numbers)


async def build_forecast(day: date, ctx: Context[AppContext]) -> Forecast:
    """Return the numerological reading for a calendar day, saving it for later calls.

    A day that was already read answers from Qdrant without running a model. Otherwise the reading
    is assembled from the last seven days of stored news (their dominant number, whether a master
    number is active, and the patterns among them) plus the activations of exactly those numbers
    over the pipeline's thirty-day memory window, and then written back. Needs Qdrant and an LLM
    endpoint.
    """
    with tool_errors():
        pipeline = await context_of(ctx).pipeline()
        return await pipeline.forecast(day)


async def query_qdrant(
    collection: CollectionName,
    query: Annotated[
        str, Field(min_length=1, description="What to look for, in natural language.")
    ],
    ctx: Context[AppContext],
    filters: NewsFilterInput | None = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum results.")] = 10,
) -> CollectionQueryResult:
    """Search the stored news or patterns by meaning and return the matching entities.

    ``collection="news"`` runs the hybrid (multi-stage) search over stored articles and honours the
    optional payload ``filters`` — publication window, source, reduced value or master number.
    ``collection="patterns"`` finds saved pattern interpretations and takes no filters: passing any
    is an error rather than a silently ignored argument. Needs Qdrant only; nothing is embedded
    remotely and no model is called.

    The returned ``items`` are the typed entities themselves (``NewsItem`` or ``Pattern``), best
    match first; the scores stay in Qdrant because the callers work with the entities.
    """
    with tool_errors():
        store = await context_of(ctx).store()
        items: Sequence[NewsItem | Pattern]
        if collection == "patterns":
            if filters is not None:
                raise ToolError("filters apply to the news collection only")
            items = await asyncio.to_thread(find_similar_patterns, store, query, limit)
        else:
            news_filter = filters.to_domain() if filters is not None else None
            items = await asyncio.to_thread(hybrid_search_news, store, query, news_filter, limit)
        return CollectionQueryResult(collection=collection, query=query, items=tuple(items))


async def save_pattern(pattern: PatternInput, ctx: Context[AppContext]) -> Pattern:
    """Store one pattern and return it as written, with ``discovered_at`` filled in.

    The roadmap called the return type ``SavedPattern``; the saved model *is* a ``Pattern`` (the one
    ``numenews.vector.save_pattern`` returns), so the tool returns that rather than a second type
    saying the same thing. Re-saving the same pattern id overwrites the point instead of adding a
    copy, and a timestamp already present is never rewritten. Needs Qdrant only.
    """
    with tool_errors():
        store = await context_of(ctx).store()
        return await asyncio.to_thread(store_pattern, store, pattern.to_domain())


async def get_history(
    number: int,
    ctx: Context[AppContext],
    days: Annotated[
        int, Field(ge=1, le=365, description="Length of the window in days, ending today.")
    ] = 30,
) -> list[NumberActivation]:
    """Return when a number was activated in the news, newest first, inside the last ``days`` days.

    One entry per ``(news item, number)`` pair the ingest stored: the day the article was published,
    the item's id and the snippet the number was read in. The window ends today and includes it
    (``days=1`` is today). Roadmap 6.10 wrote the signature as ``get_history(number)``; the read is
    a window, so ``days`` is a parameter whose default of 30 matches the memory window of phase 8.
    Needs Qdrant only.
    """
    with tool_errors():
        store = await context_of(ctx).store()
        return await asyncio.to_thread(history_in_store, store, number, days)


#: Every tool the server registers, in roadmap order.
TOOLS: tuple[Callable[..., object], ...] = (
    fetch_news,
    extract_numbers,
    compute_numerology,
    find_patterns,
    check_master_numbers,
    build_forecast,
    query_qdrant,
    save_pattern,
    get_history,
)


__all__ = [
    "TOOLS",
    "build_forecast",
    "check_master_numbers",
    "compute_numerology",
    "context_of",
    "extract_numbers",
    "fetch_news",
    "find_patterns",
    "get_history",
    "query_qdrant",
    "save_pattern",
]
