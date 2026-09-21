"""How an MCP tool reports a failure.

The layers below raise their own exceptions — :class:`~numenews.vector.errors.VectorStoreError` when
Qdrant does not answer, :class:`~numenews.agents.errors.AgentError` when the model run failed,
:class:`~numenews.news.errors.NewsSourceError` when no feed is configured and
:class:`~numenews.pipeline.errors.PipelineError` when a step spent its retry. None of them knows it
is being called by a language model.

Phase 5 deliberately left the reporting decision here ("phase 6 decides how an MCP tool reports a
failure"), and the SDK draws the line: a raised :class:`~mcp.server.mcpserver.exceptions.ToolError`
becomes a normal result with ``is_error=True`` whose message the model reads and can act on, while
any other exception is sanitised into a generic failure and logged with a traceback.

So every *expected* domain failure is translated into a ``ToolError`` — the model can fix a missing
collection, an unset key or a mistyped id — and anything else is left to crash. A defect in our own
mapping must stay loud, not become a quietly thinner result (the same rule as phase 2.8).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver.exceptions import ToolError

from numenews.agents.errors import AgentError
from numenews.news.errors import NewsSourceError
from numenews.pipeline.errors import PipelineError
from numenews.vector.errors import VectorStoreError

#: The failures a caller of the MCP tools is expected to hit and can do something about.
#: ``CollectionNotFoundError`` and ``LLMConfigurationError`` are subclasses of members, so the tuple
#: stays short on purpose.
DOMAIN_ERRORS = (AgentError, NewsSourceError, PipelineError, VectorStoreError)


@contextmanager
def tool_errors() -> Iterator[None]:
    """Turn an expected domain failure into a ``ToolError`` the model can read.

    Used as::

        with tool_errors():
            return await something()

    A ``ToolError`` raised inside the block passes through unchanged, and so does any exception that
    is not in :data:`DOMAIN_ERRORS` — those are bugs, and the SDK's sanitised crash plus the ERROR
    traceback is the right report for them.
    """
    try:
        yield
    except DOMAIN_ERRORS as error:
        raise ToolError(str(error)) from error


__all__ = ["DOMAIN_ERRORS", "tool_errors"]
