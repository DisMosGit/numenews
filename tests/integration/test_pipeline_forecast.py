"""The forecast step over the in-memory engine (ROADMAP 5.4).

Two of the roadmap's criteria are asserted here: the reading is saved, and a second call returns it
from storage instead of re-running the agent. Everything else is the step's own contract — the day's
number comes from ``numerology`` rather than from the model, a day without news still gets a number
from its date, the memory shown to the model is about this day's numbers, and a failing agent
surfaces after one retry instead of storing a fabricated reading.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from numenews.agents import ForecastAgent
from numenews.agents.prompts import format_history
from numenews.models import NewsId, NewsItem, NumberActivation
from numenews.numerology import reduce_date
from numenews.pipeline import Pipeline, PipelineRetryError
from numenews.vector import (
    FORECASTS_COLLECTION,
    NUMBER_HISTORY_COLLECTION,
    PATTERNS_COLLECTION,
    VectorStore,
    get_forecast,
    record_activation,
    upsert_news,
)
from numenews.vector.payloads import forecast_point_id

from ..unit.agent_fakes import recording, user_text
from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    broken_model,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
)

pytestmark = pytest.mark.integration

#: The day being read, and the instant the frozen clock reports (UTC noon of it).
DAY = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _item(number: int, *, day: date = DAY, text: str | None = None) -> NewsItem:
    """Return a news item whose text states ``number``, so the regex pass finds it."""
    url = f"https://example.com/{number}-{day.isoformat()}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=f"The {number}th story",
        text=f"The {number}th story happened on {day.isoformat()}." if text is None else text,
        source="example.com",
        date=day,
        url=url,
        numbers=(number,),
        numerology_value=number,
    )


def _draft(news: list[NewsItem]) -> dict[str, object]:
    """Return a scripted ``PatternDraft`` citing every given item."""
    return {
        "type": "master",
        "numbers": [11],
        "news_ids": [str(item.id.root) for item in news],
        "strength": 0.9,
        "interpretation": "Число 11 повторяется в новостях дня.",
    }


def _pipeline(
    store: VectorStore,
    *,
    patterns: list[dict[str, object]] | None = None,
    forecaster: ForecastAgent | None = None,
) -> tuple[Pipeline, ModelCounter, ModelCounter]:
    """Return a pipeline over ``store`` with counting pattern and forecast agents."""
    extract, _ = extract_agent([])
    pattern_agent_instance, pattern_counter = pattern_agent(patterns or [])
    forecast_agent_instance, forecast_counter = forecast_agent()
    return (
        Pipeline(
            store=store,
            extract=extract,
            patterns=pattern_agent_instance,
            forecast_agent=forecast_agent_instance if forecaster is None else forecaster,
            fetcher=fetcher_returning([]),
            clock=FrozenClock(now=NOW),
        ),
        pattern_counter,
        forecast_counter,
    )


async def test_forecast_saves_the_day_and_returns_it(vector_store: VectorStore) -> None:
    """ROADMAP 5.4's Definition of Done: the reading is stored under the day's point id."""
    items = [_item(11), _item(11)]
    upsert_news(vector_store, items)
    pipeline, _, _ = _pipeline(vector_store, patterns=[_draft(items)])

    reading = await pipeline.forecast(DAY)

    assert reading.date == DAY
    assert reading.dominant_number == 11
    assert reading.master_active is True
    assert reading.patterns != ()
    assert vector_store.client.count(FORECASTS_COLLECTION, exact=True).count == 1
    records = vector_store.client.retrieve(
        FORECASTS_COLLECTION, [forecast_point_id(DAY)], with_payload=True
    )
    payload = records[0].payload or {}
    assert payload["date"] == "2026-09-21T00:00:00Z"
    assert payload["dominant_number"] == 11


async def test_a_second_call_answers_from_storage_without_a_model_run(
    vector_store: VectorStore,
) -> None:
    """ROADMAP 5.4: the cached day must not cost another agent run."""
    items = [_item(11), _item(11)]
    upsert_news(vector_store, items)
    pipeline, pattern_counter, forecast_counter = _pipeline(vector_store, patterns=[_draft(items)])

    first = await pipeline.forecast(DAY)
    calls_after_first = forecast_counter.calls
    patterns_after_first = pattern_counter.calls
    second = await pipeline.forecast(DAY)

    assert second == first
    assert forecast_counter.calls == calls_after_first
    assert pattern_counter.calls == patterns_after_first


async def test_a_day_without_news_falls_back_to_the_number_of_its_date(
    vector_store: VectorStore,
) -> None:
    """A reading always has a number to rest on, even on a quiet day."""
    pipeline, pattern_counter, forecast_counter = _pipeline(vector_store)

    reading = await pipeline.forecast(DAY)

    assert reading.dominant_number == reduce_date(DAY)
    assert vector_store.client.count(FORECASTS_COLLECTION, exact=True).count == 1
    assert pattern_counter.calls == 0  # nothing to connect
    assert forecast_counter.calls == 1


async def test_the_window_keeps_the_reading_to_the_recent_days(vector_store: VectorStore) -> None:
    """Roadmap 5.5's sliding window: a day outside it does not vote."""
    recent = _item(11)
    old = _item(3, day=date(2026, 9, 1))
    upsert_news(vector_store, [recent, old])
    pipeline, _, _ = _pipeline(vector_store, patterns=[_draft([recent])])

    reading = await pipeline.forecast(DAY)

    assert reading.dominant_number == 11
    assert [pattern.news_ids for pattern in reading.patterns] == [(recent.id,)]


