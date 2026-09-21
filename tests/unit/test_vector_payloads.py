"""The payload rules of the vector layer, tested without a database.

Everything here is a pure function over a domain model, which is the point: the two rules that
would otherwise only show up as a broken index or a lost field on a real server — the RFC 3339
date and the dropped ``None`` — are pinned by a fast unit test.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from numenews.models import NewsId, NewsItem
from numenews.vector.payloads import (
    news_embedding_text,
    news_from_payload,
    news_payload,
    news_point_id,
)


def _item(**overrides: object) -> NewsItem:
    """Return a valid news item; ``overrides`` replace single fields."""
    fields: dict[str, object] = {
        "id": NewsId(uuid4()),
        "title": "Sun rises",
        "text": "The sun rises over the city.",
        "source": "gdelt",
        "date": date(2026, 9, 21),
        "url": "https://example.test/sun",
    }
    fields.update(overrides)
    return NewsItem.model_validate(fields)


def test_a_stored_item_comes_back_unchanged() -> None:
    """The payload keeps every field of the model, ids and numbers included."""
    item = _item(numbers=(7, 11), numerology_value=7)

    assert news_from_payload(news_payload(item)) == item


def test_a_date_is_stored_as_the_start_of_its_utc_day() -> None:
    """A DATETIME index needs a timestamp, so a calendar day is stored as its RFC 3339 start."""
    payload = news_payload(_item(date=date(2026, 9, 21)))

    assert payload["date"] == "2026-09-21T00:00:00Z"


def test_an_uncomputed_number_is_absent_instead_of_null() -> None:
    """`None` means "not computed yet" and must not become an indexed null value."""
    payload = news_payload(_item())

    assert "numerology_value" not in payload
    assert "master_number" not in payload


def test_the_master_flag_is_derived_from_the_reduced_value() -> None:
    """`master_number` is a filterable restatement of `numerology_value in {11, 22, 33}`."""
    assert news_payload(_item(numerology_value=11))["master_number"] is True
    assert news_payload(_item(numerology_value=22))["master_number"] is True
    assert news_payload(_item(numerology_value=33))["master_number"] is True
    assert news_payload(_item(numerology_value=7))["master_number"] is False


def test_the_embedding_text_is_the_headline_and_the_body() -> None:
    """The text that goes to the model is what a reader would read, minus the boilerplate."""
    assert news_embedding_text(_item()) == "Sun rises\n\nThe sun rises over the city."


def test_an_item_without_text_falls_back_to_its_url() -> None:
    """Two feeds ship blank descriptions; an empty string would map every such item to one point."""
    item = _item(title="", text="", url="https://example.test/only-a-link")

    assert news_embedding_text(item) == "https://example.test/only-a-link"


def test_the_point_id_is_the_news_id() -> None:
    """A deterministic id is what makes re-ingesting the same article overwrite, not duplicate."""
    item = _item()

    assert news_point_id(item) == str(item.id.root)
    assert news_point_id(item) == news_point_id(item)
