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

from collections.abc import Callable

from mcp.server.mcpserver import Context

from numenews.mcp.context import AppContext
from numenews.mcp.errors import tool_errors
from numenews.mcp.schemas import DateRangeInput
from numenews.models import ExtractedNumbers, NewsItem, NumerologyResult, Topic
from numenews.numerology import compute_numerology as read_numerology


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


#: Every tool the server registers, in roadmap order.
TOOLS: tuple[Callable[..., object], ...] = (fetch_news, extract_numbers, compute_numerology)


__all__ = ["TOOLS", "compute_numerology", "context_of", "extract_numbers", "fetch_news"]
