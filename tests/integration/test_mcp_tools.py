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
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient
from mcp import Client
from mcp.types import CallToolResult, TextContent

from numenews.config import Settings
from numenews.mcp import AppContext, build_server
from numenews.models import NewsId, NewsItem, Pattern, PatternId
from numenews.news import NewsAggregator
from numenews.pipeline import Pipeline
from numenews.vector import (
    PATTERNS_COLLECTION,
    VectorStore,
    save_pattern,
    upsert_news,
)
from numenews.vector.payloads import news_embedding_text, pattern_embedding_text

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
from .fakes import FakeEmbedder

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
) -> tuple[Pipeline, ModelCounter, ModelCounter]:
    """Return a pipeline over ``store`` and the counters of its pattern and forecast agents."""
    extract, _ = extract_agent([11])
    pattern_reader, pattern_counter = pattern_agent(patterns or [])
    forecaster, forecast_counter = forecast_agent()
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
    return pipeline, pattern_counter, forecast_counter


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
    pipeline, counter, _ = _pipeline(vector_store, patterns=[_pattern_draft(items)])
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
    pipeline, counter, _ = _pipeline(vector_store)
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


async def test_check_master_numbers_needs_no_service(settings: Settings) -> None:
    """ROADMAP 6.6: the second pure tool answers on a server with no configuration."""
    async with Client(build_server(context=AppContext(settings)), raise_exceptions=True) as client:
        result = await client.call_tool("check_master_numbers", {"numbers": [11, 11, 7]})

    assert result.is_error is False
    assert result.structured_content == {
        "has_master": True,
        "master_numbers": [11],
        "count": 2,
    }


async def test_build_forecast_reads_the_day_and_caches_it(
    settings: Settings, vector_store: VectorStore
) -> None:
    """ROADMAP 6.7: the reading comes from ``Pipeline.forecast``, and a second call is free."""
    stored = _item("11th hour deal").model_copy(update={"numbers": (11,), "numerology_value": 11})
    upsert_news(vector_store, [stored])
    pipeline, _, forecast_counter = _pipeline(vector_store)
    context = AppContext(settings, pipeline=pipeline)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        first = await client.call_tool("build_forecast", {"day": "2026-09-21"})
        second = await client.call_tool("build_forecast", {"day": "2026-09-21"})

    assert first.is_error is False
    assert first.structured_content is not None
    reading = first.structured_content
    assert reading["date"] == "2026-09-21"
    assert reading["dominant_number"] == 11
    assert reading["master_active"] is True
    assert reading["forecast"] == "День под знаком одиннадцати."
    assert reading["advice"] == "Слушайте интуицию."
    assert forecast_counter.calls == 1
    assert second.structured_content == reading


async def test_query_qdrant_ranks_the_stored_news(
    settings: Settings, vector_store: VectorStore, fake_base_embedder: FakeEmbedder
) -> None:
    """ROADMAP 6.8: the tool searches the news collection and returns typed entities."""
    near = _item("budget deal signed")
    far = _item("weather report published")
    fake_base_embedder.register_axis(news_embedding_text(near), 0)
    fake_base_embedder.register_axis(news_embedding_text(far), 1)
    fake_base_embedder.register_axis("budget", 0)
    upsert_news(vector_store, [near, far])
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool("query_qdrant", {"collection": "news", "query": "budget"})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["collection"] == "news"
    assert result.structured_content["query"] == "budget"
    items = result.structured_content["items"]
    assert [item["title"] for item in items] == ["budget deal signed", "weather report published"]


async def test_query_qdrant_honours_the_news_filter(
    settings: Settings, vector_store: VectorStore, fake_base_embedder: FakeEmbedder
) -> None:
    """The payload filter narrows the candidate set before the ranking, as phase 3.8 requires."""
    seven = _item("seven seats lost").model_copy(update={"numerology_value": 7})
    eleven = _item("eleven seats lost").model_copy(update={"numerology_value": 11})
    fake_base_embedder.register_axis(news_embedding_text(seven), 0)
    fake_base_embedder.register_axis(news_embedding_text(eleven), 1)
    fake_base_embedder.register_axis("seats", 0)
    upsert_news(vector_store, [seven, eleven])
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "query_qdrant",
            {"collection": "news", "query": "seats", "filters": {"numerology_value": 11}},
        )

    assert result.is_error is False
    assert result.structured_content is not None
    assert [item["title"] for item in result.structured_content["items"]] == ["eleven seats lost"]


