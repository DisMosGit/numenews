"""The nine MCP tools, called through an in-memory client (ROADMAP 6.2-6.10).

Each test builds the real server and connects the SDK's own ``Client`` to it in memory — no
subprocess, no port, no JSON on a wire — and injects an :class:`~numenews.mcp.context.AppContext`
whose collaborators are the test's doubles: an in-memory Qdrant with fake embedders, scripted
``FunctionModel`` agents and ``respx`` for HTTP. The tool functions, the argument validation, the
structured output and the error translation are therefore all exercised for real, while no service
and no model is reached.

The subprocess/stdio form of the same server is checked separately in ``test_mcp_stdio.py``.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient
from mcp import Client
from mcp.types import CallToolResult, TextContent

from numenews.config import Settings
from numenews.mcp import AppContext, build_server
from numenews.models import NewsId, NewsItem
from numenews.news import NewsAggregator
from numenews.pipeline import Pipeline
from numenews.vector import VectorStore, upsert_news

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)
from .conftest import news_fixture

pytestmark = pytest.mark.integration

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TITLES = [
    "11th hour deal reached on the budget",
    "Summit ends without an agreement",
]
RANGE = {"start": "2026-09-15", "end": "2026-09-21"}


def _gdelt_router(router: respx.MockRouter) -> None:
    """Answer the GDELT endpoint with its recorded fixture."""
    router.get(GDELT).mock(
        return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
    )


def text_of(result: CallToolResult) -> str:
    """Return the text the model would read from a tool result, refusing anything else."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


def _item(title: str, *, published: date = date(2026, 9, 21)) -> NewsItem:
    """Return a stored-able news item with a deterministic id and just enough variety."""
    return NewsItem(
        id=NewsId(uuid4()),
        title=title,
        text=f"{title} body",
        source="example.com",
        date=published,
        url=f"https://example.test/{title.replace(' ', '-').lower()}",
    )


def _pattern_draft(items: list[NewsItem]) -> dict[str, object]:
    """Return a scripted ``PatternDraft`` connecting ``items`` over the number 11."""
    return {
        "type": "repetition",
        "numbers": [11],
        "news_ids": [str(item.id.root) for item in items],
        "strength": 0.9,
        "interpretation": "Число 11 повторяется в новостях.",
    }


def _pipeline(
    store: VectorStore,
    *,
    patterns: list[dict[str, object]] | None = None,
) -> tuple[Pipeline, ModelCounter]:
    """Return a pipeline over ``store`` whose every collaborator is a scripted double."""
    extract, _ = extract_agent([11])
    pattern_reader, pattern_counter = pattern_agent(patterns or [])
    forecaster, _ = forecast_agent()
    summarizer, _ = summarize_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=pattern_reader,
        forecast_agent=forecaster,
        summarizer=summarizer,
        fetcher=fetcher_returning([]),
        clock=FrozenClock(),
    )
    return pipeline, pattern_counter


async def test_fetch_news_returns_the_aggregated_items(
    settings: Settings, news_client: AsyncCacheClient
) -> None:
    """ROADMAP 6.2: the tool reaches ``NewsAggregator`` and returns ``list[NewsItem]``."""
    context = AppContext(settings, aggregator=NewsAggregator.from_settings(settings, news_client))

    with respx.mock(assert_all_called=False) as router:
        _gdelt_router(router)
        async with Client(build_server(context=context), raise_exceptions=True) as client:
            result = await client.call_tool(
                "fetch_news", {"topic": "politics", "date_range": RANGE}
            )

    assert result.is_error is False
    assert result.structured_content is not None
    items = result.structured_content["result"]
    assert [item["title"] for item in items] == GDELT_TITLES
    assert items[0]["date"] == date(2026, 9, 21).isoformat()
    assert items[0]["source"] == "example.com"


async def test_fetch_news_reports_an_unconfigured_feed_as_a_tool_error(
    settings: Settings,
) -> None:
    """No source at all is the one fetch failure worth surfacing: the model can act on it."""
    context = AppContext(settings, aggregator=NewsAggregator([]))

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool("fetch_news", {"topic": "politics", "date_range": RANGE})

    assert result.is_error is True
    assert result.structured_content is None
    assert "no news sources are configured" in text_of(result)


async def test_extract_numbers_returns_the_agents_reading(settings: Settings) -> None:
    """ROADMAP 6.3: the tool reaches ``ExtractNumbersAgent`` and returns its structured reading."""
    extract, counter = extract_agent([11], symbols=["☀"])
    context = AppContext(settings, extract=extract)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "extract_numbers", {"text": "The 11th hour deal was signed at 7"}
        )

    assert result.is_error is False
    assert counter.calls == 1
    assert result.structured_content is not None
    assert sorted(result.structured_content["numbers"]) == [7, 11]
    assert result.structured_content["symbols"] == ["☀"]
    assert "llm" in result.structured_content["sources"]


async def test_extract_numbers_reports_a_missing_llm_endpoint(settings: Settings) -> None:
    """An unconfigured LLM is an expected failure, and the message says what to set."""
    async with Client(build_server(context=AppContext(settings)), raise_exceptions=True) as client:
        result = await client.call_tool("extract_numbers", {"text": "eleven ministers resigned"})

    assert result.is_error is True
    assert "No LLM endpoint configured" in text_of(result)


async def test_compute_numerology_needs_no_service(settings: Settings) -> None:
    """ROADMAP 6.4: a pure tool answers on a server that has nothing configured at all."""
    async with Client(build_server(context=AppContext(settings)), raise_exceptions=True) as client:
        result = await client.call_tool("compute_numerology", {"text": "sun"})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["value"] == 9
    assert result.structured_content["gematria"] == 54
    assert result.structured_content["is_master"] is False


async def test_find_patterns_connects_the_stored_items(
    settings: Settings, vector_store: VectorStore
) -> None:
    """ROADMAP 6.5: the tool runs ``Pipeline.analyze`` and returns the saved patterns."""
    items = [_item(f"story {number}") for number in range(3)]
    upsert_news(vector_store, items)
    pipeline, counter = _pipeline(vector_store, patterns=[_pattern_draft(items)])
    context = AppContext(settings, pipeline=pipeline)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "find_patterns", {"news_ids": [str(item.id.root) for item in items]}
        )

    assert result.is_error is False
    assert counter.calls == 1
    assert result.structured_content is not None
    patterns = result.structured_content["result"]
    assert len(patterns) == 1
    assert patterns[0]["type"] == "repetition"
    assert patterns[0]["numbers"] == [11]
    assert patterns[0]["news_ids"] == [str(item.id.root) for item in items]
    assert patterns[0]["discovered_at"] is not None


async def test_find_patterns_without_ids_answers_empty(
    settings: Settings, vector_store: VectorStore
) -> None:
    """An empty list never reaches the model: "nothing to look at" is not "nothing connects"."""
    pipeline, counter = _pipeline(vector_store)
    context = AppContext(settings, pipeline=pipeline)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool("find_patterns", {"news_ids": []})

    assert result.is_error is False
    assert result.structured_content == {"result": []}
    assert counter.calls == 0


async def test_find_patterns_refuses_a_malformed_id_before_running(settings: Settings) -> None:
    """Argument validation is the SDK's job, and its message names the offending field."""
    async with Client(build_server(context=AppContext(settings)), raise_exceptions=True) as client:
        result = await client.call_tool("find_patterns", {"news_ids": ["not-a-uuid"]})

    assert result.is_error is True
    assert "valid UUID" in text_of(result)
