"""The context step over the in-memory engine (docs/RAG_PIPELINE.md).

`Pipeline.summarize` is the public entry of the task: ingest a range, keep the sliding window raw,
and compress everything before it into one stored digest. The interesting cases are the boundaries —
what counts as "old", what happens when nothing is old, and what a second run does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid5

import pytest

from numenews.agents import SummarizeAgent
from numenews.models import DateRange, NewsId, NewsItem, Topic
from numenews.pipeline import Pipeline, PipelineRetryError
from numenews.vector import DIGESTS_COLLECTION, VectorStore, get_activations, get_digest

from ..unit.agent_fakes import recording, user_text
from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    ScriptedExtract,
    broken_model,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)
from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration

TOPIC = Topic(query="politics")
TODAY = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _item(day: date, *, text: str | None = None) -> NewsItem:
    """Return a news item published on ``day``, whose text states a number the regex can find."""
    number = day.day
    url = f"https://example.com/{day.isoformat()}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=f"The {number}th report",
        text=f"The {number}th report was published on {day.isoformat()}." if text is None else text,
        source="example.com",
        date=day,
        url=url,
    )


def _pipeline(
    store: VectorStore,
    items: list[NewsItem],
    *,
    summarizer: SummarizeAgent | None = None,
) -> tuple[Pipeline, ModelCounter]:
    """Return a pipeline over ``store`` fetching ``items``, plus the summarizer's call count."""
    extract, _ = extract_agent([])
    patterns, _ = pattern_agent([])
    forecaster, _ = forecast_agent()
    summary_agent_instance, counter = summarize_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=patterns,
        forecast_agent=forecaster,
        summarizer=summary_agent_instance if summarizer is None else summarizer,
        fetcher=fetcher_returning(items),
        clock=FrozenClock(now=NOW),
    )
    return pipeline, counter


async def test_the_older_items_become_one_digest_and_the_window_stays_raw(
    vector_store: VectorStore,
) -> None:
    """docs/RAG_PIPELINE.md: the sliding window is kept, the stretch before it is compressed."""
    items = [_item(date(2026, 9, 2)), _item(date(2026, 9, 3)), _item(date(2026, 9, 20))]
    pipeline, counter = _pipeline(vector_store, items)

    digest = await pipeline.summarize(
        TOPIC, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21))
    )

    assert digest is not None
    assert digest.period_start == date(2026, 9, 2)
    assert digest.period_end == date(2026, 9, 3)
    assert digest.summary
    assert counter.calls == 1
    assert get_digest(vector_store, date(2026, 9, 2), date(2026, 9, 3)) == digest
    assert vector_store.client.count(DIGESTS_COLLECTION, exact=True).count == 1


async def test_a_range_inside_the_window_produces_no_digest(vector_store: VectorStore) -> None:
    """A daily run has nothing old to compress: `None`, no model call, no point."""
    items = [_item(date(2026, 9, 18)), _item(date(2026, 9, 20))]
    pipeline, counter = _pipeline(vector_store, items)

    digest = await pipeline.summarize(
        TOPIC, DateRange(start=date(2026, 9, 18), end=date(2026, 9, 21))
    )

    assert digest is None
    assert counter.calls == 0
    assert not vector_store.client.collection_exists(DIGESTS_COLLECTION)


async def test_one_old_item_is_not_a_digest(vector_store: VectorStore) -> None:
    """Summarising a single article would only restate it; two items are the minimum."""
    items = [_item(date(2026, 9, 2)), _item(date(2026, 9, 20))]
    pipeline, counter = _pipeline(vector_store, items)

    digest = await pipeline.summarize(
        TOPIC, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21))
    )

    assert digest is None
    assert counter.calls == 0
    assert not vector_store.client.collection_exists(DIGESTS_COLLECTION)


async def test_summarising_twice_replaces_the_period(vector_store: VectorStore) -> None:
    """A period has one digest, so a second run of the same range does not pile memories up."""
    items = [_item(date(2026, 9, 2)), _item(date(2026, 9, 3))]
    pipeline, _ = _pipeline(vector_store, items)
    date_range = DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21))

    first = await pipeline.summarize(TOPIC, date_range)
    second = await pipeline.summarize(TOPIC, date_range)

    assert first == second
    assert vector_store.client.count(DIGESTS_COLLECTION, exact=True).count == 1


async def test_the_summarizer_limit_bounds_the_prompt_not_the_period(
    vector_store: VectorStore,
) -> None:
    """The digest still covers the whole older stretch; only the model's view of it is capped."""
    # The newest ten days carry text the first five do not, so the test can tell which of them
    # reached the model and which only reached the stored period.
    recent_text = "Eleven ministers resigned today over the budget."
    items = [
        _item(date(2026, 9, day), text=recent_text if day > 5 else None) for day in range(1, 15)
    ]
    model, recorder = recording(summary="Период прошёл под числом 11.")
    pipeline, _ = _pipeline(vector_store, items, summarizer=SummarizeAgent(model))
    pipeline = Pipeline(
        store=vector_store,
        extract=pipeline.extract,
        patterns=pipeline.patterns,
        forecast_agent=pipeline.forecast_agent,
        summarizer=pipeline.summarizer,
        fetcher=fetcher_returning(items),
        clock=FrozenClock(now=NOW),
        summary_limit=5,
    )

    digest = await pipeline.summarize(
        TOPIC, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21))
    )

    assert pipeline.summary_limit == 5
    assert len(recorder.calls) == 1
    assert digest is not None
    # The stored period and numbers describe the whole older range, not the five items shown.
    assert digest.period_start == date(2026, 9, 1)
    assert digest.period_end == date(2026, 9, 14)
    assert digest.numbers == (6, 1)
    assert get_digest(vector_store, date(2026, 9, 1), date(2026, 9, 14)) == digest
    assert vector_store.client.count(DIGESTS_COLLECTION, exact=True).count == 1
    # The prompt really was bounded: the model read the five oldest days and no later one, while
    # the stored numbers come from a range it never saw in full.
    prompt = user_text(recorder.calls[0])
    assert "2026-09-01" in prompt
    assert "2026-09-05" in prompt
    assert recent_text not in prompt


