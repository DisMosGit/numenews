"""Tests for `PatternAgent` (ROADMAP 4.3).

The model is a `pydantic-ai` test double throughout: one test proves the prompt carries the items,
the others prove what this layer — not the model — decides: which ids a pattern may cite, what its
identity is, and that an out-of-range strength never becomes a `Pattern`.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic_ai.exceptions import ModelAPIError

from numenews.agents import AgentExecutionError, PatternAgent, pattern_id
from numenews.agents.prompts import PATTERN_TEXT_LIMIT
from numenews.models import NewsId, NewsItem

from .agent_fakes import answering, failing, recording, user_text

FIRST = UUID("00000000-0000-0000-0000-000000000001")
SECOND = UUID("00000000-0000-0000-0000-000000000002")
STRANGER = UUID("00000000-0000-0000-0000-0000000000ff")


def _item(item_id: UUID, *, text: str = "Some text.", numbers: tuple[int, ...] = ()) -> NewsItem:
    """Return a news item with a known id, so a test can cite it in a scripted answer."""
    return NewsItem(
        id=NewsId(item_id),
        title=f"Title {item_id.int}",
        text=text,
        source="example.com",
        date=date(2026, 9, 21),
        url=f"https://example.com/{item_id.int}",
        numbers=numbers,
        numerology_value=11,
    )


def _draft(**overrides: object) -> dict[str, object]:
    """Return one scripted `PatternDraft` payload, valid unless a test overrides a field."""
    draft: dict[str, object] = {
        "type": "master",
        "numbers": [11],
        "news_ids": [str(FIRST), str(SECOND)],
        "strength": 0.8,
        "interpretation": "Число 11 повторяется в обеих новостях.",
    }
    draft.update(overrides)
    return draft


async def test_find_patterns_returns_the_model_connections() -> None:
    """A valid draft becomes a `Pattern` carrying this layer's identity, not the model's."""
    agent = PatternAgent(answering(response=[_draft()]))
    news = [_item(FIRST, numbers=(11,)), _item(SECOND, numbers=(11,))]

    patterns = await agent.find_patterns(news)

    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.type == "master"
    assert pattern.numbers == (11,)
    assert pattern.news_ids == (NewsId(FIRST), NewsId(SECOND))
    assert pattern.strength == 0.8
    assert pattern.interpretation == "Число 11 повторяется в обеих новостях."
    assert pattern.discovered_at is None
    assert pattern.id == pattern_id("master", (11,), (NewsId(FIRST), NewsId(SECOND)))


async def test_find_patterns_keeps_only_the_ids_it_was_given() -> None:
    """An id the model invented (or mangled) is not a connection this layer can store."""
    agent = PatternAgent(
        answering(response=[_draft(news_ids=[str(FIRST), str(STRANGER), "not-a-uuid"])])
    )

    patterns = await agent.find_patterns([_item(FIRST), _item(SECOND)])

    assert [pattern.news_ids for pattern in patterns] == [(NewsId(FIRST),)]


async def test_find_patterns_drops_a_connection_with_no_known_item() -> None:
    """A pattern that cites nothing the caller passed is dropped, not stored with no evidence."""
    agent = PatternAgent(answering(response=[_draft(news_ids=[str(STRANGER)])]))

    assert await agent.find_patterns([_item(FIRST)]) == []


async def test_find_patterns_rejects_a_strength_outside_the_unit_interval() -> None:
    """ROADMAP 4.3: Pydantic rejects an invalid confidence instead of clamping it."""
    agent = PatternAgent(answering(response=[_draft(strength=1.5)]))

    with pytest.raises(AgentExecutionError, match="find_patterns"):
        await agent.find_patterns([_item(FIRST), _item(SECOND)])


async def test_find_patterns_makes_a_stable_id_for_the_same_connection() -> None:
    """Two runs over the same items produce the same point id, so saving is idempotent."""
    agent = PatternAgent(answering(response=[_draft()]))
    news = [_item(FIRST), _item(SECOND)]

    first = await agent.find_patterns(news)
    second = await agent.find_patterns(news)

    assert first == second


async def test_find_patterns_raises_when_the_model_fails() -> None:
    """A failed run is reported as an agent error, never as an empty list."""
    agent = PatternAgent(failing(ModelAPIError(model_name="test", message="boom")))

    with pytest.raises(AgentExecutionError, match="find_patterns"):
        await agent.find_patterns([_item(FIRST)])


async def test_find_patterns_without_news_does_not_call_the_model() -> None:
    """Nothing to connect is answered locally — the empty list is a result, not a failed run."""
    model, recorder = recording(response=[])

    result = await PatternAgent(model).find_patterns([])

    assert result == []
    assert recorder.calls == []


async def test_find_patterns_prompt_carries_every_item() -> None:
    """The model sees the id it must cite, the date, the source, the numbers and the text."""
    model, recorder = recording(response=[])
    news = [_item(FIRST, text="Eleven ministers met.", numbers=(11, 22)), _item(SECOND)]

    await PatternAgent(model).find_patterns(news)

    prompt = user_text(recorder.calls[-1])
    assert str(FIRST) in prompt
    assert "2026-09-21" in prompt
    assert "source: example.com" in prompt
    assert "numbers: 11, 22" in prompt
    assert "numerology_value: 11" in prompt
    assert "Eleven ministers met." in prompt


async def test_find_patterns_truncates_a_long_item() -> None:
    """A long article does not crowd the other items out of the prompt."""
    model, recorder = recording(response=[])
    long_text = "x" * (PATTERN_TEXT_LIMIT + 500)

    await PatternAgent(model).find_patterns([_item(FIRST, text=long_text)])

    prompt = user_text(recorder.calls[-1])
    assert "x" * PATTERN_TEXT_LIMIT in prompt
    assert "x" * (PATTERN_TEXT_LIMIT + 1) not in prompt
