"""The ``patterns`` collection: the connections between news items, searchable by meaning.

A pattern is stored twice over in a sense — its own fields, and a vector of its interpretation — so
a later run can ask "have I seen something like this before" instead of re-deriving every connection
from scratch. That is what makes the collection grow into the long-term memory of phase 8.

``save_pattern`` is the writer the MCP tool 6.9 and the pipeline (5.3) call; it stamps
``discovered_at`` when the pattern does not carry one, because "when was this found" is a fact about
storage, not about the connection.
"""

from __future__ import annotations

from datetime import UTC, datetime

from qdrant_client.models import PointStruct

from numenews.logging import get_logger
from numenews.models import Pattern
from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    PATTERNS_COLLECTION,
    create_patterns_collection,
    require_collection,
)
from numenews.vector.payloads import (
    pattern_embedding_text,
    pattern_from_payload,
    pattern_payload,
    pattern_point_id,
)

logger = get_logger(__name__)


def save_pattern(store: VectorStore, pattern: Pattern) -> Pattern:
    """Embed and store one pattern, returning the version that was written.

    The returned model is the stored one: when ``pattern.discovered_at`` was ``None``, it now
    carries the current UTC time. An existing timestamp is never overwritten, so re-saving a pattern
    that was read back from Qdrant does not rewrite its history.

    Args:
        store: The connection and the 768d embedder.
        pattern: The connection to persist.

    Returns:
        The pattern as stored, with ``discovered_at`` filled in when it was missing.
    """
    stamped = pattern
    if pattern.discovered_at is None:
        stamped = pattern.model_copy(update={"discovered_at": datetime.now(UTC)})
    create_patterns_collection(store.client)
    vector = store.base.embed([pattern_embedding_text(stamped)])[0]
    store.client.upsert(
        PATTERNS_COLLECTION,
        [
            PointStruct(
                id=pattern_point_id(stamped), vector=vector, payload=pattern_payload(stamped)
            )
        ],
        wait=True,
    )
    logger.info(
        "vector.pattern.saved",
        pattern=str(stamped.id.root),
        type=stamped.type,
        strength=stamped.strength,
    )
    return stamped


def find_similar_patterns(
    store: VectorStore,
    query: str,
    limit: int = 10,
) -> list[Pattern]:
    """Return the stored patterns whose interpretation is nearest to ``query``, best first.

    Args:
        store: The connection and the 768d embedder.
        query: Free text, embedded with the same model as the stored interpretations.
        limit: Maximum number of patterns to return.

    Raises:
        ValueError: when ``limit`` is not positive.
        CollectionNotFoundError: when the ``patterns`` collection was never created.

    Returns:
        The nearest patterns, in Qdrant's similarity order.
    """
    if limit < 1:
        raise ValueError("search limit must be positive")
    require_collection(store.client, PATTERNS_COLLECTION)
    vector = store.base.embed([query])[0]
    response = store.client.query_points(
        collection_name=PATTERNS_COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    return [pattern_from_payload(point.payload or {}) for point in response.points]
