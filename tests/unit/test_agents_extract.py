"""Tests for `ExtractNumbersAgent` (ROADMAP 4.2).

The model is always a `pydantic-ai` test double, so these tests exercise the real structured-output
path — validation, retries, the `AgentRunError` on failure — without a network or a key.
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import ModelAPIError

from numenews.agents import ExtractNumbersAgent
from numenews.models import ExtractedNumbers

from .agent_fakes import answering, failing, recording, user_text

TEXT = "AI shares rose 7% on 21 September 2026"


async def test_extract_merges_the_model_reading_with_the_regex_pass() -> None:
    """The model reads first; the regex pass adds the numbers it missed, and `sources` says so."""
    agent = ExtractNumbersAgent(answering(numbers=[7], symbols=["AI"]))

    result = await agent.extract(TEXT)

    assert result == ExtractedNumbers(
        numbers=(7, 21, 2026),
        sources=("llm", "regex"),
        symbols=("AI",),
    )


async def test_extract_reports_a_model_only_reading_when_regex_adds_nothing() -> None:
    """A regex pass that contributes no new value is not claimed as a source."""
    agent = ExtractNumbersAgent(answering(numbers=[7], symbols=["AI"]))

    result = await agent.extract("AI shares rose 7 percent", symbols=("AI",))

    assert result.numbers == (7,)
    assert result.symbols == ("AI",)
    assert result.sources == ("llm",)


async def test_extract_uses_the_regex_fallback_when_the_model_fails() -> None:
    """ROADMAP 4.2: a broken provider degrades to `extract_numbers_regex`, it does not raise."""
    agent = ExtractNumbersAgent(failing(ModelAPIError(model_name="test", message="boom")))

    result = await agent.extract(TEXT, symbols=("AI", "$"))

    assert result == ExtractedNumbers(
        numbers=(7, 21, 2026),
        sources=("regex",),
        symbols=("AI",),
    )


async def test_extract_uses_the_regex_fallback_when_the_output_never_validates() -> None:
    """Output that stays invalid after the output retries is a failed model run like any other."""
    agent = ExtractNumbersAgent(answering(numbers=["seven"]))

    result = await agent.extract(TEXT)

    assert result.sources == ("regex",)
    assert result.numbers == (7, 21, 2026)


async def test_extract_deduplicates_numbers_in_text_order() -> None:
    """`ExtractedNumbers.numbers` is unique: the vector layer derives one point per number."""
    agent = ExtractNumbersAgent(answering(numbers=[]))

    result = await agent.extract("11 people, then 11 more people")

    assert result.numbers == (11,)


async def test_extract_sends_the_text_and_the_watchlist_to_the_model() -> None:
    """The prompt carries the text itself and the caller's symbol vocabulary."""
    model, recorder = recording(numbers=[7], symbols=["AI"])

    await ExtractNumbersAgent(model).extract(TEXT, symbols=("AI", "$"))

    prompt = user_text(recorder.calls[-1])
    assert TEXT in prompt
    assert "Watchlist symbols: AI, $" in prompt


async def test_extract_omits_the_watchlist_line_when_there_is_no_watchlist() -> None:
    """No watchlist means no empty header in the prompt."""
    model, recorder = recording(numbers=[7])

    await ExtractNumbersAgent(model).extract(TEXT)

    assert "Watchlist symbols" not in user_text(recorder.calls[-1])


@pytest.mark.parametrize("text", ["", "No numbers here at all."])
async def test_extract_returns_an_empty_reading_when_there_is_nothing_to_read(text: str) -> None:
    """An empty input is a valid result, not an error: both strategies simply find nothing."""
    agent = ExtractNumbersAgent(answering())

    result = await agent.extract(text)

    assert result == ExtractedNumbers(numbers=(), sources=("llm",), symbols=())
