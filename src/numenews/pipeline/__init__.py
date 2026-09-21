"""The RAG pipeline: the one place that knows the order of the chain.

``news`` fetches, ``numerology`` reads, ``agents`` reason, ``vector`` remembers — and none of them
imports the others. This package composes them in the order roadmap 5.2-5.4 describe::

    fetch news → extract numbers → compute numerology → embed and upsert
        → find patterns → read activation history → build the forecast → save it

:class:`~numenews.pipeline.pipeline.Pipeline` holds the collaborators and the sliding window;
:mod:`numenews.pipeline.steps` holds one async function per step; :mod:`numenews.pipeline.context`
holds the window rule and the digest that summarises the news it leaves behind.

The package is the *only* async caller of the synchronous vector layer, and the bridge is
``asyncio.to_thread`` (ADR 0003). It owns no state: everything a run remembers lives in Qdrant, so a
one-shot command is idempotent and resumable (AGENTS.md).
"""

from __future__ import annotations

from numenews.pipeline.clock import Clock, SystemClock
from numenews.pipeline.context import build_digest, partition, window_start
from numenews.pipeline.errors import PipelineError, PipelineRetryError
from numenews.pipeline.pipeline import (
    DEFAULT_HISTORY_DAYS,
    DEFAULT_WINDOW_DAYS,
    NewsFetcher,
    Pipeline,
)
from numenews.pipeline.steps import (
    activate,
    context_snippet,
    reading_text,
    reduced_value,
)
from numenews.pipeline.timings import PipelineRun, StepTimer, Timing

__all__ = [
    "DEFAULT_HISTORY_DAYS",
    "DEFAULT_WINDOW_DAYS",
    "Clock",
    "NewsFetcher",
    "Pipeline",
    "PipelineError",
    "PipelineRetryError",
    "PipelineRun",
    "StepTimer",
    "SystemClock",
    "Timing",
    "activate",
    "build_digest",
    "context_snippet",
    "partition",
    "reading_text",
    "reduced_value",
    "window_start",
]
