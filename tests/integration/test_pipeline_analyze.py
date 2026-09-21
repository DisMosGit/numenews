"""The analyze step over the in-memory engine (ROADMAP 5.3).

Roadmap 5.3's acceptance test is stated in the roadmap itself: three news items carrying the number
11 produce a ``resonance``-kind pattern citing all three ids. The pattern agent is a real
``PatternAgent`` over a ``FunctionModel``, so what is asserted here is the step's own contract —
which items it shows the agent, what it saves, and that an unknown id never reaches the model —
rather than the model's taste.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest

from numenews.agents import PatternAgent
from numenews.models import NewsId, NewsItem
from numenews.pipeline import Pipeline, PipelineRetryError
from numenews.vector import (
    PATTERNS_COLLECTION,
    VectorStore,
    upsert_news,
)

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    broken_model,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)

pytestmark = pytest.mark.integration

DAY = date(2026, 9, 21)


def _item(number: int) -> NewsItem:
    """Return a news item whose deterministic id comes from its URL, carrying ``number``."""
    url = f"https://example.com/{number}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=f"Story {number}",
        text=f"Story about the number {number}.",
        source="example.com",
        date=DAY,
        url=url,
        numbers=(number,),
        numerology_value=11,
    )


def _draft(news: list[NewsItem], *, kind: str = "resonance") -> dict[str, object]:
    """Return a scripted ``PatternDraft`` citing every given item."""
    return {
        "type": kind,
        "numbers": [11],
        "news_ids": [str(item.id.root) for item in news],
        "strength": 0.9,
        "interpretation": "Число 11 повторяется во всех новостях дня.",
    }


def _pipeline(
    store: VectorStore,
    patterns: list[dict[str, object]],
    *,
    patterns_agent: PatternAgent | None = None,
) -> tuple[Pipeline, ModelCounter]:
    """Return a pipeline over ``store`` whose pattern agent answers with ``patterns``."""
    extract, _ = extract_agent([])
    agent, counter = pattern_agent(patterns)
    forecaster, _ = forecast_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=patterns_agent if patterns_agent is not None else agent,
        forecast_agent=forecaster,
        summarizer=summarize_agent()[0],
        fetcher=fetcher_returning([]),
        clock=FrozenClock(),
    )
    return pipeline, counter


async def test_three_items_with_eleven_produce_a_resonance_pattern(
    vector_store: VectorStore,
) -> None:
    """ROADMAP 5.3's own acceptance test, with the ids the pipeline actually passes."""
    items = [_item(11), _item(12), _item(13)]
    upsert_news(vector_store, items)
    pipeline, _ = _pipeline(vector_store, [_draft(items)])

    run = await pipeline.analyze(tuple(item.id for item in items))

    assert [pattern.type for pattern in run.patterns] == ["resonance"]
    pattern = run.patterns[0]
    assert pattern.news_ids == tuple(item.id for item in items)
    assert pattern.numbers == (11,)
    assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1


async def test_the_saved_pattern_carries_the_discovery_time(vector_store: VectorStore) -> None:
    """`save_pattern` stamps what the agent could not know; the step reports the stored version."""
    items = [_item(11), _item(12)]
    upsert_news(vector_store, items)
    pipeline, _ = _pipeline(vector_store, [_draft(items)])

    run = await pipeline.analyze(tuple(item.id for item in items))

    assert run.patterns[0].discovered_at is not None


async def test_analyze_hands_the_agent_the_items_the_ids_name(
    vector_store: VectorStore,
) -> None:
    """The step owns the read; the agent only ever sees items that exist."""
    items = [_item(11), _item(12)]
    upsert_news(vector_store, items)
    pipeline, counter = _pipeline(vector_store, [])

    run = await pipeline.analyze(tuple(item.id for item in items))

    assert [item.id for item in run.news] == [item.id for item in items]
    assert counter.calls == 1


async def test_an_unknown_id_is_skipped_and_nothing_is_stored(
    vector_store: VectorStore,
) -> None:
    """An id that names no item is the same as no item at all: no model call, no point."""
    items = [_item(11)]
    upsert_news(vector_store, items)
    pipeline, counter = _pipeline(vector_store, [])

    run = await pipeline.analyze((NewsId(uuid5(NAMESPACE_URL, "https://example.com/missing")),))

    assert run.news == ()
    assert run.patterns == ()
    assert counter.calls == 0
    assert not vector_store.client.collection_exists(PATTERNS_COLLECTION)


async def test_analyze_without_ids_answers_an_empty_run(vector_store: VectorStore) -> None:
    """Roadmap 4.3: nothing to connect is an empty answer, not a model run."""
    upsert_news(vector_store, [_item(11)])
    pipeline, counter = _pipeline(vector_store, [])

    run = await pipeline.analyze(())

    assert run.news == ()
    assert run.patterns == ()
    assert run.activations == 0
    assert [timing.step for timing in run.timings] == ["find", "store"]
    assert counter.calls == 0


async def test_a_failing_pattern_agent_surfaces_after_one_retry(
    vector_store: VectorStore,
) -> None:
    """An empty list must stay distinguishable from "the model never answered" (phase 4.3)."""
    item = _item(11)
    upsert_news(vector_store, [item])
    broken = PatternAgent(broken_model())
    pipeline, _ = _pipeline(vector_store, [], patterns_agent=broken)

    with pytest.raises(PipelineRetryError, match="find_patterns"):
        await pipeline.analyze((item.id,))


async def test_a_pattern_that_cites_no_stored_item_is_not_saved(
    vector_store: VectorStore,
) -> None:
    """The agent drops an unciteable draft (phase 4.3); the step then has nothing to store."""
    items = [_item(11)]
    upsert_news(vector_store, items)
    draft = _draft(items)
    draft["news_ids"] = ["00000000-0000-0000-0000-0000000000ff"]
    pipeline, _ = _pipeline(vector_store, [draft])

    run = await pipeline.analyze(tuple(item.id for item in items))

    assert run.patterns == ()
    assert not vector_store.client.collection_exists(PATTERNS_COLLECTION)
