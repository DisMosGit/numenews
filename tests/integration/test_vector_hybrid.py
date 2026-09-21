"""The hybrid (multi-stage) news search, over the in-memory engine.

Roadmap 3.8 asks for a dense query whose payload filter is applied inside the ``Prefetch`` — the
pre-filtering the payload indexes exist for. The test proves it the only way a caller can tell:
an item that is the exact vector twin of the query but fails the filter must not come back, while
an unfiltered search still returns it.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest

from numenews.models import NewsFilter, NewsId, NewsItem
from numenews.vector import (
    NEWS_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    hybrid_search_news,
    search_news,
    upsert_news,
)
from numenews.vector.payloads import news_embedding_text

from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def _item(title: str, *, numerology_value: int | None = None) -> NewsItem:
    """Return a news item with a deterministic id."""
    return NewsItem(
        id=NewsId(uuid5(NAMESPACE_URL, f"https://example.test/{title}")),
        title=title,
        text=f"{title} body",
        source="example.com",
        date=date(2026, 9, 21),
        url=f"https://example.test/{title}",
        numerology_value=numerology_value,
    )


def _register(fake: FakeEmbedder, item: NewsItem, axis: int) -> NewsItem:
    """Map the item's embedded text to a one-hot axis and return the item."""
    fake.register_axis(news_embedding_text(item), axis)
    return item


def test_the_filter_narrows_what_the_dense_retriever_can_rank(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """Roadmap 3.8 DoD: `numerology_value=7` + a semantic query, filter inside the prefetch.

    ``twin`` is embedded to the very same vector as the query, so it would win an unfiltered
    ranking; it is filtered out by its reduced value, which is only possible if the filter is
    applied to the candidate set the retriever ranks.
    """
    matching = _register(fake_base_embedder, _item("seven", numerology_value=7), 0)
    twin = _register(fake_base_embedder, _item("seven twin", numerology_value=3), 0)
    farther = _register(fake_base_embedder, _item("quiet day", numerology_value=7), 1)
    upsert_news(vector_store, [matching, twin, farther])

    results = hybrid_search_news(
        vector_store,
        "seven",
        NewsFilter(numerology_value=7),
        limit=10,
    )

    assert {item.title for item in results} == {"seven", "quiet day"}
    # The same query without the filter still sees the twin, so the filter — not the vector — is
    # what removed it.
    assert {item.title for item in search_news(vector_store, "seven", limit=10)} == {
        "seven",
        "seven twin",
        "quiet day",
    }


def test_the_nearest_item_comes_first(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """Fusion preserves the dense ranking when there is only one retriever."""
    nearest = _register(fake_base_embedder, _item("markets fall"), 0)
    farther = _register(fake_base_embedder, _item("the sun rises"), 1)
    upsert_news(vector_store, [nearest, farther])

    results = hybrid_search_news(vector_store, "markets fall", limit=2)

    assert [item.title for item in results] == ["markets fall", "the sun rises"]


def test_a_filter_that_matches_nothing_returns_nothing(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """A narrowed candidate set can be empty, and that is an answer, not an error."""
    upsert_news(
        vector_store, [_register(fake_base_embedder, _item("seven", numerology_value=7), 0)]
    )

    assert hybrid_search_news(vector_store, "seven", NewsFilter(numerology_value=3)) == []


def test_the_limit_bounds_the_result(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """`limit` is the size of the candidate set as well as of the result."""
    items = [
        _register(fake_base_embedder, _item(f"item {index}", numerology_value=7), index)
        for index in range(3)
    ]
    upsert_news(vector_store, items)

    assert len(hybrid_search_news(vector_store, "item 0", limit=2)) == 2


def test_searching_an_absent_collection_raises_a_clear_error(
    vector_store: VectorStore,
) -> None:
    """A read before any write explains the missing setup."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        hybrid_search_news(vector_store, "anything")


def test_a_non_positive_limit_is_refused(vector_store: VectorStore) -> None:
    """`limit` is a count; zero would ask the engine for nothing sensible."""
    with pytest.raises(ValueError, match="limit must be positive"):
        hybrid_search_news(vector_store, "anything", limit=0)


def test_the_collection_is_still_just_news(vector_store: VectorStore) -> None:
    """Hybrid search reads the same collection the plain search writes; there is no second index."""
    upsert_news(vector_store, [_item("seven", numerology_value=7)])

    assert vector_store.client.collection_exists(NEWS_COLLECTION)
    assert hybrid_search_news(vector_store, "seven") != []
