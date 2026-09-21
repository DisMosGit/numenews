"""Test doubles the agent tests share.

They live in a module rather than in ``conftest.py`` for the same reason as
``tests/integration/fakes.py``: a test that wants to know *what* the model was shown, or to script a
specific answer, needs the concrete type, not just a fixture name.

Every double is a ``pydantic_ai`` test model, so the agents' real machinery — structured output,
validation, retries — runs while no request ever leaves the process (``ALLOW_MODEL_REQUESTS`` is
turned off for the whole suite in ``tests/conftest.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

#: Name of the output tool ``pydantic-ai`` registers for a structured ``output_type``.
OUTPUT_TOOL = "final_result"


@dataclass
class ModelCall:
    """One recorded request to the model: what it was shown and what it was instructed."""

    messages: tuple[ModelMessage, ...]
    instructions: str | None


@dataclass
class Recorder:
    """A ``FunctionModel`` that answers with one output tool call and records every request."""

    output: dict[str, Any]
    calls: list[ModelCall] = field(default_factory=list)

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.calls.append(ModelCall(messages=tuple(messages), instructions=info.instructions))
        return ModelResponse(parts=[ToolCallPart(OUTPUT_TOOL, self.output)])


def answering(**args: Any) -> FunctionModel:
    """Return a model that answers every request with one output tool call.

    ``args`` are the tool-call arguments as the model would emit them: a draft's fields for an
    object output type, and ``response=<value>`` for a non-object one (``pydantic-ai`` wraps
    ``list[…]`` outputs in a single-element object).
    """
    return FunctionModel(Recorder(output=args))


def recording(**args: Any) -> tuple[FunctionModel, Recorder]:
    """Return a model that records its requests, and the recorder holding them."""
    recorder = Recorder(output=args)
    return FunctionModel(recorder), recorder


def failing(error: Exception) -> FunctionModel:
    """Return a model whose every request fails with ``error``, as a broken provider would."""

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise error

    return FunctionModel(respond)


def user_text(call: ModelCall) -> str:
    """Return the concatenated text of every user prompt the model was shown."""
    chunks = [
        part.content
        for message in call.messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    ]
    return "\n".join(chunks)
