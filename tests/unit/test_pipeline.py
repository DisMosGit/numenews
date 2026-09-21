"""Tests for the pipeline orchestrator (ROADMAP 5.1).

Three things are asserted here: the constructor wires every collaborator and refuses a window that
cannot work, the step timer measures with the injected clock and survives a failing block, and the
blocking bridge really moves work off the event loop. None of them needs Qdrant, a model or a key.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from numenews.agents import AgentExecutionError
from numenews.pipeline import (
    DEFAULT_HISTORY_DAYS,
    DEFAULT_WINDOW_DAYS,
    Pipeline,
    PipelineError,
    PipelineRetryError,
    PipelineRun,
    StepTimer,
    SystemClock,
    Timing,
)
from numenews.pipeline.steps import ATTEMPTS, retrying

from .pipeline_fakes import (
    NOW,
    FakeStore,
    FrozenClock,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    orchestration_pipeline,
    pattern_agent,
    summarize_agent,
)


def _pipeline() -> Pipeline:
    """Return a pipeline over a marker store, with every collaborator a test double."""
    extract, _ = extract_agent([11])
    patterns, _ = pattern_agent([])
    forecaster, _ = forecast_agent()
    return orchestration_pipeline(
        extract=extract,
        patterns=patterns,
        forecast_agent=forecaster,
        fetcher=fetcher_returning([]),
        clock=FrozenClock(),
    )


def test_the_default_window_is_seven_days() -> None:
    """ROADMAP 5.5 names the window: the day being read and the six before it."""
    assert _pipeline().window_days == DEFAULT_WINDOW_DAYS == 7


def test_a_window_without_days_is_refused() -> None:
    """A window of zero days would make the reading blind; it is a call-site bug, not data."""
    with pytest.raises(PipelineError, match="window_days"):
        orchestration_pipeline(window_days=0)


def test_the_default_history_window_is_thirty_days() -> None:
    """ROADMAP 8.3 names the memory window; it is wider than the news window on purpose."""
    assert _pipeline().history_days == DEFAULT_HISTORY_DAYS == 30


def test_a_history_window_without_days_is_refused() -> None:
    """Memory of no days is no memory; the caller asked for something impossible."""
    with pytest.raises(PipelineError, match="history_days"):
        orchestration_pipeline(history_days=0)


def test_a_summary_limit_without_room_is_refused() -> None:
    """A digest that may summarise nothing would silently never be written."""
    with pytest.raises(PipelineError, match="summary_limit"):
        orchestration_pipeline(summary_limit=0)


def test_the_constructor_keeps_the_collaborators_it_was_given() -> None:
    """An injected store, clock and agents are the ones the properties report."""
    store = FakeStore()
    clock = FrozenClock()
    extract, _ = extract_agent([7])
    patterns, _ = pattern_agent([])
    forecaster, _ = forecast_agent()

    pipeline = Pipeline(
        store=store,  # type: ignore[arg-type]
        extract=extract,
        patterns=patterns,
        forecast_agent=forecaster,
        summarizer=summarize_agent()[0],
        fetcher=fetcher_returning([]),
        clock=clock,
    )

    assert pipeline.clock is clock
    assert pipeline.extract is extract
    assert pipeline.patterns is patterns
    assert pipeline.forecast_agent is forecaster
    assert pipeline.summarizer is not None
    assert pipeline.fetcher is not None
    assert pipeline.settings is not None
    assert pipeline.window_days == 7
    assert pipeline.history_days == 30
    assert pipeline.summary_limit == 50


def test_the_default_clock_reads_the_real_wall_and_monotonic_clocks() -> None:
    """`SystemClock` is what production uses, so it must answer both of the layer's questions."""
    clock = SystemClock()

    first = clock.monotonic()
    now = clock.now()

    assert now.tzinfo is UTC
    assert abs(now.timestamp() - datetime.now(UTC).timestamp()) < 5
    assert clock.monotonic() >= first


