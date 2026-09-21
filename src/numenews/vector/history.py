"""The ``number_history`` collection: the exact log of when a number was activated.

This is the project's long-term memory (``ROADMAP.md``, phase 8): every ingest appends the numbers
it found with the day they were published, and a forecast reads the window back. The collection has
no vectors — a question about history is exact ("which 11s since Monday?"), and the semantic
counterpart lives in ``numbers``. A read returns the rows (:func:`get_history`,
:func:`get_activations`), and :func:`activation_frequency` folds them into the per-day series.

Writes are idempotent: the point id is derived from the news item and the number, so re-ingesting an
article overwrites its activations rather than appending duplicates.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from qdrant_client.models import (
    Condition,
    DatetimeRange,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
)

from numenews.logging import get_logger
from numenews.models import DayActivationCount, NumberActivation
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
        activation: What to remember — the number, the day, the item it was read in, the snippet
            around it and the item's reduced value (phase 8.1).
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
    activations = _scroll(store, _window_filter(days, today, number=number))
    activations.sort(key=_newest_first, reverse=True)
    logger.debug("vector.history.read", number=number, days=days, activations=len(activations))
    return activations


def get_activations(
    store: VectorStore,
    days: int,
    *,
    today: date | None = None,
) -> list[NumberActivation]:
    """Return every activation inside the last ``days`` days, newest first, whatever the number.

    This is the read the forecast step needs (roadmap 5.4): the day's reading should draw on all the
    numbers the recent news activated, not on one of them. ``get_history`` stays the question with a
    subject ("when was 11 active"), this one is the question without ("what was active").

    Args:
        store: The connection. The history has no vectors, so neither embedder is used.
        days: Length of the window in calendar days, ending today and including it.
        today: The end of the window. Defaults to the current UTC day.

    Raises:
        ValueError: when ``days`` is less than one.
        CollectionNotFoundError: when the ``number_history`` collection was never created.

    Returns:
        The activations, newest first.
    """
    if days < 1:
        raise ValueError("history window must be at least one day")
    require_collection(store.client, NUMBER_HISTORY_COLLECTION)
    activations = _scroll(store, _window_filter(days, today))
    activations.sort(key=_newest_first, reverse=True)
    logger.debug("vector.history.window_read", days=days, activations=len(activations))
    return activations


def activation_frequency(activations: Sequence[NumberActivation]) -> tuple[DayActivationCount, ...]:
    """Return how many activations fall on each day, newest day first.

    A history read answers "when was 11 active" with one row per news item; this folds the same rows
    into the time series the roadmap 8.2 aggregation asks for, which is what a reader wants beside
    the rows themselves. The order matches :func:`get_history` — newest first — so the report and
    its series read the same way. Rows are counted, not distinct numbers: two articles that both
    state 11 make one day with ``count=2``.

    Args:
        activations: The rows a read returned, in any order.

    Returns:
        One bucket per day present, newest first; an empty input gives an empty tuple.
    """
    counts = Counter(activation.date for activation in activations)
    return tuple(
        DayActivationCount(date=day, count=count)
        for day, count in sorted(counts.items(), reverse=True)
    )


def _window_filter(
    days: int,
    today: date | None,
    *,
    number: int | None = None,
) -> Filter:
    """Return the payload filter of a window ending today, optionally for one number."""
    end = today if today is not None else datetime.now(UTC).date()
    conditions: list[Condition] = [
        FieldCondition(
            key="date",
            range=DatetimeRange(
                gte=day_start(end - timedelta(days=days - 1)),
                lt=day_start(end + timedelta(days=1)),
            ),
        )
    ]
    if number is not None:
        conditions.insert(0, FieldCondition(key="number", match=MatchValue(value=number)))
    return Filter(must=conditions)


def _newest_first(activation: NumberActivation) -> tuple[date, str]:
    """Return the key that orders activations newest first when the sort is reversed."""
    return (activation.date, str(activation.news_id.root))


def _scroll(store: VectorStore, scroll_filter: Filter) -> list[NumberActivation]:
    """Return every activation the filter matches, page by page, unsorted."""
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
            return activations
