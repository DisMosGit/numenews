"""The ``news`` collection: articles a semantic query can find and a payload filter can narrow.

``search_news`` embeds the query with the 768d model and asks Qdrant for the nearest points after
applying the payload filter; because the filter's fields are indexed, the narrowing happens inside
the HNSW walk rather than after it. ``hybrid_search_news`` (3.8) is the multi-stage form of the same
question.

Writes are idempotent by construction: the point id is the item's deterministic ``NewsId``, so a
repeated ingest of the same article overwrites its point instead of adding a second copy.
"""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client.models import Fusion, FusionQuery, PointStruct, Prefetch

from numenews.logging import get_logger
from numenews.models import NewsFilter, NewsItem
from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    NEWS_COLLECTION,
    create_news_collection,
    require_collection,
)
from numenews.vector.filters import build_news_filter
from numenews.vector.payloads import (
    news_embedding_text,
    news_from_payload,
    news_payload,
    news_point_id,
)

logger = get_logger(__name__)


def upsert_news(store: VectorStore, items: Sequence[NewsItem]) -> int:
    """Embed and store ``items`` in one batch, returning how many points were written.

    The collection and its payload indexes are created here if they are missing — before the first
    point is written, as roadmap 3.3 requires — and the whole batch is embedded in one call, so the
    model sees a batch instead of N single texts.

    Args:
        store: The connection and the 768d embedder.
        items: Articles to store; their order is preserved.

    Returns:
        The number of points written (``0`` for an empty batch, without touching the collection).
    """
    if not items:
        return 0
    create_news_collection(store.client)
    vectors = store.base.embed([news_embedding_text(item) for item in items])
    points = [
        PointStruct(id=news_point_id(item), vector=vector, payload=news_payload(item))
        for item, vector in zip(items, vectors, strict=True)
    ]
    store.client.upsert(NEWS_COLLECTION, points, wait=True)
    logger.info("vector.news.upserted", items=len(points))
    return len(points)


def search_news(
    store: VectorStore,
    query: str,
    filters: NewsFilter | None = None,
    limit: int = 10,
) -> list[NewsItem]:
    """Return the items nearest to ``query`` among those ``filters`` allow, best first.

    Args:
        store: The connection and the 768d embedder.
        query: Free text, embedded with the same model as the stored items.
        filters: Payload constraints; ``None`` searches everything.
        limit: Maximum number of items to return.

    Raises:
        ValueError: when ``limit`` is not positive.
        CollectionNotFoundError: when the ``news`` collection was never created.

    Returns:
        The matching items, ordered by cosine similarity. The scores are not part of the result:
        phase 3 works with the entities, and a caller that needs a score can query the collection
        directly.
    """
    if limit < 1:
        raise ValueError("search limit must be positive")
    require_collection(store.client, NEWS_COLLECTION)
    vectors = store.base.embed([query])
    response = store.client.query_points(
        collection_name=NEWS_COLLECTION,
        query=vectors[0],
        query_filter=build_news_filter(filters),
        limit=limit,
        with_payload=True,
    )
    return [news_from_payload(point.payload or {}) for point in response.points]


def hybrid_search_news(
    store: VectorStore,
    query: str,
    filters: NewsFilter | None = None,
    limit: int = 10,
) -> list[NewsItem]:
    """Return the items nearest to ``query`` using the multi-stage (Query API) form.

    Where :func:`search_news` passes the filter alongside a single dense query, this builds the
    question the way a hybrid retriever has to: each retriever runs inside a
    :class:`~qdrant_client.models.Prefetch` with its own filter, and a
    :class:`~qdrant_client.models.FusionQuery` merges their rankings. With the filter inside the
    prefetch, Qdrant narrows the candidate set before the HNSW walk of that retriever, which is the
    pre-filtering the payload indexes exist for (roadmap 3.8).

    Phase 3 has one dense retriever, so the fusion receives a single ranking; the shape is what
    matters, because a sparse/BM25 prefetch is a second entry in the same list. The consequence is
    that the returned order is by reciprocal-rank fusion (``1 / (60 + rank)``) rather than by cosine
    similarity, and the ranks are relative within the prefetch's own ``limit``.

    Args:
        store: The connection and the 768d embedder.
        query: Free text, embedded with the same model as the stored items.
        filters: Payload constraints; ``None`` searches everything.
        limit: Maximum number of items to return, and the size of the candidate set each retriever
            ranks.

    Raises:
        ValueError: when ``limit`` is not positive.
        CollectionNotFoundError: when the ``news`` collection was never created.

    Returns:
        The matching items, best fused rank first.
    """
    if limit < 1:
        raise ValueError("search limit must be positive")
    require_collection(store.client, NEWS_COLLECTION)
    vector = store.base.embed([query])[0]
    response = store.client.query_points(
        collection_name=NEWS_COLLECTION,
        prefetch=[
            Prefetch(query=vector, filter=build_news_filter(filters), limit=limit),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    return [news_from_payload(point.payload or {}) for point in response.points]
