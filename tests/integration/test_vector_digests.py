"""The ``digests`` collection, over the in-memory engine (ROADMAP 5.5).

A digest is identified by the period it summarises, so the two things worth proving are that the
period round-trips and that re-summarising the same period replaces the point instead of adding
another. Whether its payload indexes exist is checked against Docker in ``test_vector_docker.py``.
"""

from __future__ import annotations

from datetime import date

import pytest
from qdrant_client.models import VectorParams

from numenews.models import Digest
from numenews.vector import (
    DIGESTS_COLLECTION,
    CollectionNotFoundError,
    VectorStore,
    get_digest,
    save_digest,
)
from numenews.vector.payloads import digest_embedding_text, digest_point_id

from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration

START = date(2026, 9, 1)
END = date(2026, 9, 7)


def _digest(
    *,
    start: date = START,
    end: date = END,
    summary: str = "Период прошёл под числом 11.",
    numbers: tuple[int, ...] = (11, 7),
) -> Digest:
    """Return a valid digest for one period."""
    return Digest(period_start=start, period_end=end, summary=summary, numbers=numbers)


def test_saving_creates_a_768d_collection(vector_store: VectorStore) -> None:
    """A digest is prose, so it lives in the same embedding space as the other text collections."""
    save_digest(vector_store, _digest())

    info = vector_store.client.get_collection(DIGESTS_COLLECTION)

    assert isinstance(info.config.params.vectors, VectorParams)
    assert info.config.params.vectors.size == 768
    assert info.points_count == 1


def test_a_saved_digest_comes_back_unchanged(vector_store: VectorStore) -> None:
    """The payload is lossless: the summary and the numbers included."""
    digest = _digest()

    save_digest(vector_store, digest)

    assert get_digest(vector_store, START, END) == digest


def test_an_unwritten_period_is_none_not_an_error(vector_store: VectorStore) -> None:
    """A period that was never summarised is a legitimate answer for a caller."""
    save_digest(vector_store, _digest())

    assert get_digest(vector_store, date(2026, 9, 8), date(2026, 9, 14)) is None


def test_reading_a_digest_from_an_absent_collection_is_a_setup_error(
    vector_store: VectorStore,
) -> None:
    """No collection at all is different from an unwritten period, and says so."""
    with pytest.raises(CollectionNotFoundError, match="ensure_collections"):
        get_digest(vector_store, START, END)


def test_summarising_the_same_period_twice_replaces_the_summary(
    vector_store: VectorStore,
) -> None:
    """A period has one digest; a better summary corrects it instead of duplicating it."""
    save_digest(vector_store, _digest(summary="first"))
    save_digest(vector_store, _digest(summary="second"))

    assert vector_store.client.count(DIGESTS_COLLECTION, exact=True).count == 1
    stored = get_digest(vector_store, START, END)
    assert stored is not None
    assert stored.summary == "second"


def test_the_stored_payload_carries_the_indexed_period(vector_store: VectorStore) -> None:
    """Both ends of the period are `DATETIME` fields, so they are written as RFC 3339 days."""
    save_digest(vector_store, _digest())

    records = vector_store.client.retrieve(
        DIGESTS_COLLECTION,
        [digest_point_id(START, END)],
        with_payload=True,
    )

    payload = records[0].payload or {}
    assert payload["period_start"] == "2026-09-01T00:00:00Z"
    assert payload["period_end"] == "2026-09-07T00:00:00Z"
    assert payload["numbers"] == [11, 7]


def test_the_embedded_text_is_the_summary(vector_store: VectorStore) -> None:
    """A later semantic question about a period matches the prose, not the payload fields."""
    digest = _digest()

    assert digest_embedding_text(digest) == digest.summary


def test_a_digest_without_a_summary_embeds_its_numbers(vector_store: VectorStore) -> None:
    """A blank string would map every digest to one point; the numbers are the fallback."""
    assert digest_embedding_text(_digest(summary="   ", numbers=(11, 22))) == "11 22"


def test_a_reversed_period_is_refused() -> None:
    """A period that ends before it starts is a call-site bug, caught at the model."""
    with pytest.raises(ValueError, match="period_start"):
        _digest(start=date(2026, 9, 7), end=date(2026, 9, 1))


def test_a_digest_is_deterministic_in_its_point_id(vector_store: VectorStore) -> None:
    """The same period is the same point, so the identity does not depend on the summary."""
    assert digest_point_id(START, END) == digest_point_id(START, END)


def test_the_store_uses_the_768d_embedder(vector_store: VectorStore) -> None:
    """The fixture pair is 768d/384d, and this collection is built for the wide one."""
    assert isinstance(vector_store.base, FakeEmbedder)
    assert vector_store.base.dimension == 768
