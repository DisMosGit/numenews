"""Tests for the summarizer (ROADMAP 5.5) and its prompt.

The model contributes the prose only. The period of the digest and the numbers it rests on are facts
about the items, so those are asserted to come from here rather than from a model answer; the model
itself is a ``FunctionModel`` double, as in every other agent test.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic_ai.exceptions import ModelAPIError

from numenews.agents import AgentExecutionError, DigestDraft, SummarizeAgent
from numenews.agents.prompts import (
    DIGEST_ITEM_LIMIT,
    SUMMARIZE_FEW_SHOT,
    SUMMARIZE_INSTRUCTIONS,
    SUMMARIZE_RULES,
    build_digest_prompt,
)
from numenews.agents.summarize import digest_of
from numenews.models import Digest, NewsId, NewsItem

from .agent_fakes import answering, failing, recording, user_text

SUMMARY = "Период прошёл под числом 11."


def _item(
    *,
    day: date = date(2026, 9, 1),
    value: int | None = 11,
    title: str = "Eleven ministers resign",
    text: str = "Eleven ministers resigned over the budget.",
) -> NewsItem:
    """Return a news item with a deterministic id and a known reduced value."""
    url = f"https://example.com/{title}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=title,
        text=text,
        source="example.com",
        date=day,
        url=url,
        numbers=(value,) if value is not None else (),
        numerology_value=value,
    )


async def test_summarize_returns_a_digest_built_from_the_items() -> None:
    """The period and the numbers are the caller's facts; only the prose comes from the model."""
    news = [
        _item(day=date(2026, 9, 1), value=11, title="first"),
        _item(day=date(2026, 9, 7), value=7, title="second"),
    ]
    agent = SummarizeAgent(answering(summary=SUMMARY))

    digest = await agent.summarize(news)

    assert digest == Digest(
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 7),
        summary=SUMMARY,
        numbers=(11, 7),
    )


async def test_digest_numbers_skip_an_item_that_was_never_computed() -> None:
    """A `None` value means "not computed" and must not become part of the period's reading."""
    news = [
        _item(day=date(2026, 9, 1), value=11, title="a"),
        _item(day=date(2026, 9, 2), value=7, title="b"),
        _item(day=date(2026, 9, 3), value=7, title="c"),
    ]

    digest = digest_of(news, SUMMARY)

    assert digest.numbers == (11, 7)


async def test_summarize_refuses_to_compress_nothing() -> None:
    """An empty period has no range to label; the caller decides what an idle stretch means."""
    agent = SummarizeAgent(answering(summary=SUMMARY))

    with pytest.raises(ValueError, match="at least one news item"):
        await agent.summarize([])


async def test_a_blank_summary_is_rejected() -> None:
    """A digest that says nothing is a failed run to retry, not a stored memory."""
    agent = SummarizeAgent(answering(summary=""))

    with pytest.raises(AgentExecutionError, match="summarize_news"):
        await agent.summarize([_item()])


async def test_a_failing_model_is_reported() -> None:
    """A broken provider is surfaced, so the pipeline can retry or fail loudly."""
    agent = SummarizeAgent(failing(ModelAPIError(model_name="test", message="boom")))

    with pytest.raises(AgentExecutionError, match="summarize_news"):
        await agent.summarize([_item()])


async def test_the_prompt_carries_the_period_and_the_items() -> None:
    """The model is told what it is compressing and what each item contributed."""
    model, recorder = recording(summary=SUMMARY)

    await SummarizeAgent(model).summarize(
        [
            _item(day=date(2026, 9, 1), title="first"),
            _item(day=date(2026, 9, 7), title="second"),
        ]
    )

    prompt = user_text(recorder.calls[0])
    assert "Period: 2026-09-01 to 2026-09-07" in prompt
    assert "Items to summarise: 2" in prompt
    assert "numerology_value: 11" in prompt


def test_the_prompt_is_ordered_by_day_and_capped() -> None:
    """A busy month cannot build a prompt of unbounded size, and the oldest days come first."""
    news = [_item(day=date(2026, 9, day), title=f"story-{day}") for day in range(20, 0, -1)]

    prompt = build_digest_prompt(news)

    assert f"Items to summarise: {len(news)}" in prompt
    assert "Period: 2026-09-01 to 2026-09-20" in prompt
    assert prompt.index("story-1") < prompt.index("story-20")


def test_a_period_longer_than_the_limit_is_cut() -> None:
    """`DIGEST_ITEM_LIMIT` bounds one prompt; the summary of a huge period is one call, not many."""
    news = [
        _item(day=date(2026, 9, 1), title=f"story-{index}")
        for index in range(DIGEST_ITEM_LIMIT + 5)
    ]

    prompt = build_digest_prompt(news)

    assert f"Items to summarise: {DIGEST_ITEM_LIMIT}" in prompt
    assert f"story-{DIGEST_ITEM_LIMIT}" not in prompt


def test_an_empty_prompt_says_so() -> None:
    """The function is total: an empty list renders a period of nothing rather than crashing."""
    assert build_digest_prompt([]) == "Period: (no news)\nItems to summarise: 0"


def test_the_instructions_are_the_documented_blocks() -> None:
    """A prompt change is a deliberate three-file change (phase 4.5); this is the literal."""
    assert f"{SUMMARIZE_RULES}\n\n{SUMMARIZE_FEW_SHOT}" == SUMMARIZE_INSTRUCTIONS
    assert SUMMARIZE_RULES in SUMMARIZE_INSTRUCTIONS


def test_the_draft_rejects_an_empty_summary() -> None:
    """The schema, not the prompt, is what guarantees the layer never stores a blank memory."""
    with pytest.raises(ValueError, match="summary"):
        DigestDraft(summary="")
