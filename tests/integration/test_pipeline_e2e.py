"""The whole pipeline, end to end (ROADMAP 5.6).

The dependencies of one real run are all present but none of them is real: ``respx`` answers the
GDELT endpoint through the cached ``httpx`` client of phase 2, a ``FunctionModel`` stands in for the
language model, and Qdrant runs in memory. So the test drives the actual chain — fetch → extract →
compute → embed/upsert → analyze → forecast → save — and nothing is stubbed at the seam where the
bug would hide.

The GDELT fixture is the recorded answer in ``tests/fixtures/news/gdelt_artlist.json``. For the
2026-09-15..21 range it yields two usable articles, dated 2026-09-20 and 2026-09-21; the other
entries have no URL or an unparsable timestamp and are dropped by the adapter.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient

from numenews.config import Settings
from numenews.models import DateRange, Forecast, NewsItem, Topic
from numenews.numerology import dominant_number
from numenews.pipeline import DEFAULT_WINDOW_DAYS, Pipeline
from numenews.vector import (
    DIGESTS_COLLECTION,
    FORECASTS_COLLECTION,
    NEWS_COLLECTION,
    NUMBER_HISTORY_COLLECTION,
    NUMBERS_COLLECTION,
    PATTERNS_COLLECTION,
    VectorStore,
    get_forecast,
    get_history,
)

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    extract_agent,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)
from .conftest import news_fixture

pytestmark = pytest.mark.integration

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
DAY = date(2026, 9, 21)
FIXTURE_TITLES = [
    "11th hour deal reached on the budget",
    "Summit ends without an agreement",
]


def _pipeline(
    store: VectorStore,
    *,
    patterns: list[dict[str, object]] | None = None,
) -> tuple[Pipeline, ModelCounter, ModelCounter, ModelCounter]:
    """Return a pipeline over ``store`` with counting agents and an in-memory store."""
    extract, extract_counter = extract_agent([11])
    patterns_agent, pattern_counter = pattern_agent(patterns or [])
    forecaster, forecast_counter = forecast_agent()
    summarizer, _ = summarize_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=patterns_agent,
        forecast_agent=forecaster,
        summarizer=summarizer,
        clock=FrozenClock(now=datetime(2026, 9, 21, 12, 0, tzinfo=UTC)),
    )
    return pipeline, extract_counter, pattern_counter, forecast_counter


def _with_pattern_agent(pipeline: Pipeline, draft: dict[str, object]) -> Pipeline:
    """Return ``pipeline`` with a pattern agent that answers ``draft``.

    The draft cites the ingested items, whose ids only exist after the fetch, so the agent cannot be
    built before the ingest has run.
    """
    return Pipeline(
        store=pipeline.store,
        extract=pipeline.extract,
        patterns=pattern_agent([draft])[0],
        forecast_agent=pipeline.forecast_agent,
        summarizer=pipeline.summarizer,
        fetcher=pipeline.fetcher,
        clock=pipeline.clock,
    )


def _draft(news: list[NewsItem]) -> dict[str, object]:
    """Return a scripted ``PatternDraft`` connecting the given items over the number 11."""
    return {
        "type": "repetition",
        "numbers": [11],
        "news_ids": [str(item.id.root) for item in news],
        "strength": 0.9,
        "interpretation": "Число 11 повторяется в новостях недели.",
    }


def _gdelt_router(router: respx.MockRouter) -> None:
    """Answer the GDELT endpoint with its recorded fixture."""
    router.get(GDELT).mock(
        return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
    )


@pytest.fixture(autouse=True)
def _fix_gdelt_url() -> None:
    """Keep the endpoint constant honest: the adapter must be asking the URL ``respx`` answers.

    One real unmocked request would reach the network, and the module-level guard of phase 4
    (``ALLOW_MODEL_REQUESTS``) exists for the same reason on the model side.
    """
    from numenews.news import gdelt

    assert gdelt._ENDPOINT == GDELT  # the point is to check the private constant


async def test_ingest_analyze_forecast_over_the_whole_layer(
    vector_store: VectorStore,
    news_client: AsyncCacheClient,
    settings: Settings,
    instant_retries: None,
) -> None:
    """ROADMAP 5.6: the recorded GDELT answer becomes a stored forecast, through every layer."""
    pipeline, extract_counter, _placeholder_counter, forecast_counter = _pipeline(vector_store)

    with respx.mock(assert_all_called=False) as router:
        _gdelt_router(router)
        ingestion = await pipeline.ingest(TOPIC, RANGE)

    assert [item.title for item in ingestion.news] == FIXTURE_TITLES
    assert extract_counter.calls == 2
    # One activation per (item, number): both articles state one number.
    assert ingestion.activations == 2
    assert vector_store.client.count(NEWS_COLLECTION, exact=True).count == 2
    assert [timing.step for timing in ingestion.timings] == ["news", "extract", "compute", "embed"]

    # The day's forecast derives the window's patterns through `analyze` and writes the reading.
    window = ingestion.news
    pipeline = _with_pattern_agent(pipeline, _draft(list(window)))
    expected = dominant_number(
        [item.numerology_value for item in window if item.numerology_value is not None]
    )

    reading = await pipeline.forecast(DAY)

    assert reading.dominant_number == expected.dominant_number
    assert reading.master_active == expected.is_master
    assert [pattern.type for pattern in reading.patterns] == ["repetition"]
    assert reading.patterns[0].news_ids == tuple(item.id for item in window)
    assert reading.patterns[0].discovered_at is not None
    assert isinstance(reading, Forecast)
    assert forecast_counter.calls == 1
    assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1
    assert await pipeline.run_blocking(lambda: get_forecast(vector_store, DAY)) == reading

    # A second call answers from storage, with no further agent run and no second pattern.
    assert await pipeline.forecast(DAY) == reading
    assert forecast_counter.calls == 1
    assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1


async def test_the_second_run_is_idempotent_and_costs_no_model_calls(
    vector_store: VectorStore,
    news_client: AsyncCacheClient,
    settings: Settings,
    instant_retries: None,
) -> None:
    """A repeated one-shot run stores nothing new: the articles are known and the day is read."""
    pipeline, extract_counter, pattern_counter, forecast_counter = _pipeline(vector_store)

    with respx.mock(assert_all_called=False) as router:
        _gdelt_router(router)
        first = await pipeline.ingest(TOPIC, RANGE)
        extracted_once = (extract_counter.calls, pattern_counter.calls, forecast_counter.calls)
        again_ingested = await pipeline.ingest(TOPIC, RANGE)
        after_repeat = (extract_counter.calls, pattern_counter.calls, forecast_counter.calls)
        reading = await pipeline.forecast(DAY)
        after_day = (pattern_counter.calls, forecast_counter.calls)
        second_reading = await pipeline.forecast(DAY)

    assert first.news != ()
    assert again_ingested.news == ()
    assert again_ingested.activations == 0
    # The repeated ingest added no article, so no extraction ran and no agent was asked anything.
    assert extracted_once == (2, 0, 0)
    assert after_repeat == extracted_once
    assert after_day == (1, 1)  # the day's forecast ran both agents exactly once
    assert second_reading == reading
    assert await pipeline.run_blocking(lambda: get_forecast(vector_store, DAY)) == reading


async def test_the_activation_history_holds_the_ingested_numbers(
    vector_store: VectorStore,
    news_client: AsyncCacheClient,
    settings: Settings,
    instant_retries: None,
) -> None:
    """Roadmap 8's memory starts in phase 5: ingest records the activations of what it read."""
    pipeline, _, _, _ = _pipeline(vector_store)

    with respx.mock(assert_all_called=False) as router:
        _gdelt_router(router)
        await pipeline.ingest(TOPIC, RANGE)

    history = await pipeline.run_blocking(lambda: get_history(vector_store, 11, 7, today=DAY))

    assert [activation.number for activation in history] == [11, 11]
    assert {activation.date for activation in history} == {
        date(2026, 9, 20),
        date(2026, 9, 21),
    }
    assert all(activation.context for activation in history)
    assert vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count == 2
    assert vector_store.client.count(NUMBERS_COLLECTION, exact=True).count == 2


async def test_the_chain_provisions_every_collection_it_writes(
    vector_store: VectorStore,
    news_client: AsyncCacheClient,
    settings: Settings,
    instant_retries: None,
) -> None:
    """Each write path creates its schema first; the digest waits for old news (roadmap 5.5)."""
    pipeline, _, _, _ = _pipeline(vector_store)

    with respx.mock(assert_all_called=False) as router:
        _gdelt_router(router)
        ingestion = await pipeline.ingest(TOPIC, RANGE)
        # The draft cites the ingested items, whose ids only exist after the fetch.
        pipeline = _with_pattern_agent(pipeline, _draft(list(ingestion.news)))
        await pipeline.analyze(tuple(item.id for item in ingestion.news))
        await pipeline.forecast(DAY)

    assert DEFAULT_WINDOW_DAYS == 7
    for collection in (
        NEWS_COLLECTION,
        NUMBERS_COLLECTION,
        PATTERNS_COLLECTION,
        FORECASTS_COLLECTION,
        NUMBER_HISTORY_COLLECTION,
    ):
        assert vector_store.client.collection_exists(collection), collection
    assert not vector_store.client.collection_exists(DIGESTS_COLLECTION)
    assert DEFAULT_WINDOW_DAYS == 7
