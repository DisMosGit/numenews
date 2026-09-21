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

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient
from mcp import Client
from mcp.types import CallToolResult, TextContent

from numenews.config import Settings
from numenews.mcp import AppContext, build_server
from numenews.news import NewsAggregator

from ..unit.pipeline_fakes import extract_agent
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
