"""Tests for the Pydantic v2 domain models.

The models are the shared vocabulary of every layer, so two properties matter more than the field
lists: validation is strict (nothing is coerced at a boundary) and instances are frozen (a value
cannot change after it crossed one).
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from numenews.models import (
    ExtractedNumbers,
    Forecast,
    ForecastId,
    MasterCheckResult,
    NewsId,
    NewsItem,
    NumberActivation,
    Pattern,
    PatternId,
)


def _news_item_payload() -> dict[str, object]:
    """Return a valid `NewsItem` payload; each call gets a fresh id."""
    return {
        "id": NewsId(uuid4()),
        "title": "Sun rises",
        "text": "The sun rises over the city.",
        "source": "gdelt",
        "date": date(2026, 9, 21),
        "url": "https://example.com/sun",
    }


def _news_item() -> NewsItem:
    """Return one valid news item."""
    return NewsItem.model_validate(_news_item_payload())


def test_news_item_defaults_to_uncomputed_numbers() -> None:
    """A freshly fetched item carries no numbers yet, and `None` means "not computed"."""
    item = _news_item()

    assert item.numbers == ()
    assert item.numerology_value is None


def test_models_are_frozen() -> None:
    """Assigning to a field of a validated model raises instead of mutating it."""
    item = _news_item()

    with pytest.raises(ValidationError):
        item.title = "changed"  # type: ignore[misc]  # frozen model, mypy cannot see it


def test_models_are_hashable() -> None:
    """Frozen models can be put in a set or used as a dict key."""
    assert len({_news_item(), _news_item()}) == 2
    assert len({PatternId(uuid4()) for _ in range(2)}) == 2


def test_strict_validation_rejects_coercion() -> None:
    """Nothing is coerced across a boundary: str is not UUID, list is not tuple, "1" is not 1."""
    payload = _news_item_payload()

    with pytest.raises(ValidationError):
        NewsItem.model_validate(
            {**payload, "id": str(uuid4()), "numbers": [1, 2], "numerology_value": "7"}
        )

    with pytest.raises(ValidationError):
        NewsItem.model_validate({**payload, "numbers": ("1",)})


def test_strict_validation_accepts_a_json_payload() -> None:
    """JSON strings remain valid input: a payload read back from Qdrant uses this path."""
    item = _news_item()

    restored = NewsItem.model_validate_json(item.model_dump_json())

    assert restored == item
    assert isinstance(restored.id.root, UUID)


def test_news_id_serializes_as_a_bare_uuid_string() -> None:
    """An id wrapper is transparent in JSON and does not wrap the value in an object."""
    serialized = NewsId(UUID(int=0)).model_dump_json()

    assert json.loads(serialized) == "00000000-0000-0000-0000-000000000000"


def test_news_id_rejects_a_plain_string() -> None:
    """In Python mode the wrapper only accepts a `UUID` instance."""
    with pytest.raises(ValidationError):
        NewsId.model_validate(str(uuid4()))


def test_forecast_id_wrapper_exists() -> None:
    """`ForecastId` mirrors the other id wrappers."""
    assert isinstance(ForecastId(uuid4()).root, UUID)


def test_pattern_strength_is_bounded() -> None:
    """A confidence outside `[0, 1]` is rejected at the boundary, not in the agent."""
    pattern_id = PatternId(uuid4())

    def build(strength: float) -> Pattern:
        return Pattern(
            id=pattern_id,
            type="resonance",
            numbers=(11, 22),
            news_ids=(NewsId(uuid4()),),
            strength=strength,
            interpretation="11 and 22 resonate",
        )

    assert build(0.0).strength == 0.0
    assert build(1.0).strength == 1.0
    assert build(1).strength == 1.0  # strict float still accepts an int

    for invalid in (-0.1, 1.5):
        with pytest.raises(ValidationError):
            build(invalid)


def test_pattern_type_is_closed() -> None:
    """Only the declared pattern kinds validate."""
    payload: dict[str, object] = {
        "id": PatternId(uuid4()),
        "numbers": (),
        "news_ids": (),
        "strength": 0.5,
        "interpretation": "unknown kind",
    }

    with pytest.raises(ValidationError):
        Pattern.model_validate({**payload, "type": "astrology"})


def test_forecast_defaults_to_no_patterns_or_warnings() -> None:
    """A reading can exist before patterns were attached."""
    forecast = Forecast(
        date=date(2026, 9, 21),
        dominant_number=7,
        master_active=False,
        forecast="A quiet day.",
        advice="Finish what is open.",
    )

    assert forecast.patterns == ()
    assert forecast.warnings == ()


def test_extracted_numbers_defaults_to_empty() -> None:
    """An extraction that found nothing is still a valid result."""
    extracted = ExtractedNumbers()

    assert extracted.numbers == ()
    assert extracted.sources == ()
    assert extracted.symbols == ()


def test_number_activation_requires_the_news_it_came_from() -> None:
    """An activation without provenance would be unusable as memory."""
    activation = NumberActivation(
        number=11,
        date=date(2026, 9, 21),
        news_id=NewsId(uuid4()),
        context="the 11th hour",
    )

    assert activation.number == 11
    assert activation.context == "the 11th hour"


def test_master_check_result_fields() -> None:
    """The check result keeps distinct masters and the occurrence count apart."""
    result = MasterCheckResult(has_master=True, master_numbers=(11, 22), count=3)

    assert result.has_master is True
    assert result.master_numbers == (11, 22)
    assert result.count == 3
