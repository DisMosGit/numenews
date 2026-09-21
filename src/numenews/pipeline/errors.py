"""Failures of the pipeline layer.

The layer composes other layers, so most of what it can raise is already theirs: a
:class:`~numenews.agents.errors.AgentExecutionError` when a model run failed, a
:class:`~numenews.news.errors.NewsSourceError` when no feed is configured, a
:class:`~numenews.vector.errors.VectorStoreError` when Qdrant is unreachable. Two things are the
pipeline's own: a configuration it cannot accept, and a step that failed after its retry.
"""

from __future__ import annotations


class PipelineError(RuntimeError):
    """Base class for every error raised by ``numenews.pipeline``."""


class PipelineRetryError(PipelineError):
    """Raised when a step failed after its retry was already spent.

    The cause is always one of the step's own exceptions — typically an
    :class:`~numenews.agents.errors.AgentExecutionError` — so a caller can unwrap it to tell a
    transport failure from an answer that never validated.
    """

    def __init__(self, step: str, message: str) -> None:
        self.step = step
        super().__init__(f"{step}: {message}")
