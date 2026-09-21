"""The ``news`` collection, exercised against the in-memory Qdrant engine.

The vectors are stated by the test rather than computed: a one-hot vector per title makes cosine
similarity exactly 1 or exactly 0, so "which item came back first" is a fact about the collection,
not about a model's taste. Whether the payload indexes exist cannot be checked here — local mode
ignores them — and is asserted against Docker in ``test_vector_docker.py``.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest
from qdrant_client.models import VectorParams

from numenews.models import NewsFilter, NewsId, NewsItem
from numenews.vector import (
    NEWS_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    get_news_items,
    read_news_range,
    search_news,
    upsert_news,
)
from numenews.vector.payloads import news_embedding_text

from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def _item(
    title: str,
    *,
    source: str = "example.com",
    published: date = date(2026, 9, 21),
    numerology_value: int | None = None,
    numbers: tuple[int, ...] = (),
) -> NewsItem:
    """Return a news item with a deterministic id, so a re-upsert targets the same point."""
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, f"https://example.test/{title}")),
        title=title,
        text=f"{title} body",
        source=source,
        date=published,
        url=f"https://example.test/{title}",
        numbers=numbers,
        numerology_value=numerology_value,
    )


def test_upserting_creates_the_collection_with_the_right_vector_size(
    vector_store: VectorStore,
) -> None:
    """Roadmap 3.3: the collection and its schema exist before the first point is written."""
    upsert_news(vector_store, [_item("sun rises")])

    info = vector_store.client.get_collection(NEWS_COLLECTION)

    assert isinstance(info.config.params.vectors, VectorParams)
    assert info.config.params.vectors.size == 768
    assert info.points_count == 1


def test_an_empty_batch_touches_nothing(vector_store: VectorStore) -> None:
    """Nothing to store is not a reason to create a collection."""
    assert upsert_news(vector_store, []) == 0
    assert not vector_store.client.collection_exists(NEWS_COLLECTION)


def test_upserting_the_same_item_twice_keeps_one_point(vector_store: VectorStore) -> None:
    """The deterministic id makes a repeated ingest idempotent, which phase 5 depends on."""
    item = _item("sun rises")

    upsert_news(vector_store, [item])
    upsert_news(vector_store, [item])

    assert vector_store.client.count(NEWS_COLLECTION, exact=True).count == 1


def _register(fake: FakeEmbedder, item: NewsItem, index: int) -> NewsItem:
    """Point the fake at one item's embedded text — headline and body, not the headline."""
    fake.register_axis(news_embedding_text(item), index)
    return item


