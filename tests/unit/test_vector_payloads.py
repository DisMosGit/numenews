"""The payload rules of the vector layer, tested without a database.

Everything here is a pure function over a domain model, which is the point: the two rules that
would otherwise only show up as a broken index or a lost field on a real server — the RFC 3339
date and the dropped ``None`` — are pinned by a fast unit test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from numenews.models import Forecast, NewsId, NewsItem, NumberActivation, Pattern, PatternId
from numenews.vector.payloads import (
    activation_embedding_text,
    activation_from_payload,
    activation_payload,
    activation_point_id,
    forecast_embedding_text,
    forecast_from_payload,
    forecast_payload,
    forecast_point_id,
    news_embedding_text,
    news_from_payload,
    news_payload,
    news_point_id,
    pattern_embedding_text,
    pattern_from_payload,
    pattern_payload,
    pattern_point_id,
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


def _activation(**overrides: object) -> NumberActivation:
    """Return a number activation; ``overrides`` replace single fields."""
    fields: dict[str, object] = {
        "number": 7,
        "date": date(2026, 9, 21),
        "news_id": NewsId(uuid4()),
        "context": "seven markets closed higher",
    }
    fields.update(overrides)
    return NumberActivation.model_validate(fields)


def test_a_stored_activation_comes_back_unchanged() -> None:
    """`numbers` and `number_history` share one payload shape, so one round trip covers both."""
    activation = _activation()

    assert activation_from_payload(activation_payload(activation)) == activation


def test_an_activation_date_is_stored_as_the_start_of_its_utc_day() -> None:
    """`number_history` indexes `date` as a DATETIME, so the same RFC 3339 rule applies."""
    payload = activation_payload(_activation(date=date(2026, 9, 21)))

    assert payload["date"] == "2026-09-21T00:00:00Z"


def test_an_activation_is_embedded_by_its_context() -> None:
    """The snippet is what makes an activation findable by meaning."""
    assert activation_embedding_text(_activation()) == "seven markets closed higher"


def test_an_activation_without_a_context_is_embedded_by_its_number() -> None:
    """An empty string would give every context-less activation the same vector."""
    assert activation_embedding_text(_activation(context="")) == "7"


def test_an_activation_id_is_one_per_news_item_and_number() -> None:
    """Re-ingesting an article overwrites its activations instead of duplicating them."""
    news_id = NewsId(uuid4())
    first = _activation(news_id=news_id, number=7)
    same = _activation(news_id=news_id, number=7)
    other_number = _activation(news_id=news_id, number=11)
    other_news = _activation(news_id=NewsId(uuid4()), number=7)

    assert activation_point_id(first) == activation_point_id(same)
    assert len({activation_point_id(item) for item in (first, other_number, other_news)}) == 3


def _pattern(**overrides: object) -> Pattern:
    """Return a pattern; ``overrides`` replace single fields."""
    fields: dict[str, object] = {
        "id": PatternId(uuid4()),
        "type": "resonance",
        "numbers": (7,),
        "news_ids": (NewsId(uuid4()),),
        "strength": 0.5,
        "interpretation": "7 repeats across the week",
        "discovered_at": datetime(2026, 9, 21, 12, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return Pattern.model_validate(fields)


def test_a_stored_pattern_comes_back_unchanged() -> None:
    """Ids, news ids and the discovery timestamp all survive the payload round trip."""
    pattern = _pattern()

    assert pattern_from_payload(pattern_payload(pattern)) == pattern


def test_an_undiscovered_pattern_is_stored_without_a_timestamp() -> None:
    """`save_pattern` fills the timestamp; the payload builder does not invent one."""
    payload = pattern_payload(_pattern(discovered_at=None))

    assert "discovered_at" not in payload


def test_a_pattern_is_embedded_by_its_interpretation() -> None:
    """The interpretation is the pattern's meaning in words, which is what a query should match."""
    assert pattern_embedding_text(_pattern()) == "7 repeats across the week"


def test_a_pattern_without_an_interpretation_is_embedded_by_type_and_numbers() -> None:
    """An empty interpretation would give every such pattern the same vector."""
    assert pattern_embedding_text(_pattern(interpretation="  ")) == "resonance 7"


def test_a_pattern_point_id_is_its_pattern_id() -> None:
    """Storing the same pattern twice overwrites the point instead of adding a twin."""
    pattern = _pattern()

    assert pattern_point_id(pattern) == str(pattern.id.root)


def _forecast(**overrides: object) -> Forecast:
    """Return a forecast; ``overrides`` replace single fields."""
    fields: dict[str, object] = {
        "date": date(2026, 9, 21),
        "dominant_number": 7,
        "master_active": False,
        "patterns": (),
        "forecast": "A day of quiet progress.",
        "advice": "Finish what is already open.",
        "warnings": ("avoid new commitments",),
    }
    fields.update(overrides)
    return Forecast.model_validate(fields)


def test_a_stored_forecast_comes_back_unchanged() -> None:
    """The nested patterns and the warnings survive the payload round trip too."""
    forecast = _forecast(patterns=(_pattern(),))

    assert forecast_from_payload(forecast_payload(forecast)) == forecast


def test_a_forecast_date_is_stored_as_the_start_of_its_utc_day() -> None:
    """`forecasts.date` is a DATETIME-indexed payload field, so it follows the same rule."""
    payload = forecast_payload(_forecast(date=date(2026, 9, 21)))

    assert payload["date"] == "2026-09-21T00:00:00Z"


def test_a_forecast_is_embedded_by_its_reading_and_advice() -> None:
    """The interpretable part is what a later similarity query should match."""
    assert forecast_embedding_text(_forecast()) == (
        "A day of quiet progress.\n\nFinish what is already open."
    )


def test_a_forecast_without_text_is_embedded_by_its_dominant_number() -> None:
    """An empty reading still has to map to something rather than to an empty string."""
    assert forecast_embedding_text(_forecast(forecast="", advice="", warnings=())) == "7"


def test_one_forecast_point_id_per_day() -> None:
    """A day has exactly one reading, so the date is the key and a re-save overwrites."""
    assert forecast_point_id(date(2026, 9, 21)) == forecast_point_id(date(2026, 9, 21))
    assert forecast_point_id(date(2026, 9, 21)) != forecast_point_id(date(2026, 9, 22))