async def test_rerun_analysis_can_be_skipped(vector_store: VectorStore) -> None:
    """A caller that just ran `analyze` does not pay for the pattern agent twice."""
    items = [_item(11), _item(11)]
    upsert_news(vector_store, items)
    pipeline, pattern_counter, _ = _pipeline(vector_store, patterns=[_draft(items)])

    reading = await pipeline.forecast(DAY, rerun_analysis=False)

    assert pattern_counter.calls == 0
    assert reading.patterns == ()
    assert reading.dominant_number == 11


async def test_the_history_shown_to_the_model_is_the_day_s_numbers(
    vector_store: VectorStore,
) -> None:
    """The memory in the prompt is evidence for this reading, not an unrelated activation."""
    item = _item(11)
    upsert_news(vector_store, [item])
    mine = NumberActivation(
        number=11,
        date=DAY,
        news_id=item.id,
        context="Eleven ministers resigned.",
    )
    unrelated = NumberActivation(
        number=7,
        date=DAY,
        news_id=NewsId(uuid4()),
        context="Seven ships left the port.",
    )
    await asyncio.to_thread(record_activation, vector_store, mine)
    await asyncio.to_thread(record_activation, vector_store, unrelated)
    model, recorder = recording(
        forecast="День под знаком одиннадцати.",
        advice="Слушайте интуицию.",
        warnings=[],
    )
    pipeline, _, _ = _pipeline(vector_store, patterns=[_draft([item])])
    pipeline = Pipeline(
        store=vector_store,
        extract=pipeline.extract,
        patterns=pipeline.patterns,
        forecast_agent=ForecastAgent(model),
        fetcher=fetcher_returning([]),
        clock=FrozenClock(now=NOW),
    )

    await pipeline.forecast(DAY)

    prompt = user_text(recorder.calls[0])
    assert "Eleven ministers resigned." in prompt
    assert "Seven ships left the port." not in prompt
    assert vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count == 2


async def test_a_failing_forecast_agent_stores_nothing_and_surfaces(
    vector_store: VectorStore,
) -> None:
    """A broken endpoint must not leave a fabricated reading behind."""
    items = [_item(11)]
    upsert_news(vector_store, items)
    pipeline, _, _ = _pipeline(
        vector_store, patterns=[_draft(items)], forecaster=ForecastAgent(broken_model())
    )

    with pytest.raises(PipelineRetryError, match="build_forecast"):
        await pipeline.forecast(DAY)

    # Storage holds readings, not attempts: the failed run wrote no point.
    assert not vector_store.client.collection_exists(FORECASTS_COLLECTION)


async def test_a_replayed_day_reads_its_own_window(vector_store: VectorStore) -> None:
    """`today` is injectable, so an old batch reads its own days instead of the wall clock."""
    old_item = _item(7, day=date(2026, 9, 10))
    upsert_news(vector_store, [old_item])
    pipeline, _, _ = _pipeline(vector_store, patterns=[_draft([old_item])])

    reading = await pipeline.forecast(date(2026, 9, 10), today=date(2026, 9, 10))

    assert reading.dominant_number == 7
    assert [pattern.news_ids for pattern in reading.patterns] == [(old_item.id,)]
    assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1
    stored = await pipeline.run_blocking(lambda: get_forecast(vector_store, date(2026, 9, 10)))
    assert stored == reading


def test_the_history_block_of_the_prompt_is_the_agents_own_format() -> None:
    """The step hands over activations; the agent's formatter is what renders them."""
    activation = NumberActivation(
        number=11,
        date=DAY,
        news_id=NewsId(uuid5(NAMESPACE_URL, "https://example.com/11")),
        context="Eleven ministers resigned.",
    )

    assert format_history([activation]).startswith("- 2026-09-21 · 11 · Eleven ministers")
