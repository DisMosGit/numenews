"""The wire schemas: what a client may send, and how it becomes a domain model (ROADMAP 6.x).

The domain models are strict, so these DTOs are the only place JSON shapes are accepted. The tests
assert both halves: a valid payload converts to the frozen domain model field by field, and the
rules the domain enforces (reversed ranges, reversed dates, a strength outside the unit interval)
are refused here rather than later, so ``to_domain`` cannot fail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import get_args
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from numenews.mcp.schemas import (
    CollectionName,
    CollectionQueryResult,
    DateRangeInput,
    NewsFilterInput,
    PatternInput,
)
from numenews.models import (
    DateRange,
    NewsFilter,
    NewsId,
    NewsItem,
    Pattern,
    PatternId,
    PatternType,
)

NEWS_ID = UUID("123e4567-e89b-12d3-a456-426614174000")
PATTERN_ID = UUID("8f14e45f-ceea-467a-9a4f-52b3b7a0b1c2")
WHEN = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def test_collection_name_lists_exactly_the_searchable_collections() -> None:
    """Phase 3 built semantic read paths for news and patterns only; the Literal must say so."""
    assert get_args(CollectionName.__value__) == ("news", "patterns")


def test_a_date_range_input_becomes_the_domain_range() -> None:
    """A one-line conversion, but the domain model is what the layers below receive."""
    converted = DateRangeInput(start=date(2026, 9, 15), end=date(2026, 9, 21)).to_domain()

    assert converted == DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))


def test_a_reversed_date_range_input_is_refused_at_the_wire() -> None:
    """The domain rule is mirrored, so the error names the argument the model passed."""
    with pytest.raises(ValidationError, match=r"date_range\.start"):
        DateRangeInput(start=date(2026, 9, 21), end=date(2026, 9, 15))


def test_an_empty_news_filter_input_constrains_nothing() -> None:
    """Every field is optional; the all-default filter matches everything, as NewsFilter does."""
    assert NewsFilterInput().to_domain() == NewsFilter()


def test_a_full_news_filter_input_becomes_the_domain_filter() -> None:
    """Each field survives the conversion unchanged."""
    converted = NewsFilterInput(
        date_from=date(2026, 9, 15),
        date_to=date(2026, 9, 21),
        source="example.com",
        numerology_value=7,
        master_number=False,
    ).to_domain()

    assert converted == NewsFilter(
        date_from=date(2026, 9, 15),
        date_to=date(2026, 9, 21),
        source="example.com",
        numerology_value=7,
        master_number=False,
    )


def test_a_reversed_news_filter_input_is_refused_at_the_wire() -> None:
    """The reversed-date rule of NewsFilter is mirrored on the DTO."""
    with pytest.raises(ValidationError, match=r"filters\.date_from"):
        NewsFilterInput(date_from=date(2026, 9, 21), date_to=date(2026, 9, 15))


def test_a_pattern_input_becomes_the_domain_pattern() -> None:
    """JSON arrays become tuples and UUID strings become the id wrappers."""
    draft = PatternInput(
        id=PATTERN_ID,
        type="repetition",
        numbers=[11, 7],
        news_ids=[NEWS_ID],
        strength=0.9,
        interpretation="Число 11 повторяется.",
        discovered_at=WHEN,
    )

    assert draft.to_domain() == Pattern(
        id=PatternId(PATTERN_ID),
        type="repetition",
        numbers=(11, 7),
        news_ids=(NewsId(NEWS_ID),),
        strength=0.9,
        interpretation="Число 11 повторяется.",
        discovered_at=WHEN,
    )


def test_a_pattern_input_without_a_timestamp_is_allowed() -> None:
    """``save_pattern`` stamps an unstamped pattern, so the wire may omit it."""
    draft = PatternInput(
        id=PATTERN_ID,
        type="master",
        numbers=[11],
        news_ids=[],
        strength=0.5,
        interpretation="Одиннадцать.",
    )

    assert draft.to_domain().discovered_at is None


def test_a_strength_outside_the_unit_interval_is_refused_at_the_wire() -> None:
    """Confidence is bounded where the model can see the error, not inside the vector layer."""
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        PatternInput(
            id=PATTERN_ID,
            type="resonance",
            numbers=[7],
            news_ids=[],
            strength=1.5,
            interpretation="Слишком уверенно.",
        )


def test_an_unknown_pattern_type_is_refused_at_the_wire() -> None:
    """The set of pattern kinds is the model's Literal, so a typo is a tool error."""
    with pytest.raises(ValidationError, match="resonance"):
        PatternInput(
            id=PATTERN_ID,
            type="mystery",  # type: ignore[arg-type]  # the wire is where a bad literal must fail
            numbers=[7],
            news_ids=[],
            strength=0.4,
            interpretation="Неизвестный тип.",
        )


def test_a_query_result_holds_the_typed_entities() -> None:
    """The result replaces the roadmap's ``list[dict]`` with the two searchable entities."""
    item = NewsItem(
        id=NewsId(NEWS_ID),
        title="11th hour deal",
        text="a body",
        source="example.com",
        date=date(2026, 9, 21),
        url="https://example.test/a",
    )
    result = CollectionQueryResult(collection="news", query="deal", items=(item,))

    assert result.items == (item,)
    assert result.model_dump()["items"][0]["title"] == "11th hour deal"


def test_a_query_result_is_frozen() -> None:
    """A boundary value never changes after it was built."""
    result = CollectionQueryResult(collection="patterns", query="resonance", items=())

    with pytest.raises(ValidationError):
        result.query = "other"  # type: ignore[misc]  # frozen models refuse assignment


def test_pattern_type_is_reused_from_the_domain_layer() -> None:
    """The DTO must not define a second set of pattern kinds: it annotates the domain alias."""
    assert get_args(PatternType.__value__) == (
        "resonance",
        "repetition",
        "master",
        "symbol",
        "hidden",
    )


def test_a_pattern_input_keeps_more_than_one_news_id() -> None:
    """A connection can cite several items; order is preserved."""
    other = uuid4()
    draft = PatternInput(
        id=PATTERN_ID,
        type="symbol",
        numbers=[11],
        news_ids=[NEWS_ID, other],
        strength=0.7,
        interpretation="Символ повторяется.",
    )

    assert draft.to_domain().news_ids == (NewsId(NEWS_ID), NewsId(other))
