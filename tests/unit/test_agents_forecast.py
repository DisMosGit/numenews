"""Tests for `ForecastAgent` (ROADMAP 4.4).

What the model contributes is the prose; everything else in a `Forecast` is asserted to be the
caller's fact passed through unchanged. The history-injection tests read the prompt the model was
shown, which is what phase 8.3 extends with the real `number_history` window.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic_ai.exceptions import ModelAPIError

from numenews.agents import AgentExecutionError, ForecastAgent
from numenews.agents.prompts import HISTORY_CONTEXT_LIMIT
from numenews.models import Forecast, NewsId, NumberActivation, Pattern, PatternId

from .agent_fakes import answering, failing, recording, user_text

DAY = date(2026, 9, 22)
FIRST = UUID("00000000-0000-0000-0000-000000000001")


def _pattern() -> Pattern:
    """Return one pattern the forecast is supposed to rest on."""
    return Pattern(
        id=PatternId(FIRST),
        type="master",
        numbers=(11,),
        news_ids=(NewsId(FIRST),),
        strength=0.8,
        interpretation="Число 11 повторяется.",
    )


def _activation(number: int, *, day: date, context: str = "Some context.") -> NumberActivation:
    """Return one activation of ``number`` on ``day``."""
    return NumberActivation(number=number, date=day, news_id=NewsId(FIRST), context=context)


def _draft(**overrides: object) -> dict[str, object]:
    """Return one scripted `ForecastDraft` payload, valid unless a test overrides a field."""
    draft: dict[str, object] = {
        "forecast": "День под знаком одиннадцати.",
        "advice": "Слушайте интуицию.",
        "warnings": ["Возможны повторяющиеся события."],
    }
    draft.update(overrides)
    return draft


async def test_forecast_carries_every_field_of_the_domain_model() -> None:
    """ROADMAP 4.4: every `Forecast` field is present — facts from us, prose from the model."""
    agent = ForecastAgent(answering(**_draft()))
    patterns = [_pattern()]

    result = await agent.forecast(
        date=DAY, dominant_number=11, master_active=True, patterns=patterns
    )

    assert result == Forecast(
        date=DAY,
        dominant_number=11,
        master_active=True,
        patterns=(patterns[0],),
        forecast="День под знаком одиннадцати.",
        advice="Слушайте интуицию.",
        warnings=("Возможны повторяющиеся события.",),
    )


async def test_forecast_keeps_the_patterns_it_was_given() -> None:
    """The model never invents the day's patterns; the ones passed in are the ones returned."""
    agent = ForecastAgent(answering(**_draft(patterns=[])))

    result = await agent.forecast(date=DAY, dominant_number=3, master_active=False)

    assert result.patterns == ()
    assert result.warnings == ("Возможны повторяющиеся события.",)


async def test_forecast_rejects_blank_prose() -> None:
    """An empty reading is a failed run to retry, not a forecast."""
    agent = ForecastAgent(answering(**_draft(forecast="")))

    with pytest.raises(AgentExecutionError, match="build_forecast"):
        await agent.forecast(date=DAY, dominant_number=3, master_active=False)


async def test_forecast_raises_when_the_model_fails() -> None:
    """A broken provider is reported, so phase 5 can decide how to degrade."""
    agent = ForecastAgent(failing(ModelAPIError(model_name="test", message="boom")))

    with pytest.raises(AgentExecutionError, match="build_forecast"):
        await agent.forecast(date=DAY, dominant_number=3, master_active=False)


async def test_forecast_prompt_shows_the_day_the_patterns_and_the_history() -> None:
    """The model sees the facts the reading must rest on."""
    model, recorder = recording(**_draft())
    history = [_activation(11, day=date(2026, 9, 21))]

    await ForecastAgent(model).forecast(
        date=DAY,
        dominant_number=11,
        master_active=True,
        patterns=[_pattern()],
        history=history,
    )

    prompt = user_text(recorder.calls[-1])
    assert "Date: 2026-09-22" in prompt
    assert "Dominant number: 11 · master number active: yes" in prompt
    assert "Число 11 повторяется." in prompt
    assert "- 2026-09-21 · 11 · Some context." in prompt


async def test_forecast_prompt_says_so_when_there_is_no_history() -> None:
    """An empty history is stated, so the model does not read the gap as "no information"."""
    model, recorder = recording(**_draft())

    await ForecastAgent(model).forecast(date=DAY, dominant_number=3, master_active=False)

    prompt = user_text(recorder.calls[-1])
    assert "No number activations were recorded for this window." in prompt
    assert "No patterns were found for this day." in prompt


async def test_forecast_history_is_newest_first_and_cut_to_the_limit() -> None:
    """The block is deterministic (newest first) and one long context cannot crowd it out."""
    model, recorder = recording(**_draft())
    long_context = "y" * (HISTORY_CONTEXT_LIMIT + 50)
    history = [
        _activation(7, day=date(2026, 9, 19), context=long_context),
        _activation(11, day=date(2026, 9, 21)),
    ]

    await ForecastAgent(model).forecast(
        date=DAY, dominant_number=11, master_active=True, history=history
    )

    prompt = user_text(recorder.calls[-1])
    assert prompt.index("- 2026-09-21") < prompt.index("- 2026-09-19")
    assert "y" * HISTORY_CONTEXT_LIMIT in prompt
    assert "y" * (HISTORY_CONTEXT_LIMIT + 1) not in prompt