def test_closing_the_pipeline_closes_the_store() -> None:
    """A pipeline owns its store; the context manager releases the connection."""
    pipeline = _pipeline()

    with pipeline as entered:
        assert entered is pipeline

    assert pipeline.store.closed is True  # type: ignore[attr-defined]


def test_run_blocking_moves_the_call_to_another_thread() -> None:
    """The vector layer is synchronous; the pipeline runs it in a worker, not on the loop."""
    pipeline = _pipeline()
    loop_thread = threading.get_ident()

    worker_thread = asyncio.run(pipeline.run_blocking(threading.get_ident))

    assert worker_thread != loop_thread


def test_a_step_timer_records_what_the_clock_reported() -> None:
    """The duration is the monotonic delta, and the start is the wall-clock instant."""
    clock = FrozenClock(monotonic=100.0)

    with StepTimer(clock, "news") as timer:
        clock.advance(2.5)

    assert timer.timing is not None
    assert timer.timing == Timing(step="news", started_at=NOW, duration_seconds=2.5)
    assert timer.failed is False
    assert timer.step == "news"


def test_a_step_timer_still_records_a_failing_step() -> None:
    """The slow step that died is exactly the one a profile is looking for."""
    clock = FrozenClock(monotonic=5.0)

    with pytest.raises(RuntimeError, match="boom"), StepTimer(clock, "extract") as timer:
        clock.advance(1.0)
        raise RuntimeError("boom")

    assert timer.failed is True
    assert timer.timing is not None
    assert timer.timing.duration_seconds == 1.0


def test_a_clock_that_went_backwards_never_records_a_negative_duration() -> None:
    """The model refuses a negative duration; the timer clamps instead of crashing a step."""
    clock = FrozenClock(monotonic=10.0)

    with StepTimer(clock, "compute") as timer:
        clock.advance(-3.0)

    assert timer.timing is not None
    assert timer.timing.duration_seconds == 0.0


def test_timing_rejects_a_negative_duration() -> None:
    """The clamp exists because the model is strict about the field it guards."""
    with pytest.raises(ValidationError):
        Timing(step="news", started_at=datetime(2026, 9, 21, tzinfo=UTC), duration_seconds=-1.0)


def test_a_pipeline_run_is_frozen_and_strict() -> None:
    """A result crosses the CLI and MCP boundaries, so it is a frozen, strict model."""
    run = PipelineRun()

    assert run.news == ()
    assert run.activations == 0
    assert run.timings == ()
    with pytest.raises(ValidationError):
        run.activations = 1  # type: ignore[misc]


async def test_retrying_returns_the_first_success_without_retrying() -> None:
    """A step that works is attempted exactly once."""
    attempts = 0

    async def run() -> str:
        nonlocal attempts
        attempts += 1
        return "ok"

    assert await retrying("news", run) == "ok"
    assert attempts == 1


async def test_retrying_retries_an_agent_failure_once() -> None:
    """One retry absorbs a dropped connection or a single malformed answer."""
    attempts = 0

    async def run() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < ATTEMPTS:
            raise AgentExecutionError("find_patterns", "the model answered nonsense")
        return "ok"

    assert await retrying("analyze", run) == "ok"
    assert attempts == ATTEMPTS


async def test_retrying_surfaces_a_persistent_failure() -> None:
    """A broken endpoint must not turn into a silently thinner result."""

    async def run() -> str:
        raise AgentExecutionError("build_forecast", "the model answered nonsense")

    with pytest.raises(PipelineRetryError, match="build_forecast") as failure:
        await retrying("forecast", run)

    assert failure.value.step == "forecast"


async def test_retrying_does_not_repeat_a_non_agent_failure() -> None:
    """A `VectorStoreError` means the database is gone; a second attempt cannot help."""
    attempts = 0

    async def run() -> str:
        nonlocal attempts
        attempts += 1
        raise PipelineError("the store is gone")

    with pytest.raises(PipelineError, match="store is gone"):
        await retrying("embed", run)

    assert attempts == 1
