"""The ingest step over the in-memory engine (ROADMAP 5.2).

The acceptance test of this task is idempotency by ``news_id``: a second ingest of the same page
must add no points, make no model call and embed nothing. The rest of the file states what one run
writes — the news item, the semantic activation and the exact history row — and that the profile of
roadmap 5.1 covers the four steps of the chain.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest
from qdrant_client.models import VectorParams

from numenews.models import DateRange, NewsId, NewsItem, NumberActivation, Topic
from numenews.news import NewsSourceError
from numenews.numerology import compute_numerology
from numenews.pipeline import Pipeline, PipelineRun
from numenews.vector import (
    NEWS_COLLECTION,
    NUMBER_HISTORY_COLLECTION,
    NUMBERS_COLLECTION,
    VectorStore,
    get_activations,
    get_news_items,
)
from numenews.vector.payloads import activation_point_id, news_point_id

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    ScriptedExtract,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)

pytestmark = pytest.mark.integration

TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))

#: The text of both test articles is written so the regex pass finds exactly one number, so the
#: expected payloads below can be written out literally.
FIRST_TITLE = "The 11th hour deal"
FIRST_TEXT = "The 11th hour deal was reached on Tuesday."
SECOND_TITLE = "Seven nations sign"
SECOND_TEXT = "Seven nations signed the accord."


def _item(number: int, *, title: str, text: str, day: date = date(2026, 9, 21)) -> NewsItem:
    """Return a news item whose deterministic id comes from its URL, as the adapters build them."""
    url = f"https://example.com/{number}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=title,
        text=text,
        source="example.com",
        date=day,
        url=url,
    )


def _pipeline(
    store: VectorStore,
    items: list[NewsItem],
    numbers: list[int],
    *,
    fetcher: object = None,
) -> tuple[Pipeline, ModelCounter]:
    """Return a pipeline over ``store``, fetching ``items`` through the injectable fetcher."""
    extract, counter = extract_agent(numbers)
    patterns, _ = pattern_agent([])
    forecaster, _ = forecast_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=patterns,
        forecast_agent=forecaster,
        summarizer=summarize_agent()[0],
        fetcher=fetcher_returning(items) if fetcher is None else fetcher,  # type: ignore[arg-type]
        clock=FrozenClock(),
    )
    return pipeline, counter


async def test_ingest_writes_the_news_the_activation_and_the_history(
    vector_store: VectorStore,
) -> None:
    """One run of the chain fills all three collections of roadmap 5.2."""
    first = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    second = _item(7, title=SECOND_TITLE, text=SECOND_TEXT)
    pipeline, _ = _pipeline(vector_store, [first, second], [11, 7])

    run = await pipeline.ingest(TOPIC, RANGE)

    assert isinstance(run, PipelineRun)
    assert [item.numbers for item in run.news] == [(11, 7), (11, 7)]
    assert [item.numerology_value for item in run.news] == [
        compute_numerology(f"{FIRST_TITLE}\n\n{FIRST_TEXT}").value,
        compute_numerology(f"{SECOND_TITLE}\n\n{SECOND_TEXT}").value,
    ]
    assert run.activations == 4
    assert vector_store.client.count(NEWS_COLLECTION, exact=True).count == 2
    assert vector_store.client.count(NUMBERS_COLLECTION, exact=True).count == 4
    assert vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count == 4

    stored = vector_store.client.retrieve(
        NEWS_COLLECTION, [news_point_id(first)], with_payload=True
    )
    payload = stored[0].payload or {}
    assert payload["numbers"] == [11, 7]
    assert payload["numerology_value"] == run.news[0].numerology_value
    assert payload["date"] == "2026-09-21T00:00:00Z"


async def test_the_history_row_carries_the_snippet_around_the_number(
    vector_store: VectorStore,
) -> None:
    """The exact log keeps the number, the day, the item and the phrase it was read in."""
    item = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    pipeline, _ = _pipeline(vector_store, [item], [11])

    await pipeline.ingest(TOPIC, RANGE)

    stored_items = await pipeline.run_blocking(lambda: get_news_items(vector_store, [item.id]))
    assert [stored.numbers for stored in stored_items] == [(11,)]
    assert stored_items[0].numerology_value is not None
    activation = NumberActivation(
        number=11,
        date=item.date,
        news_id=item.id,
        context="The 11th hour deal was reached on Tuesday.",
    )
    records = vector_store.client.retrieve(
        NUMBER_HISTORY_COLLECTION, [activation_point_id(activation)], with_payload=True
    )
    payload = records[0].payload or {}
    assert payload["number"] == 11
    assert payload["date"] == "2026-09-21T00:00:00Z"
    assert payload["news_id"] == str(item.id.root)
    assert "11th hour" in str(payload["context"])
    # The row carries the item's own reduced value, so the memory is readable on its own (8.1).
    assert payload["numerology_value"] == stored_items[0].numerology_value


async def test_a_second_batch_grows_the_history(vector_store: VectorStore) -> None:
    """Phase 8's DoD: the memory accumulates across runs instead of restarting each time."""
    first_day = date(2026, 9, 20)
    next_day = date(2026, 9, 21)
    first = _item(11, title=FIRST_TITLE, text=FIRST_TEXT, day=first_day)
    second = _item(7, title=SECOND_TITLE, text=SECOND_TEXT, day=next_day)
    morning, _ = _pipeline(vector_store, [first], [11])
    evening, _ = _pipeline(vector_store, [second], [7])

    first_run = await morning.ingest(TOPIC, RANGE)
    after_first = vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count
    second_run = await evening.ingest(TOPIC, RANGE)
    after_second = vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count

    history = await evening.run_blocking(lambda: get_activations(vector_store, 30, today=next_day))

    assert first_run.activations == 1
    assert second_run.activations == 1
    assert (after_first, after_second) == (1, 2)
    assert {activation.date for activation in history} == {first_day, next_day}


