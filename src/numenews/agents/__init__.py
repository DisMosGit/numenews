"""``pydantic-ai`` agents: extract numbers, find patterns, build the forecast.

Each agent is a small class around a ``pydantic_ai.Agent``. The model's ``output_type`` is a *draft*
schema that holds only what a language model can know; the wrapper then returns the domain model of
``numenews.models``, stamping provenance (``ExtractedNumbers.sources``), identity (``Pattern.id``)
and the numerological fields the pure layer computed. Free-form JSON parsing is not allowed.

The model comes from :func:`build_llm_model` — any OpenAI-compatible endpoint — and every agent
accepts an explicit ``pydantic_ai.models.Model`` instead, which is how the tests run without a
network. The prompts live in :mod:`numenews.agents.prompts` and are documented in
``docs/PROMPTS.md``.
"""

from __future__ import annotations

from numenews.agents.errors import AgentError, AgentExecutionError, LLMConfigurationError
from numenews.agents.extract import ExtractNumbersAgent
from numenews.agents.llm import build_llm_model
from numenews.agents.pattern import PatternAgent, pattern_id
from numenews.agents.schemas import ExtractionDraft, PatternDraft

__all__ = [
    "AgentError",
    "AgentExecutionError",
    "ExtractNumbersAgent",
    "ExtractionDraft",
    "LLMConfigurationError",
    "PatternAgent",
    "PatternDraft",
    "build_llm_model",
    "pattern_id",
]
