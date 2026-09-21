"""The ``numbers`` collection, over the in-memory engine.

The point of this collection is that a number context is findable by meaning while the number
itself stays filterable, so the tests register the embedding geometry explicitly and then assert
both halves: the vector picks the context, the payload keeps the number and the day.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest
from qdrant_client.models import VectorParams

from numenews.models import NewsId, NumberActivation
from numenews.vector import NUMBERS_COLLECTION, VectorStore, upsert_number_patterns
from numenews.vector.payloads import activation_embedding_text, activation_point_id

from .fakes import FakeEmbedder

pytestmark = pytest.mark.integration


def _activation(
    context: str,
    *,
    number: int = 7,
    news_url: str = "https://example.test/a",
    activated: date = date(2026, 9, 21),
    numerology_value: int | None = None,
) -> NumberActivation:
    """Return an activation with a deterministic news id, so re-upserts hit the same point."""
    return NumberActivation(
        number=number,
        date=activated,
        news_id=NewsId(uuid5(NAMESPACE_URL, news_url)),
        context=context,
        numerology_value=numerology_value,
    )


def test_upserting_creates_a_384d_collection(vector_store: VectorStore) -> None:
    """The short contexts use the small model, and the collection is built for its width."""
    upsert_number_patterns(vector_store, [_activation("seven markets closed higher")])

    info = vector_store.client.get_collection(NUMBERS_COLLECTION)

    assert isinstance(info.config.params.vectors, VectorParams)
    assert info.config.params.vectors.size == 384
    assert info.points_count == 1


def test_an_empty_batch_touches_nothing(vector_store: VectorStore) -> None:
    """Nothing to store is not a reason to create a collection."""
    assert upsert_number_patterns(vector_store, []) == 0
    assert not vector_store.client.collection_exists(NUMBERS_COLLECTION)


def test_the_same_activation_twice_keeps_one_point(vector_store: VectorStore) -> None:
    """One point per `(news item, number)`, so a repeated ingest is idempotent."""
    activation = _activation("seven markets closed higher")

    upsert_number_patterns(vector_store, [activation])
    upsert_number_patterns(vector_store, [activation])

    assert vector_store.client.count(NUMBERS_COLLECTION, exact=True).count == 1


def test_the_context_is_embedded_with_the_small_model(
    vector_store: VectorStore,
    fake_small_embedder: FakeEmbedder,
) -> None:
    """The 384d embedder is the one called, with the context as the text."""
    activation = _activation("seven markets closed higher")

    upsert_number_patterns(vector_store, [activation])

    assert fake_small_embedder.calls == [[activation_embedding_text(activation)]]


def test_the_payload_keeps_the_number_the_day_and_the_context(
    vector_store: VectorStore,
) -> None:
    """Everything `number_history` and the forecast prompt need is in the stored payload."""
    activation = _activation("seven markets closed higher", number=11)

    upsert_number_patterns(vector_store, [activation])

    stored = vector_store.client.retrieve(
        NUMBERS_COLLECTION,
        [activation_point_id(activation)],
        with_payload=True,
    )

    assert stored[0].payload == {
        "number": 11,
        "date": "2026-09-21T00:00:00Z",
        "news_id": str(activation.news_id.root),
        "context": "seven markets closed higher",
    }


def test_the_payload_keeps_the_items_reduced_value_when_it_has_one(
    vector_store: VectorStore,
) -> None:
    """The value is written only when it exists, so "not computed" is never an indexed null."""
    activation = _activation("seven markets closed higher", number=11, numerology_value=11)

    upsert_number_patterns(vector_store, [activation])

    stored = vector_store.client.retrieve(
        NUMBERS_COLLECTION,
        [activation_point_id(activation)],
        with_payload=True,
    )

    assert stored[0].payload == {
        "number": 11,
        "date": "2026-09-21T00:00:00Z",
        "news_id": str(activation.news_id.root),
        "context": "seven markets closed higher",
        "numerology_value": 11,
    }