async def test_a_period_that_was_never_summarised_answers_nothing(
    vector_store: VectorStore,
) -> None:
    """A digest is found by its own two days, so a sub-period does not answer with a wider one."""
    items = [_item(date(2026, 9, day)) for day in range(1, 15)]
    pipeline, _ = _pipeline(vector_store, items)
    pipeline = Pipeline(
        store=vector_store,
        extract=pipeline.extract,
        patterns=pipeline.patterns,
        forecast_agent=pipeline.forecast_agent,
        summarizer=pipeline.summarizer,
        fetcher=fetcher_returning(items),
        clock=FrozenClock(now=NOW),
        summary_limit=5,
    )

    digest = await pipeline.summarize(
        TOPIC, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21))
    )

    assert digest is not None
    # The sub-period the model actually read is not a digest anyone stored.
    assert get_digest(vector_store, date(2026, 9, 1), date(2026, 9, 5)) is None
    assert get_digest(vector_store, date(2026, 9, 3), date(2026, 9, 4)) is None
    assert vector_store.client.count(DIGESTS_COLLECTION, exact=True).count == 1


async def test_the_stored_snippet_is_the_text_the_numbers_index_embeds(
    vector_store: VectorStore,
    fake_small_embedder: FakeEmbedder,
) -> None:
    """The evidence behind an activation is one snippet, not two: what `numbers` embeds is stored.

    An activation for `3` in a text that also says `30` is anchored at the standalone mention, so
    the payload a semantic search finds and the vector it was ranked by describe the same sentence.
    """
    text = "The 30 delegates met. A 3 hour debate followed."
    item = _item(date(2026, 9, 20), text=text)
    pipeline, _ = _pipeline(vector_store, [item])
    pipeline = Pipeline(
        store=vector_store,
        # `ScriptedExtract` is a subclass, so it stands in wherever the real class is expected; the
        # ignore is for the annotation, which mypy cannot narrow to the subclass at this call site.
        extract=ScriptedExtract({f"{item.title}\n\n{item.text}": (3, 30)}),  # type: ignore[arg-type]
        patterns=pipeline.patterns,
        forecast_agent=pipeline.forecast_agent,
        summarizer=pipeline.summarizer,
        fetcher=fetcher_returning([item]),
        clock=FrozenClock(now=NOW),
    )

    await pipeline.ingest(TOPIC, DateRange(start=date(2026, 9, 20), end=date(2026, 9, 20)))

    # `today` is passed so the read window depends on the fixture's day, not on the wall clock.
    activations = await pipeline.run_blocking(
        lambda: get_activations(vector_store, 1, today=date(2026, 9, 20))
    )
    by_number = {activation.number: activation for activation in activations}
    assert by_number[3].context == "A 3 hour debate followed."
    assert by_number[30].context == "The 30 delegates met. A 3 hour debate followed."
    # The `numbers` batch embeds exactly the stored contexts, in the order the activations were
    # built. `upsert_number_patterns` embeds `activation.context` directly, so an equality here is
    # the whole claim: the index and the payload cannot disagree about the evidence.
    assert fake_small_embedder.calls == [
        [by_number[3].context, by_number[30].context],
    ]


async def test_a_failing_summarizer_surfaces_and_stores_nothing(vector_store: VectorStore) -> None:
    """A broken endpoint must not leave a fabricated memory behind."""
    items = [_item(date(2026, 9, 2)), _item(date(2026, 9, 3))]
    pipeline, _ = _pipeline(vector_store, items, summarizer=SummarizeAgent(broken_model()))

    with pytest.raises(PipelineRetryError, match="summarize_news"):
        await pipeline.summarize(TOPIC, DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21)))

    assert not vector_store.client.collection_exists(DIGESTS_COLLECTION)


async def test_the_window_of_the_summary_follows_the_injected_day(
    vector_store: VectorStore,
) -> None:
    """`today` moves the window, so a replayed run compresses the same stretch it always did."""
    items = [_item(date(2026, 9, 2)), _item(date(2026, 9, 3)), _item(date(2026, 9, 20))]
    pipeline, _ = _pipeline(vector_store, items)

    digest = await pipeline.summarize(
        TOPIC,
        DateRange(start=date(2026, 9, 1), end=date(2026, 9, 21)),
        today=date(2026, 9, 15),
    )

    assert digest is not None
    # From the 15th the window reaches back to the 9th, so the 20th is a *future* day for this
    # replay and only the two early-September items are old news.
    assert digest.period_start == date(2026, 9, 2)
    assert digest.period_end == date(2026, 9, 3)