async def test_a_repeated_ingest_adds_nothing_and_calls_no_model(
    vector_store: VectorStore,
) -> None:
    """ROADMAP 5.2's Definition of Done: the second run is a no-op."""
    item = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    pipeline, counter = _pipeline(vector_store, [item], [11])

    first = await pipeline.ingest(TOPIC, RANGE)
    second = await pipeline.ingest(TOPIC, RANGE)

    assert first.news != ()
    assert second.news == ()
    assert second.activations == 0
    assert counter.calls == 1
    assert vector_store.client.count(NEWS_COLLECTION, exact=True).count == 1
    assert vector_store.client.count(NUMBERS_COLLECTION, exact=True).count == 1
    assert vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count == 1


async def test_a_partly_known_page_still_adds_the_new_articles(
    vector_store: VectorStore,
) -> None:
    """The skip is per item, so yesterday's cache does not hide today's article."""
    known = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    pipeline, _ = _pipeline(vector_store, [known], [11])
    await pipeline.ingest(TOPIC, RANGE)

    fresh = _item(7, title=SECOND_TITLE, text=SECOND_TEXT)
    refreshing, _ = _pipeline(vector_store, [known, fresh], [11])
    run = await refreshing.ingest(TOPIC, RANGE)

    assert [item.title for item in run.news] == [SECOND_TITLE]
    assert vector_store.client.count(NEWS_COLLECTION, exact=True).count == 2


async def test_the_engine_embeds_into_the_collections_they_were_built_for(
    vector_store: VectorStore,
) -> None:
    """A run cannot hang a 768d vector in a 384d collection: the store pins pair and width."""
    item = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    pipeline, _ = _pipeline(vector_store, [item], [11])

    await pipeline.ingest(TOPIC, RANGE)

    news_vectors = vector_store.client.get_collection(NEWS_COLLECTION).config.params.vectors
    assert isinstance(news_vectors, VectorParams)
    assert news_vectors.size == 768
    numbers_vectors = vector_store.client.get_collection(NUMBERS_COLLECTION).config.params.vectors
    assert isinstance(numbers_vectors, VectorParams)
    assert numbers_vectors.size == 384


async def test_the_extraction_reads_the_headline_and_the_body(vector_store: VectorStore) -> None:
    """A number written only in the body is still read: the extractor gets both, one blank apart."""
    item = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    extract = ScriptedExtract({f"{FIRST_TITLE}\n\n{FIRST_TEXT}": (11,)})
    pipeline = Pipeline(
        store=vector_store,
        extract=extract,  # type: ignore[arg-type]
        patterns=pattern_agent([])[0],
        forecast_agent=forecast_agent()[0],
        summarizer=summarize_agent()[0],
        fetcher=fetcher_returning([item]),
        clock=FrozenClock(),
    )

    run = await pipeline.ingest(TOPIC, RANGE)

    assert extract.texts == [f"{FIRST_TITLE}\n\n{FIRST_TEXT}"]
    assert [stored.numbers for stored in run.news] == [(11,)]


async def test_the_run_reports_one_timing_per_step(vector_store: VectorStore) -> None:
    """ROADMAP 5.1: every step of the chain leaves a timing for the profile."""
    item = _item(11, title=FIRST_TITLE, text=FIRST_TEXT)
    pipeline, _ = _pipeline(vector_store, [item], [11])

    run = await pipeline.ingest(TOPIC, RANGE)

    assert [timing.step for timing in run.timings] == ["news", "extract", "compute", "embed"]
    assert all(timing.duration_seconds >= 0 for timing in run.timings)


async def test_ingest_with_no_news_writes_nothing(vector_store: VectorStore) -> None:
    """An empty page is a result, not an error: no store write, no model call, a report of zero."""
    pipeline, counter = _pipeline(vector_store, [], [])

    run = await pipeline.ingest(TOPIC, RANGE)

    assert run.news == ()
    assert run.activations == 0
    assert counter.calls == 0
    # Not even the collection is created: the run touched the store not at all.
    assert vector_store.client.collection_exists(NEWS_COLLECTION) is False


async def test_ingest_surfaces_a_source_failure(vector_store: VectorStore) -> None:
    """A configuration with no feeds is a real error; the pipeline does not hide it."""

    async def broken(topic: Topic, date_range: DateRange) -> list[NewsItem]:
        raise NewsSourceError("no news sources are configured")

    pipeline, _ = _pipeline(vector_store, [], [], fetcher=broken)

    with pytest.raises(NewsSourceError, match="no news sources"):
        await pipeline.ingest(TOPIC, RANGE)
