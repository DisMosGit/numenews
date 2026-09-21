"""The pure half of the history read: folding activations into their per-day frequency.

The window itself (filters, pagination, ordering) needs a database and is covered by
``tests/integration/test_vector_history.py``. `activation_frequency` is a function over the rows a
read already returned, so it is tested here, without a store.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from numenews.models import DayActivationCount, NewsId, NumberActivation
from numenews.vector import activation_frequency

DAY = date(2026, 9, 21)


def _activation(*, number: int, day: date = DAY) -> NumberActivation:
    """Return one activation row of ``number`` on ``day``, with a fresh news id."""
    return NumberActivation(
        number=number,
        date=day,
        news_id=NewsId(uuid4()),
        context=f"the {number} appeared here",
    )


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