def test_search_returns_the_nearest_item_first(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """Roadmap 3.3 DoD: upsert then search by semantics returns the nearest stored article."""
    nearest = _register(fake_base_embedder, _item("markets fall"), 0)
    farther = _register(fake_base_embedder, _item("the sun rises"), 1)
    upsert_news(vector_store, [nearest, farther])

    results = search_news(vector_store, "markets fall", limit=2)

    assert [item.title for item in results] == ["markets fall", "the sun rises"]


def test_a_stored_item_comes_back_as_the_same_model(
    vector_store: VectorStore,
) -> None:
    """The payload is lossless: what phase 5 reads back is what phase 4 stored."""
    item = _item("sun rises", numerology_value=7, numbers=(7, 2026))

    upsert_news(vector_store, [item])

    assert search_news(vector_store, "sun rises") == [item]


def test_a_numerology_filter_narrows_the_search(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """Roadmap 3.8's filter: only the items whose reduced value is 7 are returned."""
    items = [
        _register(fake_base_embedder, _item("seven", numerology_value=7), 0),
        _register(fake_base_embedder, _item("three", numerology_value=3), 1),
        _register(fake_base_embedder, _item("seven again", numerology_value=7), 2),
    ]
    upsert_news(vector_store, items)

    results = search_news(vector_store, "x", NewsFilter(numerology_value=7), limit=10)

    assert {item.title for item in results} == {"seven", "seven again"}


def test_items_without_a_computed_value_never_match_a_value_filter(
    vector_store: VectorStore,
) -> None:
    """`None` is "not computed", not a value: the item is stored but filtered out."""
    upsert_news(vector_store, [_item("unread")])

    assert search_news(vector_store, "unread", NewsFilter(numerology_value=7)) == []
    # The item is still there; only the value filter excludes it.
    assert search_news(vector_store, "unread") == [_item("unread")]


def test_the_master_flag_is_filterable(
    vector_store: VectorStore,
) -> None:
    """The derived boolean is what lets phase 7 ask for the days of a master number."""
    upsert_news(
        vector_store,
        [_item("eleven", numerology_value=11), _item("seven", numerology_value=7)],
    )

    assert [
        item.title for item in search_news(vector_store, "x", NewsFilter(master_number=True))
    ] == ["eleven"]
    assert [
        item.title for item in search_news(vector_store, "x", NewsFilter(master_number=False))
    ] == ["seven"]


def test_source_and_date_filters_narrow_the_search(vector_store: VectorStore) -> None:
    """The three other indexed fields behave like the value filter."""
    upsert_news(
        vector_store,
        [
            _item("early", source="a.example", published=date(2026, 9, 15)),
            _item("late", source="b.example", published=date(2026, 9, 21)),
        ],
    )

    assert [
        item.title for item in search_news(vector_store, "x", NewsFilter(source="b.example"))
    ] == ["late"]
    assert [
        item.title
        for item in search_news(
            vector_store,
            "x",
            NewsFilter(date_from=date(2026, 9, 20), date_to=date(2026, 9, 21)),
        )
    ] == ["late"]


def test_searching_an_absent_collection_raises_a_clear_error(
    vector_store: VectorStore,
) -> None:
    """A read before any write explains the missing setup instead of leaking a Qdrant error."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        search_news(vector_store, "anything")


def test_a_non_positive_limit_is_refused(vector_store: VectorStore) -> None:
    """`limit` is a count, and zero or negative would ask the engine for nothing sensible."""
    with pytest.raises(ValueError, match="limit must be positive"):
        search_news(vector_store, "anything", limit=0)


def test_reading_items_by_id_returns_them_in_the_requested_order(
    vector_store: VectorStore,
) -> None:
    """Phase 5.3 gets a list of ids from a search and has to show the items those ids name."""
    first = _item("alpha")
    second = _item("beta")
    upsert_news(vector_store, [first, second])

    found = get_news_items(vector_store, [second.id, first.id])

    assert [item.title for item in found] == ["beta", "alpha"]


def test_reading_items_by_id_skips_an_id_that_is_not_stored(vector_store: VectorStore) -> None:
    """A mistyped id is a normal outcome of an id-only request, not an error."""
    stored = _item("alpha")
    upsert_news(vector_store, [stored])

    missing = _item("nowhere")

    assert get_news_items(vector_store, [missing.id, stored.id]) == [stored]


def test_reading_no_ids_touches_nothing(vector_store: VectorStore) -> None:
    """An empty request needs no collection to exist."""
    assert get_news_items(vector_store, []) == []
    assert not vector_store.client.collection_exists(NEWS_COLLECTION)


def test_reading_an_absent_collection_by_id_explains_the_setup(vector_store: VectorStore) -> None:
    """Unlike an unknown id, a missing collection is a setup error and says so."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        get_news_items(vector_store, [_item("alpha").id])


def test_the_window_reads_both_ends_inclusively(vector_store: VectorStore) -> None:
    """Roadmap 5.5: seven days means the seven days, starting and ending where the caller asked."""
    upsert_news(
        vector_store,
        [
            _item("before", published=date(2026, 9, 14)),
            _item("first", published=date(2026, 9, 15)),
            _item("middle", published=date(2026, 9, 18)),
            _item("last", published=date(2026, 9, 21)),
            _item("after", published=date(2026, 9, 22)),
        ],
    )

    window = read_news_range(vector_store, date(2026, 9, 15), date(2026, 9, 21))

    assert [item.title for item in window] == ["first", "middle", "last"]


def test_the_window_is_ordered_by_date_oldest_first(vector_store: VectorStore) -> None:
    """A prompt built from the window is stable because the order does not depend on the engine."""
    upsert_news(
        vector_store,
        [
            _item("last", published=date(2026, 9, 21)),
            _item("first", published=date(2026, 9, 15)),
        ],
    )

    assert [
        item.title for item in read_news_range(vector_store, date(2026, 9, 15), date(2026, 9, 21))
    ] == ["first", "last"]


def test_an_empty_window_returns_nothing(vector_store: VectorStore) -> None:
    """A quiet day is an empty list, not a missing collection (the collection exists by then)."""
    upsert_news(vector_store, [_item("older", published=date(2026, 9, 1))])

    assert read_news_range(vector_store, date(2026, 9, 15), date(2026, 9, 21)) == []


def test_reading_a_window_from_an_absent_collection_explains_the_setup(
    vector_store: VectorStore,
) -> None:
    """The window read runs on a store that was never initialised."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        read_news_range(vector_store, date(2026, 9, 15), date(2026, 9, 21))
