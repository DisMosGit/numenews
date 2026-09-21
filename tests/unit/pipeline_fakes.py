"""Test doubles the pipeline tests share.

The pipeline composes four layers, so a unit test replaces all four. The agents are *real*
``ExtractNumbersAgent`` / ``PatternAgent`` / ``ForecastAgent`` instances driven by a
``FunctionModel`` double — the same kit as ``tests/unit/agent_fakes.py`` — so a pipeline test
exercises the genuine structured-output path while no request leaves the process.

:class:`FrozenClock` is the important one: the pipeline reads the wall clock for the day a window
ends on and the monotonic clock for a step's duration, so a test that controls both can assert an
exact timing and a date-independent window instead of sleeping or accepting "roughly now".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

from numenews.agents import ExtractNumbersAgent, ForecastAgent, PatternAgent
from numenews.models import ExtractedNumbers
from numenews.pipeline import Pipeline

from .agent_fakes import Recorder

#: A fixed instant the pipeline tests work from; the frozen clock starts here.
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class FrozenClock:
    """A clock that returns what the test tells it to, and nothing else.

    ``monotonic`` advances only when a test calls :meth:`advance`, so a recorded duration is exactly
    the value the test chose — no sleeps, no flakes.
    """

    def __init__(self, *, now: datetime = NOW, monotonic: float = 0.0) -> None:
        self._now = now
        self._monotonic = monotonic

    def now(self) -> datetime:
        """Return the instant the test froze."""
        return self._now

    def monotonic(self) -> float:
        """Return the seconds value the test chose."""
        return self._monotonic

    def advance(self, seconds: float) -> None:
        """Move the monotonic clock forward, as a step taking ``seconds`` would."""
        self._monotonic += seconds

    def travel_to(self, moment: datetime) -> None:
        """Move the wall clock, as a new day would."""
        self._now = moment

    def tomorrow(self) -> None:
        """Move the wall clock one day forward, the most common window boundary in a test."""
        self._now = self._now + timedelta(days=1)


class FakeStore:
    """A vector store that answers nothing.

    Tests that only exercise the orchestration (timings, retries, wiring) need an object to hand to
    :class:`~numenews.pipeline.pipeline.Pipeline`; tests that need real vector behaviour build a
    ``VectorStore.in_memory`` with the fake embedders instead. Any test that reaches the vector code
    path must use the real store — this one only records that it was closed.
    """

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        """Record that the pipeline closed this store."""
        self.closed = True


def orchestration_pipeline(**kwargs: object) -> Pipeline:
    """Return a :class:`Pipeline` over :class:`FakeStore`, with the given keyword arguments.

    The single place a test double is passed where a ``VectorStore`` is expected, so the
    inconvenient downcast exists once instead of in every test that only cares about the wiring.
    """
    return Pipeline(store=FakeStore(), **kwargs)  # type: ignore[arg-type]


@dataclass
class ModelCounter:
    """Counts every request a ``FunctionModel`` answers, so a test can prove no call happened."""

    calls: int = field(default=0)

    def record(self) -> None:
        """Record one request."""
        self.calls += 1


def counting_model(output: Any) -> tuple[FunctionModel, ModelCounter]:
    """Return a ``FunctionModel`` answering with ``output`` and the counter watching it.

    ``output`` is the structured answer as the model would emit it: a draft's fields for an object
    output type, and ``response=[...]`` for the list-typed output of the pattern agent.
    """
    counter = ModelCounter()
    recorder = Recorder(output=output)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        counter.record()
        return recorder(messages, info)

    return FunctionModel(respond), counter


def extract_agent(
    numbers: list[int],
    *,
    symbols: list[str] | None = None,
) -> tuple[ExtractNumbersAgent, ModelCounter]:
    """Return a real ``ExtractNumbersAgent`` whose model answers with ``numbers``."""
    model, counter = counting_model({"numbers": numbers, "symbols": symbols or []})
    return ExtractNumbersAgent(model), counter


def pattern_agent(patterns: list[dict[str, Any]]) -> tuple[PatternAgent, ModelCounter]:
    """Return a real ``PatternAgent`` whose model answers with ``patterns``."""
    model, counter = counting_model({"response": patterns})
    return PatternAgent(model), counter


def forecast_agent(
    *,
    forecast: str = "День под знаком одиннадцати.",
    advice: str = "Слушайте интуицию.",
    warnings: list[str] | None = None,
) -> tuple[ForecastAgent, ModelCounter]:
    """Return a real ``ForecastAgent`` whose model answers with the given prose."""
    payload = {
        "forecast": forecast,
        "advice": advice,
        "warnings": ["Возможны повторяющиеся события."] if warnings is None else warnings,
    }
    model, counter = counting_model(payload)
    return ForecastAgent(model), counter


def broken_model() -> FunctionModel:
    """Return a ``FunctionModel`` that raises the way an unreachable endpoint would."""
    counter = ModelCounter()

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        counter.record()
        raise ModelAPIError("test-model", "the endpoint is unreachable")

    return FunctionModel(respond)


class ScriptedExtract:
    """An ``ExtractNumbersAgent`` that answers per text instead of per model script.

    It is a subclass, so it stands in wherever the real class is expected (the pipeline takes it by
    annotation, not by runtime check), and it records the texts it was shown — which is how a test
    proves the pipeline reads a headline together with its body.
    """

    def __init__(self, answers: dict[str, tuple[int, ...]] | None = None) -> None:
        self._answers = dict(answers or {})
        self.texts: list[str] = []

    async def extract(self, text: str, *, symbols: Sequence[str] = ()) -> ExtractedNumbers:
        """Record ``text`` and return the scripted numbers, empty for an unscripted text."""
        self.texts.append(text)
        return ExtractedNumbers(numbers=self._answers.get(text, ()), sources=("llm",))


def fetcher_returning(items: Sequence[Any], *, seen: list[tuple[Any, Any]] | None = None) -> Any:
    """Return a news fetcher that answers ``items`` and records the arguments it was called with."""

    async def fetch(topic: Any, date_range: Any) -> list[Any]:
        if seen is not None:
            seen.append((topic, date_range))
        return list(items)

    return fetch
