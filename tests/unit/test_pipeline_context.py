"""Tests for the sliding window and the partition it implies (ROADMAP 5.5).

The window is one rule with one definition — ``window_start`` — and ``partition`` is its other
reader: the days inside the window are the ones the agents see, the days before it are the ones a
digest compresses. These tests pin the boundary arithmetic without a store, a model or a clock.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest

from numenews.models import NewsId, NewsItem
from numenews.pipeline import window_start
from numenews.pipeline.context import partition

END = date(2026, 9, 21)


def _item(day: date, *, title: str = "story") -> NewsItem:
    """Return a news item published on ``day`` with a deterministic id."""
    url = f"https://example.com/{title}-{day.isoformat()}"
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, url)),
        title=f"{title} {day.isoformat()}",
        text="Some text.",
        source="example.com",
        date=day,
        url=url,
    )


def test_the_window_ends_on_the_day_it_is_given_and_includes_it() -> None:
    """Seven days are the day itself and the six before it, as ``get_history`` counts them."""
    assert window_start(END, 7) == date(2026, 9, 15)
    assert window_start(END, 1) == END


def test_the_window_start_depends_on_the_window_length() -> None:
    """The arithmetic is a subtraction of ``window_days - 1``, not a week constant."""
    assert window_start(END, 30) == END - timedelta(days=29)


def test_partition_keeps_the_window_and_the_older_items_apart() -> None:
    """The boundary day belongs to the window; the day before it does not."""
    inside = _item(date(2026, 9, 15))
    boundary_before = _item(date(2026, 9, 14))
    end_day = _item(date(2026, 9, 21))

    recent, older = partition([end_day, boundary_before, inside], end=END, window_days=7)

    assert recent == [inside, end_day]
    assert older == [boundary_before]


def test_partition_is_oldest_first_in_both_halves() -> None:
    """A prompt and a digest both read better chronologically, whatever order the store returned."""
    recent, older = partition(
        [
            _item(date(2026, 9, 21)),
            _item(date(2026, 9, 16)),
            _item(date(2026, 9, 2)),
            _item(date(2026, 9, 1)),
        ],
        end=END,
        window_days=7,
    )

    assert [item.date for item in recent] == [date(2026, 9, 16), date(2026, 9, 21)]
    assert [item.date for item in older] == [date(2026, 9, 1), date(2026, 9, 2)]


def test_partition_leaves_the_future_out_of_both_halves() -> None:
    """A replayed day must not summarise what had not happened yet."""
    future = _item(date(2026, 9, 25))
    inside = _item(date(2026, 9, 20))

    recent, older = partition([future, inside], end=END, window_days=7)

    assert recent == [inside]
    assert older == []


def test_partition_of_nothing_is_two_empty_lists() -> None:
    """An empty store is not an error: nothing to show and nothing to compress."""
    assert partition([], end=END, window_days=7) == ([], [])


@pytest.mark.parametrize("window_days", [1, 7, 30])
def test_partition_covers_every_item_exactly_once(window_days: int) -> None:
    """Nothing in the past is silently dropped: each item is recent or older, never both."""
    items = [_item(END - timedelta(days=offset)) for offset in range(0, 40)]

    recent, older = partition(items, end=END, window_days=window_days)

    assert len(recent) == window_days
    assert len(older) == len(items) - window_days
