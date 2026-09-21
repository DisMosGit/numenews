"""Tests for the Pydantic v2 domain models.

The models are the shared vocabulary of every layer, so two properties matter more than the field
lists: validation is strict (nothing is coerced at a boundary) and instances are frozen (a value
cannot change after it crossed one).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from numenews.models import (
    DateRange,
    DominantResult,
    ExtractedNumbers,
    Forecast,
    ForecastId,
    MasterCheckResult,
    NewsFilter,
    NewsId,
    NewsItem,
    NumberActivation,
    Pattern,
    PatternId,
    Topic,
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


def test_dominant_result_records_the_evidence_behind_the_number() -> None:
    """A reader can tell a day eleven items agree on from a day one item was all there was."""
    result = DominantResult(dominant_number=11, is_master=True, votes=3, considered=5)

    assert result.dominant_number == 11
    assert result.is_master is True
    assert result.votes == 3
    assert result.considered == 5


def test_dominant_result_is_frozen_and_strict() -> None:
    """The result crosses the CLI boundary, so it validates like every other model."""
    with pytest.raises(ValidationError):
        DominantResult.model_validate(
            {"dominant_number": "11", "is_master": True, "votes": 1, "considered": 1}
        )

    result = DominantResult(dominant_number=7, is_master=False, votes=1, considered=1)

    with pytest.raises(ValidationError):
        result.votes = 2  # type: ignore[misc]  # frozen model, mypy cannot see it


def test_topic_trims_surrounding_whitespace() -> None:
    """A padded query means the same as a clean one, so it is normalised, not rejected."""
    assert Topic(query="  politics  ").query == "politics"


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_topic_rejects_a_blank_query(blank: str) -> None:
    """A blank query would ask for the firehose, not for news about something."""
    with pytest.raises(ValidationError):
        Topic(query=blank)


def test_topic_is_frozen_and_strict() -> None:
    """The query is a string and cannot be replaced after validation."""
    with pytest.raises(ValidationError):
        Topic.model_validate({"query": 7})

    topic = Topic(query="politics")

    with pytest.raises(ValidationError):
        topic.query = "economy"  # type: ignore[misc]  # frozen model, mypy cannot see it


def test_date_range_accepts_a_single_day() -> None:
    """`start == end` is a valid one-day range."""
    day = date(2026, 9, 21)

    assert DateRange(start=day, end=day).start == day


def test_date_range_rejects_a_reversed_range() -> None:
    """A start after the end is refused at the boundary, not sorted silently."""
    with pytest.raises(ValidationError):
        DateRange(start=date(2026, 9, 22), end=date(2026, 9, 21))


def test_date_range_is_strict_in_python_mode_and_parses_json() -> None:
    """A Python `str` is not a `date`, but a JSON payload keeps working (it has no date type)."""
    with pytest.raises(ValidationError):
        DateRange.model_validate({"start": "2026-09-21", "end": "2026-09-22"})

    restored = DateRange.model_validate_json('{"start": "2026-09-21", "end": "2026-09-22"}')

    assert restored == DateRange(start=date(2026, 9, 21), end=date(2026, 9, 22))


def test_news_filter_defaults_to_no_narrowing() -> None:
    """An all-default filter constrains nothing: `None` on every field means "any"."""
    filters = NewsFilter()

    assert filters.date_from is None
    assert filters.date_to is None
    assert filters.source is None
    assert filters.numerology_value is None
    assert filters.master_number is None


def test_news_filter_rejects_a_reversed_window() -> None:
    """A window whose start lies after its end is refused, as in `DateRange`."""
    with pytest.raises(ValidationError):
        NewsFilter(date_from=date(2026, 9, 22), date_to=date(2026, 9, 21))

    one_day = date(2026, 9, 21)

    assert NewsFilter(date_from=one_day, date_to=one_day).date_from == one_day


def test_news_filter_is_frozen_and_strict() -> None:
    """A filter is validated once and never coerced or mutated afterwards."""
    with pytest.raises(ValidationError):
        NewsFilter.model_validate({"numerology_value": "7"})

    filters = NewsFilter(numerology_value=7)

    with pytest.raises(ValidationError):
        filters.numerology_value = 11  # type: ignore[misc]  # frozen model, mypy cannot see it


def test_a_pattern_is_undiscovered_until_it_is_saved() -> None:
    """The agent describes a connection; `save_pattern` is what gives it a discovery time."""
    pattern = Pattern(
        id=PatternId(uuid4()),
        type="resonance",
        numbers=(7,),
        news_ids=(),
        strength=0.5,
        interpretation="7 repeats",
    )

    assert pattern.discovered_at is None


def test_a_pattern_keeps_the_discovery_time_it_was_given() -> None:
    """A given timestamp survives validation and a JSON round trip, so storage cannot reset it."""
    discovered = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    pattern = Pattern(
        id=PatternId(uuid4()),
        type="resonance",
        numbers=(7,),
        news_ids=(),
        strength=0.5,
        interpretation="7 repeats",
        discovered_at=discovered,
    )

    assert pattern.discovered_at == discovered
    assert Pattern.model_validate_json(pattern.model_dump_json()).discovered_at == discovered
