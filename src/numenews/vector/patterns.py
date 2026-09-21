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
from uuid import UUID

from qdrant_client.models import (
    Condition,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
)

from numenews.logging import get_logger
from numenews.models import Pattern, PatternType
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

#: How many points one scroll page of :func:`read_patterns` asks for. The read paginates until
#: Qdrant stops handing back an offset, so this only bounds the round trips.
READ_PAGE = 256

#: The instant a pattern without ``discovered_at`` is ordered under. ``save_pattern`` always stamps
#: one, so this only keeps the ordering total.
_EPOCH = datetime.min.replace(tzinfo=UTC)


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


def read_patterns(
    store: VectorStore,
    *,
    pattern_type: PatternType | None = None,
    min_strength: float | None = None,
    limit: int = 50,
) -> list[Pattern]:
    """Return the stored patterns the filters allow, strongest and newest first.

    This is the exact read of the ``patterns`` collection, the counterpart of the semantic
    :func:`find_similar_patterns`: roadmap 7.7 asks "which resonance patterns are strong?" — a
    payload question, not a similarity one — so it scrolls with a filter over the two indexed fields
    (``type``, ``strength``) instead of embedding anything.

    The result is ordered by ``strength`` descending, then by ``discovered_at`` descending, then by
    pattern id, and cut to ``limit``. Qdrant has no ordering in ``scroll``, so the ordering happens
    here, after every match has been read.

    Args:
        store: The connection. The read uses no embedder.
        pattern_type: Keep only patterns of this kind; ``None`` keeps every kind.
        min_strength: Keep only patterns at least this strong, in ``[0, 1]``; ``None`` keeps all.
        limit: Maximum number of patterns to return.

    Raises:
        ValueError: when ``limit`` is not positive or ``min_strength`` is outside ``[0, 1]`` — both
            are call-site bugs, not data conditions.
        CollectionNotFoundError: when the ``patterns`` collection was never created.
    """
    if limit < 1:
        raise ValueError("search limit must be positive")
    if min_strength is not None and not 0.0 <= min_strength <= 1.0:
        raise ValueError("min_strength must be between 0 and 1")
    require_collection(store.client, PATTERNS_COLLECTION)
    conditions: list[Condition] = []
    if pattern_type is not None:
        conditions.append(FieldCondition(key="type", match=MatchValue(value=pattern_type)))
    if min_strength is not None:
        conditions.append(FieldCondition(key="strength", range=Range(gte=min_strength)))
    found = _scroll(store, Filter(must=conditions) if conditions else Filter())
    ordered = sorted(
        found,
        key=lambda pattern: (pattern.discovered_at or _EPOCH, str(pattern.id.root)),
        reverse=True,
    )
    # A second, stable sort makes strength the primary key while the timestamp order above holds
    # inside one strength.
    ordered.sort(key=lambda pattern: pattern.strength, reverse=True)
    logger.debug(
        "vector.patterns.read",
        type=pattern_type,
        min_strength=min_strength,
        matched=len(found),
        returned=min(len(ordered), limit),
    )
    return ordered[:limit]


def _scroll(store: VectorStore, scroll_filter: Filter) -> list[Pattern]:
    """Return every pattern the filter matches, page by page, unsorted."""
    patterns: list[Pattern] = []
    offset: int | str | UUID | None = None
    while True:
        records, offset = store.client.scroll(
            PATTERNS_COLLECTION,
            scroll_filter=scroll_filter,
            limit=READ_PAGE,
            offset=offset,
            with_payload=True,
        )
        patterns.extend(pattern_from_payload(record.payload or {}) for record in records)
        if offset is None:
            return patterns
