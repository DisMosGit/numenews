"""The failure policy of the MCP tools (ROADMAP 6.x).

Phase 5 deferred this decision to phase 6: a tool that hits a condition the model can act on
hands it a ``ToolError`` (a result with ``is_error=True`` and a readable message), while a
condition the model cannot fix — or a bug in our own code — is left alone so the SDK sanitises
it and logs a traceback. These tests pin both halves of that line.
"""

from __future__ import annotations

import re

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from numenews.agents.errors import AgentError, AgentExecutionError, LLMConfigurationError
from numenews.mcp.errors import DOMAIN_ERRORS, tool_errors
from numenews.news.errors import NewsSourceError
from numenews.pipeline.errors import PipelineError, PipelineRetryError
from numenews.vector.errors import CollectionNotFoundError, VectorStoreError

DOMAIN_FAILURES: tuple[Exception, ...] = (
    VectorStoreError("qdrant is not reachable: run `make dev`"),
    CollectionNotFoundError("collection 'news' does not exist"),
    AgentExecutionError("forecast", "the endpoint answered 503"),
    LLMConfigurationError("No LLM endpoint configured"),
    NewsSourceError("no news sources are configured"),
    PipelineError("window_days must be at least 1"),
    PipelineRetryError("find_patterns", "the model never answered"),
)


def test_every_expected_domain_failure_becomes_a_tool_error() -> None:
    """The model reads the message and can correct what it did."""
    for failure in DOMAIN_FAILURES:
        with pytest.raises(ToolError, match=re.escape(str(failure))), tool_errors():
            raise failure


def test_the_translated_error_keeps_the_cause() -> None:
    """The original exception stays attached, so a log still shows where it came from."""
    failure = VectorStoreError("qdrant is not reachable")

    with pytest.raises(ToolError) as raised, tool_errors():
        raise failure

    assert raised.value.__cause__ is failure


def test_a_tool_error_passes_through_unchanged() -> None:
    """A tool that already decided its message must not be wrapped a second time."""
    with pytest.raises(ToolError, match="filters apply to the news"), tool_errors():
        raise ToolError("filters apply to the news collection only")


def test_an_unexpected_error_is_left_alone() -> None:
    """A defect in our own code must stay loud instead of becoming a quiet tool result."""
    with pytest.raises(RuntimeError, match="boom"), tool_errors():
        raise RuntimeError("boom")


def test_the_domain_error_tuple_names_the_four_base_classes() -> None:
    """Specific failures are subclasses, so the tuple stays short and every one is covered."""
    assert set(DOMAIN_ERRORS) == {AgentError, NewsSourceError, PipelineError, VectorStoreError}
    assert issubclass(CollectionNotFoundError, VectorStoreError)
    assert issubclass(LLMConfigurationError, AgentError)
