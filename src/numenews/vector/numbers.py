"""The ``numbers`` collection: the semantic index over the contexts numbers appear in.

Where ``number_history`` (3.7) answers "when was 7 activated, exactly", this collection answers
"which activations read like *this*". That is why it lives on the 384d model — a number context is
one sentence, and the smaller vector is both enough and cheaper — and why the vector is built from
the context rather than from the number.

The roadmap calls the writer ``upsert_number_patterns``; its argument is
:class:`~numenews.models.NumberActivation`, because the payload it stores is exactly that model
(``number`` + ``context``, plus the date and the news id that make it traceable).
"""

from __future__ import annotations

from collections.abc import Sequence

from qdrant_client.models import PointStruct

from numenews.logging import get_logger
from numenews.models import NumberActivation
from numenews.vector.client import VectorStore
from numenews.vector.collections import NUMBERS_COLLECTION, create_numbers_collection
from numenews.vector.payloads import (
    activation_embedding_text,
    activation_payload,
    activation_point_id,
)

logger = get_logger(__name__)


def upsert_number_patterns(store: VectorStore, activations: Sequence[NumberActivation]) -> int:
    """Embed and store ``activations`` in one batch, returning how many points were written.

    Args:
        store: The connection and the 384d embedder.
        activations: One entry per ``(news item, number)`` pair; its order is preserved.

    Returns:
        The number of points written (``0`` for an empty batch, without touching the collection).
    """
    if not activations:
        return 0
    create_numbers_collection(store.client)
    vectors = store.small.embed([activation_embedding_text(item) for item in activations])
    points = [
        PointStruct(
            id=activation_point_id(activation),
            vector=vector,
            payload=activation_payload(activation),
        )
        for activation, vector in zip(activations, vectors, strict=True)
    ]
    store.client.upsert(NUMBERS_COLLECTION, points, wait=True)
    logger.info("vector.numbers.upserted", activations=len(points))
    return len(points)