async def test_query_qdrant_searches_the_patterns_collection(
    settings: Settings, vector_store: VectorStore, fake_base_embedder: FakeEmbedder
) -> None:
    """The second searchable collection answers with ``Pattern`` entities."""
    pattern = Pattern(
        id=PatternId(uuid4()),
        type="resonance",
        numbers=(11, 22),
        news_ids=(NewsId(uuid4()),),
        strength=0.8,
        interpretation="Числа 11 и 22 резонируют.",
    )
    fake_base_embedder.register_axis(pattern_embedding_text(pattern), 0)
    fake_base_embedder.register_axis("резонанс", 0)
    save_pattern(vector_store, pattern)
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "query_qdrant", {"collection": "patterns", "query": "резонанс"}
        )

    assert result.is_error is False
    assert result.structured_content is not None
    items = result.structured_content["items"]
    assert [item["id"] for item in items] == [str(pattern.id.root)]
    assert items[0]["numbers"] == [11, 22]


async def test_query_qdrant_refuses_filters_on_patterns(
    settings: Settings, vector_store: VectorStore
) -> None:
    """Ignoring a filter silently would promise a narrowing the call did not do."""
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "query_qdrant",
            {"collection": "patterns", "query": "резонанс", "filters": {"source": "example.com"}},
        )

    assert result.is_error is True
    assert "filters apply to the news collection only" in text_of(result)


async def test_query_qdrant_refuses_an_unknown_collection(settings: Settings) -> None:
    """The Literal is the contract: a collection without a read path is not a valid argument."""
    async with Client(build_server(context=AppContext(settings)), raise_exceptions=True) as client:
        result = await client.call_tool("query_qdrant", {"collection": "numbers", "query": "x"})

    assert result.is_error is True
    assert "news" in text_of(result)


async def test_query_qdrant_reports_a_missing_collection(
    settings: Settings, vector_store: VectorStore
) -> None:
    """A store without the news collection is a setup problem the model can be told about."""
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool("query_qdrant", {"collection": "news", "query": "budget"})

    assert result.is_error is True
    assert "does not exist" in text_of(result)


def _pattern_payload(
    *, pattern_id: UUID | None = None, discovered_at: str | None = None
) -> dict[str, object]:
    """Return a save_pattern argument as a client would send it."""
    payload: dict[str, object] = {
        "id": str(pattern_id or uuid4()),
        "type": "resonance",
        "numbers": [11, 22],
        "news_ids": [str(uuid4())],
        "strength": 0.8,
        "interpretation": "Числа 11 и 22 резонируют.",
    }
    if discovered_at is not None:
        payload["discovered_at"] = discovered_at
    return payload


async def test_save_pattern_stores_it_and_stamps_the_time(
    settings: Settings, vector_store: VectorStore
) -> None:
    """ROADMAP 6.9: the pattern is written to the collection and comes back stamped."""
    pattern_id = uuid4()
    context = AppContext(settings, store=vector_store)

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        result = await client.call_tool(
            "save_pattern", {"pattern": _pattern_payload(pattern_id=pattern_id)}
        )

        assert result.is_error is False
        assert result.structured_content is not None
        saved = result.structured_content
        assert saved["id"] == str(pattern_id)
        assert saved["numbers"] == [11, 22]
        assert saved["discovered_at"] is not None
        assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1


async def test_save_pattern_keeps_an_existing_timestamp_and_replaces_the_point(
    settings: Settings, vector_store: VectorStore
) -> None:
    """A found-at time is history, and the same id is an overwrite rather than a duplicate."""
    pattern_id = uuid4()
    context = AppContext(settings, store=vector_store)
    payload = _pattern_payload(pattern_id=pattern_id, discovered_at="2026-09-01T10:00:00Z")

    async with Client(build_server(context=context), raise_exceptions=True) as client:
        first = await client.call_tool("save_pattern", {"pattern": payload})
        second = await client.call_tool("save_pattern", {"pattern": payload})

        assert first.structured_content is not None
        assert second.structured_content is not None
        assert str(first.structured_content["discovered_at"]).startswith("2026-09-01T10:00:00")
        assert second.structured_content == first.structured_content
        assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1
