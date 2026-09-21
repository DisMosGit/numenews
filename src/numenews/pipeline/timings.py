"""Per-step durations, and the result a pipeline call hands back.

A pipeline call is one request to a log, a database and a language model, so "which step was slow"
is a question worth answering with data instead of a profiler. Every step is wrapped in a
:class:`StepTimer`, which records the wall-clock moment it started (for the log line) and the
monotonic duration it took (for the profile), both read from the injected
:class:`~numenews.pipeline.clock.Clock`.

The timings are part of the returned :class:`PipelineRun`, not a private logger side channel:
roadmap 5.1 asks for them "для профилирования", and a caller that wants to report them — the CLI of
phase 7, an MCP tool of phase 6 — should not have to scrape stderr.
"""

from __future__ import annotations

from datetime import datetime
from types import TracebackType

from pydantic import BaseModel, ConfigDict, Field

from numenews.models import NewsItem, Pattern
from numenews.pipeline.clock import Clock


class Timing(BaseModel):
    """How long one step took, and when it started.

    ``duration_seconds`` is a monotonic delta, so it is never negative; ``started_at`` is UTC wall
    time and exists for the log line and for a human reading the JSON.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    step: str
    started_at: datetime
    duration_seconds: float = Field(ge=0.0)


class PipelineRun(BaseModel):
    """The outcome of a pipeline call: what it saw, what it wrote, and how long each step took.

    A frozen model rather than a tuple, because the CLI of phase 7 serializes it and roadmap 5.1's
    timings belong in that answer. ``news`` carries the items as they were stored — extraction and
    reduction already applied — and ``patterns`` the connections the analyze step found, so a caller
    can read both without a second lookup.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    news: tuple[NewsItem, ...] = ()
    patterns: tuple[Pattern, ...] = ()
    activations: int = Field(default=0, ge=0)
    timings: tuple[Timing, ...] = ()


class StepTimer:
    """Context manager recording one step's start, duration and outcome.

    Used as::

        with StepTimer(clock, "news") as timer:
            items = await fetch(...)
        # timer.timing is a Timing; timer.failed says whether the block raised

    ``timing`` is set on exit even when the block raised, because a step that died after eight
    seconds is exactly the one a profile is looking for. The caller (``pipeline.steps``) logs the
    line and decides whether to re-raise.
    """

    def __init__(self, clock: Clock, step: str) -> None:
        self._clock = clock
        self._step = step
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self.timing: Timing | None = None
        self.failed = False

    @property
    def step(self) -> str:
        """The label this timer reports, e.g. ``"news"`` or ``"forecast"``."""
        return self._step

    def __enter__(self) -> StepTimer:
        """Record the start of the step."""
        self._started_at = self._clock.now()
        self._started_monotonic = self._clock.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Record the step's duration, whether or not the block raised."""
        if self._started_at is None or self._started_monotonic is None:  # pragma: no cover
            raise RuntimeError("StepTimer used outside a with block")
        duration = self._clock.monotonic() - self._started_monotonic
        self.timing = Timing(
            step=self._step,
            # A clock that went backwards would produce a negative duration, which the model
            # refuses (``ge=0.0``); clamping keeps a broken fake from turning into a validation
            # crash in the middle of a step.
            duration_seconds=max(duration, 0.0),
            started_at=self._started_at,
        )
        self.failed = exc_type is not None
