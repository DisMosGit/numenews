"""The ``number_history`` collection, over the in-memory engine.

The window is the interesting part: `get_history` must include today, exclude the day before the
window, and stay deterministic. The `today` parameter is injected rather than read from the clock,
so these tests say what they mean instead of depending on the day they run.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest

from numenews.models import NewsId, NumberActivation
from numenews.vector import (
    NUMBER_HISTORY_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    get_activations,
    get_history,
    record_activation,
)

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 21)


def _activation(
    number: int = 7,
    *,
    published: date = TODAY,
    context: str = "seven markets closed higher",
    news_url: str = "https://example.test/a",
) -> NumberActivation:
    """Return an activation with a deterministic news id."""
    return NumberActivation(
        number=number,
        date=published,
        news_id=NewsId(uuid5(NAMESPACE_URL, news_url)),
        context=context,
    )


def test_the_history_collection_has_no_vector(vector_store: VectorStore) -> None:
    """Payload-only is the point of this collection: exact questions need no embedding."""
    record_activation(vector_store, _activation())

    info = vector_store.client.get_collection(NUMBER_HISTORY_COLLECTION)

    assert info.config.params.vectors is None or info.config.params.vectors == {}
    assert info.points_count == 1


def test_a_recorded_activation_comes_back(vector_store: VectorStore) -> None:
    """Everything `get_history` returns is what `record_activation` stored."""
    activation = _activation()

    record_activation(vector_store, activation)

    assert get_history(vector_store, 7, days=7, today=TODAY) == [activation]


def test_only_the_requested_number_comes_back(vector_store: VectorStore) -> None:
    """The number is a filter, not a sort key."""
    record_activation(vector_store, _activation(number=7, news_url="a"))
    record_activation(vector_store, _activation(number=11, news_url="b"))

    assert [item.number for item in get_history(vector_store, 11, days=7, today=TODAY)] == [11]
    assert get_history(vector_store, 22, days=7, today=TODAY) == []


def test_the_window_ends_today_and_includes_it(vector_store: VectorStore) -> None:
    """`days=1` is today alone; `days=7` reaches back six days and no further."""
    for offset, url in enumerate(["a", "b", "c", "d"]):
        record_activation(
            vector_store,
            _activation(published=date(2026, 9, 21 - offset), news_url=url),
        )

    assert [item.date for item in get_history(vector_store, 7, days=1, today=TODAY)] == [TODAY]
    assert {item.date for item in get_history(vector_store, 7, days=3, today=TODAY)} == {
        date(2026, 9, 21),
        date(2026, 9, 20),
        date(2026, 9, 19),
    }
    assert len(get_history(vector_store, 7, days=7, today=TODAY)) == 4


def test_the_newest_activation_comes_first(vector_store: VectorStore) -> None:
    """A forecast reads the recent history first, so the order is part of the contract."""
    record_activation(vector_store, _activation(published=date(2026, 9, 19), news_url="older"))
    record_activation(vector_store, _activation(published=date(2026, 9, 21), news_url="newer"))

    history = get_history(vector_store, 7, days=7, today=TODAY)

    assert [item.date for item in history] == [date(2026, 9, 21), date(2026, 9, 19)]


def test_recording_the_same_activation_twice_keeps_one_row(vector_store: VectorStore) -> None:
    """A repeated ingest must not turn one event into two activations."""
    activation = _activation()

    record_activation(vector_store, activation)
    record_activation(vector_store, activation)

    assert vector_store.client.count(NUMBER_HISTORY_COLLECTION, exact=True).count == 1


def test_reading_history_from_an_absent_collection_is_a_setup_error(
    vector_store: VectorStore,
) -> None:
    """No history yet is a missing collection, not an empty answer."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        get_history(vector_store, 7, days=7, today=TODAY)


def test_a_window_shorter_than_a_day_is_refused(vector_store: VectorStore) -> None:
    """`days` counts calendar days; zero or negative is a bug at the call site."""
    with pytest.raises(ValueError, match="at least one day"):
        get_history(vector_store, 7, days=0, today=TODAY)


def test_the_whole_window_comes_back_whatever_the_number(vector_store: VectorStore) -> None:
    """Roadmap 5.4 asks "what was active", not "when was 7 active"."""
    record_activation(vector_store, _activation(number=7, news_url="a"))
    record_activation(vector_store, _activation(number=11, news_url="b"))
    record_activation(vector_store, _activation(number=7, news_url="c"))

    activations = get_activations(vector_store, days=7, today=TODAY)

    assert sorted(item.number for item in activations) == [7, 7, 11]


def test_the_whole_window_keeps_the_same_window_and_order(
    vector_store: VectorStore,
) -> None:
    """The window rule is shared with `get_history`: one implementation, one meaning."""
    record_activation(
        vector_store, _activation(number=7, published=date(2026, 9, 14), news_url="outside")
    )
    record_activation(
        vector_store, _activation(number=11, published=date(2026, 9, 19), news_url="older")
    )
    record_activation(
        vector_store, _activation(number=7, published=date(2026, 9, 21), news_url="newer")
    )

    activations = get_activations(vector_store, days=7, today=TODAY)

    assert [(item.number, item.date) for item in activations] == [
        (7, date(2026, 9, 21)),
        (11, date(2026, 9, 19)),
    ]


def test_reading_the_whole_window_from_an_absent_collection_is_a_setup_error(
    vector_store: VectorStore,
) -> None:
    """The forecast folds this into "no history"; the layer itself still reports the setup."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        get_activations(vector_store, days=7, today=TODAY)


def test_a_window_of_the_whole_history_shorter_than_a_day_is_refused(
    vector_store: VectorStore,
) -> None:
    """`days` counts calendar days here too."""
    with pytest.raises(ValueError, match="at least one day"):
        get_activations(vector_store, days=0, today=TODAY)
