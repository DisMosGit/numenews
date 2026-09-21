"""Failures of the reasoning layer.

An agent can fail for two different reasons, and a caller reacts differently to each: an endpoint
that is not configured at all is a mistake to fix before anything runs, while a run that failed is a
runtime outcome the pipeline of phase 5 may degrade from. Both derive from :class:`AgentError`, so
one ``except`` reads as "the agent could not do its job".
"""

from __future__ import annotations


class AgentError(RuntimeError):
    """Base class for every error raised by ``numenews.agents``."""


class LLMConfigurationError(AgentError):
    """Raised when the settings do not describe a usable LLM endpoint."""


class AgentExecutionError(AgentError):
    """Raised when a model run failed — a transport error, or output that never validated.

    ``agent`` names the agent that failed (``"extract_numbers"``), so a log line or an MCP error
    message says which of the three runs to look at without unwrapping the cause.
    """

    def __init__(self, agent: str, message: str) -> None:
        self.agent = agent
        super().__init__(f"{agent}: {message}")
