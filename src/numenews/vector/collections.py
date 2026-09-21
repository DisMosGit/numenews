"""The collection schemas, created before the first point is written.

Payload indexes come first, not after the data: with an index Qdrant pre-filters inside the HNSW
walk, without one it collects candidates and throws most of them away. Every ``create_*`` here is
therefore idempotent — it checks ``collection_exists`` before creating — and every write path calls
it, so ``upsert_news`` cannot run against a collection that has no indexes yet.

One unnamed COSINE vector per collection is deliberate: phase 3 searches dense vectors only
(roadmap 3.8 is "dense + filter"), and a single vector keeps the point payload the only place where
a schema can drift. The width is the model the collection was designed around — 768d for ``news``,
384d for the short number contexts of ``numbers`` — so a wrong embedder fails at creation rather
than silently at the first query. ``docs/QDRANT_COLLECTIONS.md`` records each payload field.

Local mode (``QdrantClient(":memory:")``) ignores payload indexes and warns about it; the indexes
are asserted against the Docker server in ``tests/integration/test_vector_docker.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from numenews.embeddings import BASE_DIMENSION, SMALL_DIMENSION
from numenews.logging import get_logger
from numenews.vector.errors import CollectionNotFoundError

logger = get_logger(__name__)

NEWS_COLLECTION = "news"
NUMBERS_COLLECTION = "numbers"
PATTERNS_COLLECTION = "patterns"
FORECASTS_COLLECTION = "forecasts"

#: Payload fields of ``news`` that get an index, in creation order. ``master_number`` is derived
#: from ``numerology_value`` by ``payloads.news_payload``: a filter on it must not have to fetch
#: every vector first to find out whether the reduced value is 11, 22 or 33.
NEWS_PAYLOAD_INDEXES: Mapping[str, PayloadSchemaType] = {
    "date": PayloadSchemaType.DATETIME,
    "source": PayloadSchemaType.KEYWORD,
    "numerology_value": PayloadSchemaType.INTEGER,
    "master_number": PayloadSchemaType.BOOL,
}

#: Payload fields of ``numbers``. ``context`` is indexed as a keyword because the searchable part
#: of a number activation is its vector, not a full-text match on the sentence around it.
NUMBERS_PAYLOAD_INDEXES: Mapping[str, PayloadSchemaType] = {
    "number": PayloadSchemaType.INTEGER,
    "context": PayloadSchemaType.KEYWORD,
}

#: Payload fields of ``patterns``. ``discovered_at`` is always written by ``save_pattern``, so the
#: datetime index never sees a null; ``strength`` is a float so phase 7 can ask for the strong
#: patterns without scanning the collection.
PATTERNS_PAYLOAD_INDEXES: Mapping[str, PayloadSchemaType] = {
    "type": PayloadSchemaType.KEYWORD,
    "strength": PayloadSchemaType.FLOAT,
    "discovered_at": PayloadSchemaType.DATETIME,
}

#: Payload fields of ``forecasts``. One forecast per day is stored under a date-derived point id,
#: so ``get_forecast`` is a point lookup; the indexes are what a range query ("the last week's
#: readings") will use.
FORECASTS_PAYLOAD_INDEXES: Mapping[str, PayloadSchemaType] = {
    "date": PayloadSchemaType.DATETIME,
    "dominant_number": PayloadSchemaType.INTEGER,
}


def create_news_collection(client: QdrantClient) -> None:
    """Create the 768d ``news`` collection and its payload indexes, unless it is already there."""
    _create_collection(client, NEWS_COLLECTION, BASE_DIMENSION)
    _create_indexes(client, NEWS_COLLECTION, NEWS_PAYLOAD_INDEXES)


def create_numbers_collection(client: QdrantClient) -> None:
    """Create the 384d ``numbers`` collection and its payload indexes, unless already there."""
    _create_collection(client, NUMBERS_COLLECTION, SMALL_DIMENSION)
    _create_indexes(client, NUMBERS_COLLECTION, NUMBERS_PAYLOAD_INDEXES)


def create_patterns_collection(client: QdrantClient) -> None:
    """Create the 768d ``patterns`` collection and its payload indexes, unless already there."""
    _create_collection(client, PATTERNS_COLLECTION, BASE_DIMENSION)
    _create_indexes(client, PATTERNS_COLLECTION, PATTERNS_PAYLOAD_INDEXES)


def create_forecasts_collection(client: QdrantClient) -> None:
    """Create the 768d ``forecasts`` collection and its payload indexes, unless already there."""
    _create_collection(client, FORECASTS_COLLECTION, BASE_DIMENSION)
    _create_indexes(client, FORECASTS_COLLECTION, FORECASTS_PAYLOAD_INDEXES)


def ensure_collections(client: QdrantClient) -> None:
    """Create every collection of the vector layer with its payload indexes; safe to re-run."""
    for create in COLLECTION_CREATORS:
        create(client)


def require_collection(client: QdrantClient, name: str) -> None:
    """Raise :class:`CollectionNotFoundError` unless ``name`` exists.

    Read paths call this so a missing collection is one actionable message instead of the raw
    ``ValueError`` local mode raises or the 404 a server returns.
    """
    if not client.collection_exists(name):
        raise CollectionNotFoundError(
            f"collection {name!r} does not exist: call VectorStore.ensure_collections() first"
        )


def _create_collection(client: QdrantClient, name: str, dimension: int) -> None:
    """Create one collection with a single unnamed cosine vector, if it is missing."""
    if client.collection_exists(name):
        return
    client.create_collection(
        name,
        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
    )
    logger.info("vector.collection.created", collection=name, dimension=dimension)


def _create_indexes(
    client: QdrantClient,
    name: str,
    schema: Mapping[str, PayloadSchemaType],
) -> None:
    """Create every payload index of one collection; a repeated call is a no-op on the server."""
    for field_name, field_schema in schema.items():
        client.create_payload_index(name, field_name, field_schema=field_schema)


#: Every collection creator, in the order ``ensure_collections`` runs them. It grows with the
#: collections of phase 3, so a caller always sees the schemas this build actually defines.
COLLECTION_CREATORS: tuple[Callable[[QdrantClient], None], ...] = (
    create_news_collection,
    create_numbers_collection,
    create_patterns_collection,
    create_forecasts_collection,
)
