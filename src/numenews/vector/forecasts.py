"""The ``forecasts`` collection: one day's reading, kept so the next run does not redo it.

Phase 5.4 wants ``build_forecast(date)`` to answer from storage when the day has already been read,
which is why a day's forecast is stored under a date-derived point id: the lookup is exact and
idempotent, while the ``date``/``dominant_number`` payload indexes stay available for the range
queries a CLI or a digest will need.

The vector across the reading and the advice is what would let a later run ask "was there a day like
this"; the numbers themselves are filterable, so they are not part of the embedded text.
"""

from __future__ import annotations

from datetime import date

from qdrant_client.models import PointStruct

from numenews.logging import get_logger
from numenews.models import Forecast
from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    FORECASTS_COLLECTION,
    create_forecasts_collection,
    require_collection,
)
from numenews.vector.errors import VectorStoreError
from numenews.vector.payloads import (
    forecast_embedding_text,
    forecast_from_payload,
    forecast_payload,
    forecast_point_id,
)

logger = get_logger(__name__)


def save_forecast(store: VectorStore, forecast: Forecast) -> None:
    """Embed and store one day's forecast under its date.

    Args:
        store: The connection and the 768d embedder.
        forecast: The reading to persist; its ``date`` selects the point, so a second save for the
            same day replaces the first.
    """
    create_forecasts_collection(store.client)
    vector = store.base.embed([forecast_embedding_text(forecast)])[0]
    store.client.upsert(
        FORECASTS_COLLECTION,
        [
            PointStruct(
                id=forecast_point_id(forecast.date),
                vector=vector,
                payload=forecast_payload(forecast),
            )
        ],
        wait=True,
    )
    logger.info(
        "vector.forecast.saved",
        date=forecast.date.isoformat(),
        dominant_number=forecast.dominant_number,
    )


def get_forecast(store: VectorStore, day: date) -> Forecast | None:
    """Return the forecast stored for ``day``, or ``None`` when the day has not been read yet.

    Args:
        store: The connection and the 768d embedder.
        day: The calendar day whose reading is wanted.

    Raises:
        CollectionNotFoundError: when the ``forecasts`` collection was never created — the caller
            asked for history in a store that has none, which is different from an unread day.
        VectorStoreError: when the stored point has no payload, which would mean it was written by
            something other than :func:`save_forecast`.

    Returns:
        The stored reading, or ``None``.
    """
    require_collection(store.client, FORECASTS_COLLECTION)
    records = store.client.retrieve(
        FORECASTS_COLLECTION,
        [forecast_point_id(day)],
        with_payload=True,
    )
    if not records:
        return None
    payload = records[0].payload
    if payload is None:
        raise VectorStoreError(f"stored forecast for {day.isoformat()} has no payload")
    return forecast_from_payload(payload)
