"""The typed news filter's translation into a Qdrant filter.

The translation is pure, so the tests assert the generated conditions directly instead of searching
a collection: which fields become conditions, and — the part that is easy to get wrong — that a date
window is half-open on the upper bound. Qdrant parses the RFC 3339 bound into an aware ``datetime``
in its own model, so the assertions compare datetimes rather than the string they were built from.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from qdrant_client.models import FieldCondition, MatchValue

from numenews.models import NewsFilter
from numenews.vector.filters import build_news_filter


def _conditions(filters: NewsFilter | None) -> list[FieldCondition]:
    """Return the generated conditions, asserting that every one is a `FieldCondition`."""
    generated = build_news_filter(filters).must
    if generated is None:
        return []
    assert isinstance(generated, list)
    conditions = [item for item in generated if isinstance(item, FieldCondition)]
    assert len(conditions) == len(generated)
    return conditions


def _matched_value(condition: FieldCondition) -> object:
    """Return the value of a `MatchValue` condition, refusing any other match kind."""
    assert isinstance(condition.match, MatchValue)
    return condition.match.value


def test_no_filter_matches_everything() -> None:
    """`None` and an all-default model both ask for no narrowing at all."""
    assert build_news_filter(None).must is None
    assert build_news_filter(NewsFilter()).must is None


def test_a_numerology_value_becomes_a_match_condition() -> None:
    """Roadmap 3.8 filters on the reduced value of the item."""
    (condition,) = _conditions(NewsFilter(numerology_value=7))

    assert condition.key == "numerology_value"
    assert _matched_value(condition) == 7


def test_a_master_flag_becomes_a_boolean_match() -> None:
    """`master_number` is a derived boolean field, so it compares as one."""
    (condition,) = _conditions(NewsFilter(master_number=True))

    assert condition.key == "master_number"
    assert _matched_value(condition) is True


def test_a_source_becomes_a_keyword_match() -> None:
    """`source` holds the publisher, which the aggregator de-duplicates on."""
    (condition,) = _conditions(NewsFilter(source="example.com"))

    assert condition.key == "source"
    assert _matched_value(condition) == "example.com"


def test_a_date_window_is_half_open_on_the_upper_bound() -> None:
    """An inclusive `date_to` must include the items published during that day."""
    (condition,) = _conditions(NewsFilter(date_from=date(2026, 9, 15), date_to=date(2026, 9, 21)))

    assert condition.key == "date"
    assert condition.range is not None
    assert condition.range.gte == datetime(2026, 9, 15, tzinfo=UTC)
    assert condition.range.lt == datetime(2026, 9, 22, tzinfo=UTC)


def test_one_open_date_bound_is_enough() -> None:
    """A caller may ask for "since Monday" without naming an end."""
    (condition,) = _conditions(NewsFilter(date_from=date(2026, 9, 15)))

    assert condition.range is not None
    assert condition.range.gte == datetime(2026, 9, 15, tzinfo=UTC)
    assert condition.range.lt is None


def test_every_field_produces_one_condition() -> None:
    """Conditions are conjunctive: `must` asks Qdrant for all of them at once."""
    conditions = _conditions(
        NewsFilter(
            date_from=date(2026, 9, 15),
            date_to=date(2026, 9, 21),
            source="example.com",
            numerology_value=7,
            master_number=False,
        )
    )

    assert [condition.key for condition in conditions] == [
        "date",
        "source",
        "numerology_value",
        "master_number",
    ]
