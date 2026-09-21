"""The ``patterns`` collection, over the in-memory engine.

The stored pattern is checked twice: as a model (does what comes back equal what went in?) and as a
payload (are the indexed fields really there?). The similarity ordering is stated by the test
through the fake embedder, so a failure here is about the collection, not about a model's taste.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import pytest
from qdrant_client.models import VectorParams

from numenews.models import NewsId, Pattern, PatternId, PatternType
from numenews.vector import (
    PATTERNS_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    find_similar_patterns,
    read_patterns,
    save_pattern,
)
from numenews.vector.payloads import pattern_embedding_text

from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def _pattern(
    interpretation: str = "7 repeats across the week",
    *,
    kind: PatternType = "resonance",
    strength: float = 0.5,
    discovered_at: datetime | None = None,
) -> Pattern:
    """Return a valid pattern with a deterministic id derived from its interpretation."""
    return Pattern(
        id=PatternId(uuid5(NAMESPACE_URL, interpretation)),
        type=kind,
        numbers=(7,),
        news_ids=(NewsId(uuid5(NAMESPACE_URL, "https://example.test/a")),),
        strength=strength,
        interpretation=interpretation,
        discovered_at=discovered_at,
    )


def test_saving_creates_a_768d_collection(vector_store: VectorStore) -> None:
    """Patterns are embedded with the wide model, so the collection is 768d."""
    save_pattern(vector_store, _pattern())

    info = vector_store.client.get_collection(PATTERNS_COLLECTION)

    assert isinstance(info.config.params.vectors, VectorParams)
    assert info.config.params.vectors.size == 768
    assert info.points_count == 1


def test_saving_stamps_the_discovery_time(vector_store: VectorStore) -> None:
    """A pattern the agent just produced has no timestamp; storage gives it one."""
    before = datetime.now(UTC)

    saved = save_pattern(vector_store, _pattern())

    assert saved.discovered_at is not None
    assert before <= saved.discovered_at


def test_saving_keeps_an_existing_discovery_time(vector_store: VectorStore) -> None:
    """Re-saving a pattern that came back from storage must not rewrite its history."""
    discovered = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

    saved = save_pattern(vector_store, _pattern(discovered_at=discovered))

    assert saved.discovered_at == discovered


def test_a_stored_pattern_comes_back_as_the_same_model(vector_store: VectorStore) -> None:
    """The payload is lossless: ids, news ids and timestamp included."""
    saved = save_pattern(vector_store, _pattern())

    assert find_similar_patterns(vector_store, "seven") == [saved]


def test_saving_the_same_pattern_twice_keeps_one_point(vector_store: VectorStore) -> None:
    """The point id is the `PatternId`, so a repeated save is an overwrite."""
    pattern = _pattern()

    save_pattern(vector_store, pattern)
    save_pattern(vector_store, pattern)

    assert vector_store.client.count(PATTERNS_COLLECTION, exact=True).count == 1


def test_similar_patterns_come_back_nearest_first(
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
) -> None:
    """Roadmap 3.5: a query finds the pattern whose interpretation it is closest to."""
    nearest = _pattern("master numbers around money")
    farther = _pattern("dates that reduce to the same value")
    fake_base_embedder.register_axis(pattern_embedding_text(nearest), 0)
    fake_base_embedder.register_axis(pattern_embedding_text(farther), 1)
    save_pattern(vector_store, nearest)
    save_pattern(vector_store, farther)

    results = find_similar_patterns(vector_store, "master numbers around money", limit=2)

    assert [pattern.interpretation for pattern in results] == [
        nearest.interpretation,
        farther.interpretation,
    ]


def test_the_stored_payload_carries_the_indexed_fields(vector_store: VectorStore) -> None:
    """`type`, `strength` and `discovered_at` are what phase 7 filters on."""
    saved = save_pattern(vector_store, _pattern(kind="master", strength=0.75))

    stored = vector_store.client.retrieve(
        PATTERNS_COLLECTION,
        [str(saved.id.root)],
        with_payload=True,
    )

    payload = stored[0].payload or {}
    assert payload["type"] == "master"
    assert payload["strength"] == 0.75
    # Stored as an RFC 3339 timestamp, which is the only shape a DATETIME index accepts.
    assert isinstance(payload["discovered_at"], str)
    assert datetime.fromisoformat(payload["discovered_at"].replace("Z", "+00:00")) == (
        saved.discovered_at
    )


def test_searching_without_the_collection_raises_a_clear_error(
    vector_store: VectorStore,
) -> None:
    """A read before any write explains the missing setup."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        find_similar_patterns(vector_store, "anything")


