"""The orchestrator: one object that holds every collaborator the steps need.

The four layers below are deliberately independent — ``news`` knows nothing of ``agents``,
``agents`` nothing of ``vector`` — so something has to compose them. That is this class, and it is
the *only* thing that knows the order of the chain: fetch news, read numbers out of it, reduce the
text, embed and store, connect the items, read the memory back, write the day's reading. Roadmap
5.1 calls it ``Pipeline``.

Three properties make it testable without a server, a key or a model:

* every collaborator is injectable — the vector store, the three agents, the news fetcher and the
  clock — and each defaults to the real thing;
* the pipeline is async while the vector layer is synchronous, and the one bridge is
  :func:`asyncio.to_thread` (ADR 0003);
* ``Pipeline`` itself holds no state between calls. Everything it remembers is in Qdrant, which is
  what makes a one-shot command idempotent (AGENTS.md).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from types import TracebackType
from typing import Self

from numenews.agents import ExtractNumbersAgent, ForecastAgent, PatternAgent
from numenews.config import Settings, get_settings
from numenews.models import DateRange, Forecast, NewsId, NewsItem, Topic
from numenews.news import fetch_news
from numenews.pipeline.clock import Clock, SystemClock
from numenews.pipeline.errors import PipelineError
from numenews.pipeline.timings import PipelineRun
from numenews.vector import VectorStore

#: How many calendar days one pipeline window covers, when the caller does not say. Roadmap 5.5
#: names seven: the day being read plus the six before it.
DEFAULT_WINDOW_DAYS = 7

#: What the news step calls when no fetcher is injected: a coroutine taking ``(topic, date_range)``.
type NewsFetcher = Callable[[Topic, DateRange], Awaitable[list[NewsItem]]]


class Pipeline:
    """Composes the news, reasoning and storage layers into one run.

    Args:
        settings: Configuration used to build whatever is not injected: the vector store and the
            three agents. Defaults to :func:`numenews.config.get_settings`.
        store: The Qdrant connection and its two embedders. Built from ``settings`` when omitted,
            which also proves the server answers (``VectorStore.from_settings`` health-checks).
        extract: The numbers reader. Built from ``settings`` when omitted.
        patterns: The connector of news items. Built from ``settings`` when omitted.
        forecast_agent: The prose writer. Built from ``settings`` when omitted.
        fetcher: The news step. Defaults to :func:`numenews.news.fetch_news`, which builds and
            closes its own cached HTTP client.
        clock: The only source of wall-clock and monotonic readings. Defaults to
            :class:`~numenews.pipeline.clock.SystemClock`.
        window_days: Length of the sliding window in calendar days, ending on the day being read.
        summary_limit: How many old items one digest summarises at most.

    Raises:
        PipelineError: when ``window_days`` or ``summary_limit`` is less than one — a window with
            no days would make every reading blind, which is a call-site bug, not a data condition.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        store: VectorStore | None = None,
        extract: ExtractNumbersAgent | None = None,
        patterns: PatternAgent | None = None,
        forecast_agent: ForecastAgent | None = None,
        fetcher: NewsFetcher | None = None,
        clock: Clock | None = None,
        window_days: int = DEFAULT_WINDOW_DAYS,
        summary_limit: int = 50,
    ) -> None:
        if window_days < 1:
            raise PipelineError(f"window_days must be at least 1, got {window_days}")
        if summary_limit < 1:
            raise PipelineError(f"summary_limit must be at least 1, got {summary_limit}")
        self._settings = settings if settings is not None else get_settings()
        self._store = store if store is not None else VectorStore.from_settings(self._settings)
        self._extract = (
            extract if extract is not None else ExtractNumbersAgent(settings=self._settings)
        )
        self._patterns = patterns if patterns is not None else PatternAgent(settings=self._settings)
        self._forecast_agent = (
            forecast_agent if forecast_agent is not None else ForecastAgent(settings=self._settings)
        )
        self._fetcher = fetcher if fetcher is not None else fetch_news
        self._clock = clock if clock is not None else SystemClock()
        self._window_days = window_days
        self._summary_limit = summary_limit

    @property
    def store(self) -> VectorStore:
        """The vector store this pipeline writes to and reads from."""
        return self._store

    @property
    def settings(self) -> Settings:
        """The configuration the default collaborators were built from."""
        return self._settings

    @property
    def clock(self) -> Clock:
        """The clock every step reads, for the timings and the windows."""
        return self._clock

    @property
    def extract(self) -> ExtractNumbersAgent:
        """The numbers reader used by the ingest step."""
        return self._extract

    @property
    def patterns(self) -> PatternAgent:
        """The connector used by the analyze step."""
        return self._patterns

    @property
    def forecast_agent(self) -> ForecastAgent:
        """The prose writer used by the forecast step."""
        return self._forecast_agent

    @property
    def fetcher(self) -> NewsFetcher:
        """The coroutine the news step calls, injectable so a test never touches the network."""
        return self._fetcher

    @property
    def window_days(self) -> int:
        """Length of the sliding window, in calendar days, ending on the day being read."""
        return self._window_days

    @property
    def summary_limit(self) -> int:
        """How many old items one digest summarises at most."""
        return self._summary_limit

    async def ingest(self, topic: Topic, date_range: DateRange) -> PipelineRun:
        """Fetch ``topic`` for ``date_range`` and store everything read out of it.

        Delegates to :func:`numenews.pipeline.steps.ingest`; the method exists so the everyday
        caller does not have to import the step functions.
        """
        from numenews.pipeline import steps

        return await steps.ingest(self, topic, date_range)

    async def analyze(self, news_ids: tuple[NewsId, ...]) -> PipelineRun:
        """Find and store the patterns among ``news_ids``.

        Delegates to :func:`numenews.pipeline.steps.analyze`.
        """
        from numenews.pipeline import steps

        return await steps.analyze(self, news_ids)

    async def forecast(self, day: date, *, rerun_analysis: bool = True) -> Forecast:
        """Return the reading for ``day``, from storage when it is already there.

        Delegates to :func:`numenews.pipeline.steps.forecast`.
        """
        from numenews.pipeline import steps

        return await steps.forecast(self, day, rerun_analysis=rerun_analysis)

    async def run_blocking[ResultT](self, call: Callable[[], ResultT]) -> ResultT:
        """Run the synchronous ``call`` in a worker thread, keeping the event loop free.

        The vector layer is synchronous by decision (ADR 0003) and every Qdrant call blocks on the
        network or on the local engine, so each call into ``store`` from the async pipeline goes
        through here.
        """
        return await asyncio.to_thread(call)

    def close(self) -> None:
        """Close the vector store and release its connections."""
        self._store.close()

    def __enter__(self) -> Self:
        """Return the pipeline itself, so it can be used as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the vector store on the way out, whatever happened inside the block."""
        self.close()


__all__ = ["DEFAULT_WINDOW_DAYS", "NewsFetcher", "Pipeline"]
