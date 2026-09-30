"""The history read without a database: the per-day fold and the payload translation.

The window itself (filters, pagination, ordering) needs an engine and is covered by
``tests/integration/test_vector_history.py``. What can be pinned without one is pinned here:
`activation_frequency` folds the rows a read already returned, and the translation of a malformed
stored payload is driven by a scripted client, so neither test opens a store.
"""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import uuid4

import pytest
from qdrant_client.models import Record

from numenews.models import DayActivationCount, NewsId, NumberActivation
from numenews.vector import VectorStore, VectorStoreError, activation_frequency, get_history

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