def test_a_non_positive_limit_is_refused(vector_store: VectorStore) -> None:
    """`limit` is a count; zero would ask the engine for nothing sensible."""
    with pytest.raises(ValueError, match="limit must be positive"):
        find_similar_patterns(vector_store, "anything", limit=0)


def test_read_patterns_returns_everything_unfiltered(vector_store: VectorStore) -> None:
    """The exact read of roadmap 7.7 with no arguments lists the collection."""
    save_pattern(vector_store, _pattern("first"))
    save_pattern(vector_store, _pattern("second"))

    assert {pattern.interpretation for pattern in read_patterns(vector_store)} == {
        "first",
        "second",
    }


def test_read_patterns_filters_by_type(vector_store: VectorStore) -> None:
    """``--type`` narrows to one of the five kinds through the indexed payload field."""
    save_pattern(vector_store, _pattern("master money", kind="master"))
    save_pattern(vector_store, _pattern("dates resonate", kind="resonance"))

    found = read_patterns(vector_store, pattern_type="master")

    assert [pattern.interpretation for pattern in found] == ["master money"]


def test_read_patterns_filters_by_min_strength(vector_store: VectorStore) -> None:
    """``--min-strength`` keeps only the patterns at or above the bound."""
    save_pattern(vector_store, _pattern("strong", strength=0.8))
    save_pattern(vector_store, _pattern("weak", strength=0.4))

    found = read_patterns(vector_store, min_strength=0.7)

    assert [pattern.interpretation for pattern in found] == ["strong"]


def test_read_patterns_orders_by_strength_then_newest(vector_store: VectorStore) -> None:
    """Strength is the primary key; discovery time breaks its ties, newest first."""
    older = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    newer = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
    save_pattern(vector_store, _pattern("weak new", strength=0.2, discovered_at=newer))
    save_pattern(vector_store, _pattern("strong old", strength=0.9, discovered_at=older))
    save_pattern(vector_store, _pattern("strong new", strength=0.9, discovered_at=newer))

    found = read_patterns(vector_store)

    assert [pattern.interpretation for pattern in found] == [
        "strong new",
        "strong old",
        "weak new",
    ]


def test_read_patterns_honours_the_limit(vector_store: VectorStore) -> None:
    """The limit cuts after the ordering, so it keeps the strongest ones."""
    save_pattern(vector_store, _pattern("strong", strength=0.9))
    save_pattern(vector_store, _pattern("weak", strength=0.1))

    found = read_patterns(vector_store, limit=1)

    assert [pattern.interpretation for pattern in found] == ["strong"]


def test_read_patterns_without_the_collection_raises(vector_store: VectorStore) -> None:
    """A read before any write explains the missing setup, as the other reads do."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        read_patterns(vector_store)


def test_read_patterns_refuses_bad_arguments(vector_store: VectorStore) -> None:
    """A non-positive limit and an out-of-range strength are call-site bugs, not empty results."""
    save_pattern(vector_store, _pattern())

    with pytest.raises(ValueError, match="limit must be positive"):
        read_patterns(vector_store, limit=0)
    with pytest.raises(ValueError, match="between 0 and 1"):
        read_patterns(vector_store, min_strength=1.5)
