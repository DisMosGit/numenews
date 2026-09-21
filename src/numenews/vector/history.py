"""The ``number_history`` collection: the exact log of when a number was activated.

This is the project's long-term memory (``ROADMAP.md``, phase 8): every ingest appends the numbers
it found with the day they were published, and a forecast reads the window back. The collection has
no vectors — a question about history is exact ("which 11s since Monday?"), and the semantic
counterpart lives in ``numbers``.

Writes are idempotent: the point id is derived from the news item and the number, so re-ingesting an
article overwrites its activations rather than appending duplicates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from qdrant_client.models import DatetimeRange, FieldCondition, Filter, MatchValue, PointStruct

from numenews.logging import get_logger
from numenews.models import NumberActivation
from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    NUMBER_HISTORY_COLLECTION,
    create_number_history_collection,
    require_collection,
)
from numenews.vector.payloads import (
    activation_from_payload,
    activation_payload,
    activation_point_id,
    day_start,
)

logger = get_logger(__name__)

#: How many points one scroll page asks for. The read paginates until Qdrant stops handing back an
#: offset, so this only bounds the round trips.
_SCROLL_PAGE = 256


def record_activation(store: VectorStore, activation: NumberActivation) -> None:
    """Append one activation to the history, overwriting the same pair if it is already there.

    Args:
        store: The connection. The history has no vectors, so neither embedder is used.
        activation: What to remember — the number, the day and the snippet it was read in.
    """
    create_number_history_collection(store.client)
    store.client.upsert(
        NUMBER_HISTORY_COLLECTION,
        [
            PointStruct(
                id=activation_point_id(activation),
                vector={},
                payload=activation_payload(activation),
            )
        ],
        wait=True,
    )
    logger.info(
        "vector.history.recorded",
        number=activation.number,
        date=activation.date.isoformat(),
    )


def get_history(
    store: VectorStore,
    number: int,
    days: int,
    *,
    today: date | None = None,
) -> list[NumberActivation]:
    """Return the activations of ``number`` inside the last ``days`` days, newest first.

    The window ends today and includes it: ``days=1`` is today, ``days=7`` is today and the six days
    before it. Ties on a day are ordered by news id, so the result is stable between identical runs.

    Args:
        store: The connection. The history has no vectors, so neither embedder is used.
        number: Which number's activations to read.
        days: Length of the window in calendar days.
        today: The end of the window. Defaults to the current UTC day; tests and replayed runs pass
            it explicitly so the result depends on the data, not on the clock (as in 1.6).

    Raises:
        ValueError: when ``days`` is less than one — a window with no days is a call-site bug.
        CollectionNotFoundError: when the ``number_history`` collection was never created.

    Returns:
        The activations, newest first.
    """
    if days < 1:
        raise ValueError("history window must be at least one day")
    require_collection(store.client, NUMBER_HISTORY_COLLECTION)
    end = today if today is not None else datetime.now(UTC).date()
    scroll_filter = Filter(
        must=[
            FieldCondition(key="number", match=MatchValue(value=number)),
            FieldCondition(
                key="date",
                range=DatetimeRange(
                    gte=day_start(end - timedelta(days=days - 1)),
                    lt=day_start(end + timedelta(days=1)),
                ),
            ),
        ]
    )
    activations: list[NumberActivation] = []
    offset: int | str | UUID | None = None
    while True:
        records, offset = store.client.scroll(
            NUMBER_HISTORY_COLLECTION,
            scroll_filter=scroll_filter,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=True,
        )
        activations.extend(activation_from_payload(record.payload or {}) for record in records)
        if offset is None:
            break
    activations.sort(key=lambda item: (item.date, str(item.news_id.root)), reverse=True)
    logger.debug("vector.history.read", number=number, days=days, activations=len(activations))
    return activations
