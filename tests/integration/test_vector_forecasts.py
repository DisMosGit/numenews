"""The ``forecasts`` collection, over the in-memory engine.

Roadmap 3.6 stores one reading per day and reads it back by date; roadmap 5.4 is what depends on
that: a second call for the same day must answer from storage instead of re-running the agent.
"""

from __future__ import annotations

from datetime import date

import pytest
from qdrant_client.models import VectorParams

from numenews.models import Forecast
from numenews.vector import (
    FORECASTS_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    get_forecast,
    save_forecast,
)
from numenews.vector.payloads import forecast_point_id

pytestmark = pytest.mark.integration


def _forecast(
    *,
    day: date = date(2026, 9, 21),
    dominant_number: int = 7,
    master_active: bool = False,
    reading: str = "A day of quiet progress.",
) -> Forecast:
    """Return a valid forecast for one day."""
    return Forecast(
        date=day,
        dominant_number=dominant_number,
        master_active=master_active,
        patterns=(),
        forecast=reading,
        advice="Finish what is already open.",
        warnings=("avoid new commitments",),
    )


def test_saving_creates_a_768d_collection(vector_store: VectorStore) -> None:
    """A forecast is written in the same embedding space as the news it was built from."""
    save_forecast(vector_store, _forecast())

    info = vector_store.client.get_collection(FORECASTS_COLLECTION)

    assert isinstance(info.config.params.vectors, VectorParams)
    assert info.config.params.vectors.size == 768
    assert info.points_count == 1


def test_a_saved_forecast_comes_back_unchanged(vector_store: VectorStore) -> None:
    """The payload is lossless: warnings and advice included."""
    forecast = _forecast()

    save_forecast(vector_store, forecast)

    assert get_forecast(vector_store, forecast.date) == forecast


def test_an_unread_day_is_none_not_an_error(vector_store: VectorStore) -> None:
    """A day with no reading is a legitimate answer for phase 5's `build_forecast` to act on."""
    save_forecast(vector_store, _forecast(day=date(2026, 9, 21)))

    assert get_forecast(vector_store, date(2026, 9, 22)) is None


def test_reading_a_forecast_from_an_absent_collection_is_a_setup_error(
    vector_store: VectorStore,
) -> None:
    """No collection at all is different from an unread day, and says so."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        get_forecast(vector_store, date(2026, 9, 21))


def test_saving_the_same_day_twice_replaces_the_reading(vector_store: VectorStore) -> None:
    """One day has one reading; a re-run of the pipeline corrects it instead of duplicating it."""
    save_forecast(vector_store, _forecast(reading="first"))
    save_forecast(vector_store, _forecast(reading="second"))

    assert vector_store.client.count(FORECASTS_COLLECTION, exact=True).count == 1
    stored = get_forecast(vector_store, date(2026, 9, 21))
    assert stored is not None
    assert stored.forecast == "second"


def test_the_stored_payload_carries_the_indexed_fields(vector_store: VectorStore) -> None:
    """`date` and `dominant_number` are what a range query over past readings will use."""
    save_forecast(vector_store, _forecast(dominant_number=11, master_active=True))

    stored = vector_store.client.retrieve(
        FORECASTS_COLLECTION,
        [forecast_point_id(date(2026, 9, 21))],
        with_payload=True,
    )

    payload = stored[0].payload or {}
    assert payload["date"] == "2026-09-21T00:00:00Z"
    assert payload["dominant_number"] == 11
    assert payload["master_active"] is True
