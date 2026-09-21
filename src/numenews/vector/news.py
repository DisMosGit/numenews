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

from qdrant_client.models import PointStruct

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
