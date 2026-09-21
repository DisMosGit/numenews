"""The step functions the ``Pipeline`` methods delegate to.

Each step is a plain async function over a :class:`~numenews.pipeline.pipeline.Pipeline`, so the
orchestration is testable without constructing a class around a fake and the ``Pipeline`` methods
stay three-line delegations. Every step follows the same shape:

1. run the work inside a :class:`~numenews.pipeline.timings.StepTimer`, which records the monotonic
   duration regardless of outcome;
2. log one ``pipeline.step`` line with the step's counters (roadmap 5.1);
3. put the recorded timing into the returned model, so a caller can report the profile.

Blocking vector calls go through :meth:`Pipeline.run_blocking` (``asyncio.to_thread``); the model
runs are already async. A step that failed logs ``pipeline.step.failed`` and lets the exception out
— the pipeline does not fabricate a result, and phase 6 decides how an MCP tool reports a failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date

from numenews.agents import AgentError
from numenews.logging import get_logger
from numenews.models import DateRange, Forecast, NewsId, Topic
from numenews.pipeline.errors import PipelineError, PipelineRetryError
from numenews.pipeline.pipeline import Pipeline
from numenews.pipeline.timings import PipelineRun, Timing

logger = get_logger(__name__)

#: How many attempts a model-backed step gets before its failure is surfaced. One retry absorbs a
#: dropped connection or a single malformed answer; more than one turns a broken endpoint into a
#: long, expensive run.
ATTEMPTS = 2


async def retrying[ResultT](step: str, run: Callable[[], Awaitable[ResultT]]) -> ResultT:
    """Run ``run`` up to :data:`ATTEMPTS` times, raising :class:`PipelineRetryError` at the end.

    Only agent failures are retried. A ``VectorStoreError`` means the database is gone and a second
    attempt cannot help, and an :class:`PipelineError` is the pipeline's own configuration, never
    worth repeating.
    """
    last: AgentError | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return await run()
        except AgentError as error:
            last = error
            logger.warning(
                "pipeline.step.retry",
                step=step,
                attempt=attempt,
                attempts=ATTEMPTS,
                error=str(error),
            )
    if last is None:  # pragma: no cover
        raise PipelineError(f"{step} was never attempted")
    raise PipelineRetryError(step, str(last))


async def ingest(pipeline: Pipeline, topic: Topic, date_range: DateRange) -> PipelineRun:
    """Fetch the news and store everything the extraction step read out of it.

    The chain of roadmap 5.2 — fetch → extract → compute → embed → upsert — with each link timed.
    Implemented in this phase's 5.2 commit.
    """
    raise PipelineError("pipeline.steps.ingest lands in roadmap 5.2")


async def analyze(pipeline: Pipeline, news_ids: tuple[NewsId, ...]) -> PipelineRun:
    """Find the patterns among ``news_ids`` and store them.

    Roadmap 5.3. Implemented in this phase's 5.3 commit.
    """
    raise PipelineError("pipeline.steps.analyze lands in roadmap 5.3")


async def forecast(pipeline: Pipeline, day: date, *, rerun_analysis: bool = True) -> Forecast:
    """Return the reading for ``day``, from storage when it is already there.

    Roadmap 5.4. Implemented in this phase's 5.4 commit.
    """
    raise PipelineError("pipeline.steps.forecast lands in roadmap 5.4")


def timings(*taken: Timing | None) -> tuple[Timing, ...]:
    """Return the recorded timings, in step order, dropping the ones a step did not reach."""
    return tuple(timing for timing in taken if timing is not None)


__all__ = ["ATTEMPTS", "analyze", "forecast", "ingest", "retrying", "timings"]
