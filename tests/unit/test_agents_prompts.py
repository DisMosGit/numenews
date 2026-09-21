"""Prompt-format tests for the reasoning layer (ROADMAP 4.5).

The project has no snapshot library, so the snapshot is a literal: each rendered prompt is compared
with the exact text the agent will send. When a prompt changes on purpose, this file changes with
it — that is the point, not an accident.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from numenews.agents import (
    ExtractionDraft,
    ExtractNumbersAgent,
    ForecastAgent,
    ForecastDraft,
    PatternAgent,
    PatternDraft,
)
from numenews.agents.prompts import (
    EXTRACT_FEW_SHOT,
    EXTRACT_INSTRUCTIONS,
    EXTRACT_RULES,
    FORECAST_FEW_SHOT,
    FORECAST_INSTRUCTIONS,
    FORECAST_RULES,
    PATTERN_FEW_SHOT,
    PATTERN_INSTRUCTIONS,
    PATTERN_RULES,
    build_extract_prompt,
    build_forecast_prompt,
    build_pattern_prompt,
)
from numenews.models import NewsId, NewsItem, NumberActivation, Pattern, PatternId

from .agent_fakes import recording

FIRST = UUID("00000000-0000-0000-0000-000000000001")


def _item() -> NewsItem:
    """Return one news item with known values, so the snapshot below is readable."""
    return NewsItem(
        id=NewsId(FIRST),
        title="Eleven ministers resign",
        text="Eleven ministers resigned today.",
        source="example.com",
        date=date(2026, 9, 21),
        url="https://example.com/budget",
        numbers=(11, 21),
        numerology_value=11,
    )


def _pattern() -> Pattern:
    """Return one pattern with known values."""
    return Pattern(
        id=PatternId(FIRST),
        type="master",
        numbers=(11,),
        news_ids=(NewsId(FIRST),),
        strength=0.9,
        interpretation="Число 11 повторяется.",
    )


def _activation() -> NumberActivation:
    """Return one activation with known values."""
    return NumberActivation(
        number=11,
        date=date(2026, 9, 21),
        news_id=NewsId(FIRST),
        context="Eleven ministers resigned.",
    )


def test_extract_prompt_snapshot() -> None:
    """One text and one watchlist render exactly as written here."""
    assert build_extract_prompt("Some text.", ("AI", "$")) == (
        "Watchlist symbols: AI, $\n\nText:\nSome text."
    )


def test_extract_prompt_without_a_watchlist_snapshot() -> None:
    """No watchlist means no header line."""
    assert build_extract_prompt("Some text.") == "Text:\nSome text."


def test_pattern_prompt_snapshot() -> None:
    """Every fact the model must cite is on its own line, under a numbered item."""
    assert build_pattern_prompt([_item()]) == (
        "News items to analyse:\n"
        "\n"
        "1. id: 00000000-0000-0000-0000-000000000001\n"
        "   date: 2026-09-21 · source: example.com · numerology_value: 11\n"
        "   title: Eleven ministers resign\n"
        "   numbers: 11, 21\n"
        "   text: Eleven ministers resigned today."
    )


def test_forecast_prompt_snapshot() -> None:
    """The day, its patterns and its history render in a fixed, checkable order."""
    assert build_forecast_prompt(
        date=date(2026, 9, 22),
        dominant_number=11,
        master_active=True,
        patterns=[_pattern()],
        history=[_activation()],
    ) == (
        "Date: 2026-09-22\n"
        "Dominant number: 11 · master number active: yes\n"
        "\n"
        "Patterns found for this day:\n"
        "- master · strength 0.90 · numbers 11 · Число 11 повторяется.\n"
        "\n"
        "Number activations of the recent past:\n"
        "- 2026-09-21 · 11 · Eleven ministers resigned."
    )


def test_forecast_prompt_without_context_snapshot() -> None:
    """A day with no patterns and no history states both gaps instead of leaving them blank."""
    assert build_forecast_prompt(
        date=date(2026, 9, 22), dominant_number=3, master_active=False
    ) == (
        "Date: 2026-09-22\n"
        "Dominant number: 3 · master number active: no\n"
        "\n"
        "Patterns found for this day:\n"
        "No patterns were found for this day.\n"
        "\n"
        "Number activations of the recent past:\n"
        "No number activations were recorded for this window."
    )


def test_the_instructions_are_the_rules_plus_the_worked_example() -> None:
    """Each `*_INSTRUCTIONS` is its rules block and its few-shot block, in that order."""
    for instructions, rules, few_shot in (
        (EXTRACT_INSTRUCTIONS, EXTRACT_RULES, EXTRACT_FEW_SHOT),
        (PATTERN_INSTRUCTIONS, PATTERN_RULES, PATTERN_FEW_SHOT),
        (FORECAST_INSTRUCTIONS, FORECAST_RULES, FORECAST_FEW_SHOT),
    ):
        assert instructions == f"{rules}\n\n{few_shot}"
        assert instructions.index(rules) < instructions.index(few_shot)
        assert "Example" in few_shot
        assert "Output:" in few_shot


def _example_answer(block: str) -> object:
    """Return the JSON a few-shot block shows as the answer.

    The examples in `prompts.py` keep their JSON free of blank lines, so the answer ends at the
    first blank line after ``Output:``.
    """
    start = block.index("Output:\n") + len("Output:\n")
    end = block.find("\n\n", start)
    return json.loads(block[start:] if end == -1 else block[start:end])


@pytest.mark.parametrize(
    ("block", "validate"),
    [
        (EXTRACT_FEW_SHOT, ExtractionDraft.model_validate),
        (PATTERN_FEW_SHOT, TypeAdapter(list[PatternDraft]).validate_python),
        (FORECAST_FEW_SHOT, ForecastDraft.model_validate),
    ],
)
def test_the_worked_example_is_a_valid_answer(
    block: str, validate: Callable[[object], object]
) -> None:
    """An example the schema would reject would teach the model the wrong shape."""
    assert validate(_example_answer(block)) is not None


async def test_every_agent_sends_its_rules_and_example_to_the_model() -> None:
    """The composed instructions are what the agent actually hands to the model."""
    extract_model, extract_recorder = recording()
    await ExtractNumbersAgent(extract_model).extract("Some text.")

    pattern_model, pattern_recorder = recording(response=[])
    await PatternAgent(pattern_model).find_patterns([_item()])

    forecast_model, forecast_recorder = recording(forecast="День.", advice="Совет.")
    await ForecastAgent(forecast_model).forecast(
        date=date(2026, 9, 22), dominant_number=3, master_active=False
    )

    for recorder, expected in (
        (extract_recorder, EXTRACT_INSTRUCTIONS),
        (pattern_recorder, PATTERN_INSTRUCTIONS),
        (forecast_recorder, FORECAST_INSTRUCTIONS),
    ):
        assert recorder.calls[-1].instructions == expected.strip()
