"""The history without a database: the per-day fold, the payload translation and the write's shape.

The window itself (filters, pagination, ordering) and the batch's effect on the collection need an
engine and are covered by ``tests/integration/test_vector_history.py``. What can be pinned without
one is pinned here: `activation_frequency` folds the rows a read already returned, the malformed
payload translation is driven by a scripted client, and a scripted write records the one call a
batch makes — including that an empty batch makes none.
"""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import uuid4

import pytest
from qdrant_client.models import PointStruct, Record

from numenews.models import DayActivationCount, NewsId, NumberActivation
from numenews.vector import (
    VectorStore,
    VectorStoreError,
    activation_frequency,
    get_history,
    record_activation,
    record_activations,
)
from numenews.vector.payloads import activation_payload, activation_point_id

DAY = date(2026, 9, 21)


def _activation(*, number: int, day: date = DAY) -> NumberActivation:
    """Return one activation row of ``number`` on ``day``, with a fresh news id."""
    return NumberActivation(
        number=number,
        date=day,
        news_id=NewsId(uuid4()),
        context=f"the {number} appeared here",
    )


class _ScriptedClient:
    """A Qdrant client that reports the collection as present and answers with one stored point."""

    def __init__(self, record: Record) -> None:
        self._record = record

    def collection_exists(self, collection_name: str) -> bool:
        return True

    def scroll(self, collection_name: str, **kwargs: object) -> tuple[list[Record], None]:
        return [self._record], None


class _ScriptedStore:
    """A store whose only reachable collaborator is that client: a read asks for nothing else."""

    def __init__(self, record: Record) -> None:
        self.client = _ScriptedClient(record)


def test_an_empty_history_has_no_buckets() -> None:
    """Nothing to read is an empty series, not a bucket at zero."""
    assert activation_frequency([]) == ()


def test_activations_of_one_day_share_a_bucket() -> None:
    """The frequency is a count of rows, so a day's several mentions become one number."""
    activations = [_activation(number=11), _activation(number=11), _activation(number=11)]

    assert activation_frequency(activations) == (DayActivationCount(date=DAY, count=3),)


def test_buckets_are_newest_first_like_the_read_they_fold() -> None:
    """The series reads in the same order as `get_history`: newest day first."""
    older = date(2026, 9, 19)
    activations = [
        _activation(number=7, day=older),
        _activation(number=11),
        _activation(number=7),
    ]

    assert activation_frequency(activations) == (
        DayActivationCount(date=DAY, count=2),
        DayActivationCount(date=older, count=1),
    )


def test_the_bucket_counts_rows_not_distinct_numbers() -> None:
    """Two numbers active on one day are two activations, because two rows were written."""
    activations = [_activation(number=11), _activation(number=22)]

    assert activation_frequency(activations) == (DayActivationCount(date=DAY, count=2),)


def test_a_malformed_stored_payload_is_reported_as_a_store_error() -> None:
    """A point the model refuses is the layer's failure, named so an operator can find it."""
    record = Record(id="bad-point", payload={"number": 11, "date": "2026-09-21T00:00:00Z"})
    # A read is annotated against the real store, and no duck-typed double can satisfy a nominal
    # class; the double answers `client` and `client.scroll`, which is all a window read reaches.
    store = cast(VectorStore, _ScriptedStore(record))

    with pytest.raises(VectorStoreError) as raised:
        get_history(store, 11, days=7, today=DAY)

    assert "bad-point" in str(raised.value)
    assert "number_history" in str(raised.value)


class _UntouchableStore:
    """A store that fails on any client access: an empty batch must not reach Qdrant."""

    @property
    def client(self) -> object:
        raise AssertionError("an empty batch must not touch the collection")


class _RecordingClient:
    """A Qdrant client that answers a history write and keeps the points it was handed."""

    def __init__(self) -> None:
        self.points: list[list[PointStruct]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return True

    def create_payload_index(
        self, collection_name: str, field_name: str, field_schema: object
    ) -> None:
        """Accept the index creation `create_number_history_collection` performs."""

    def upsert(self, collection_name: str, points: list[PointStruct], wait: bool = False) -> None:
        self.points.append(points)


class _RecordingStore:
    """A store whose only reachable collaborator is the client that records the write."""

    def __init__(self) -> None:
        self.client = _RecordingClient()


def test_an_empty_batch_writes_nothing_and_never_reaches_the_store() -> None:
    """No activations means no collection to ensure and no upsert, exactly as the loop did.

    The double raises on the first access to its client, so the early return is what this observes:
    an implementation that ensured the collection before looking at the batch would fail here.
    """
    assert record_activations(cast(VectorStore, _UntouchableStore()), []) == 0


def test_a_batch_is_one_upsert_carrying_every_activation() -> None:
    """The batch is the point of the change: one call, so the write phase has one place to die."""
    activations = [_activation(number=7), _activation(number=11), _activation(number=22)]
    store = _RecordingStore()

    written = record_activations(cast(VectorStore, store), activations)

    assert written == 3
    assert len(store.client.points) == 1
    assert [point.id for point in store.client.points[0]] == [
        activation_point_id(activation) for activation in activations
    ]


def test_a_single_activation_keeps_the_point_id_the_pair_derives() -> None:
    """`record_activation` delegates to the batch: the same point id, payload and one call.

    The id is the `(news item, number)` key from `activation_point_id`, which makes a re-ingest an
    overwrite, and the payload comes from `activation_payload`; the delegation must not move either.
    """
    activation = _activation(number=11)
    store = _RecordingStore()

    record_activation(cast(VectorStore, store), activation)

    assert store.client.points == [
        [
            PointStruct(
                id=activation_point_id(activation),
                vector={},
                payload=activation_payload(activation),
            )
        ]
    ]
