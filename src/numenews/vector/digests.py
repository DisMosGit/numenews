"""The ``digests`` collection: the news outside the window, compressed into a period.

Roadmap 5.5 keeps the recent seven days raw — that is what the agents read — and summarises anything
older into one numerological digest, so the project does not have to keep every article of every
month in a prompt. This collection is where the summary goes.

It is vector-backed with the same 768d model as ``news``, ``patterns`` and ``forecasts``: the point
of a digest is to be *found* later ("what did the run-up to September look like"), which is a
semantic question about its prose. The period is the identity — two summarisations of the same range
are the same digest — and it is indexed as both ends of a ``DATETIME`` range.
"""

from __future__ import annotations

from datetime import date

from qdrant_client.models import PointStruct

from numenews.logging import get_logger
from numenews.models import Digest
from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    DIGESTS_COLLECTION,
    create_digests_collection,
    require_collection,
)
from numenews.vector.errors import VectorStoreError
from numenews.vector.payloads import (
    digest_embedding_text,
    digest_from_payload,
    digest_payload,
    digest_point_id,
)

logger = get_logger(__name__)


def save_digest(store: VectorStore, digest: Digest) -> None:
    """Embed and store one digest under its period.

    Args:
        store: The connection and the 768d embedder.
        digest: The summary to persist; its period selects the point, so a second save for the same
            period replaces the first.
    """
    create_digests_collection(store.client)
    vector = store.base.embed([digest_embedding_text(digest)])[0]
    store.client.upsert(
        DIGESTS_COLLECTION,
        [
            PointStruct(
                id=digest_point_id(digest.period_start, digest.period_end),
                vector=vector,
                payload=digest_payload(digest),
            )
        ],
        wait=True,
    )
    logger.info(
        "vector.digest.saved",
        period_start=digest.period_start.isoformat(),
        period_end=digest.period_end.isoformat(),
        numbers=len(digest.numbers),
    )


def get_digest(store: VectorStore, start: date, end: date) -> Digest | None:
    """Return the digest of ``start..end``, or ``None`` when that period was never summarised.

    Args:
        store: The connection and the 768d embedder.
        start: First day of the period.
        end: Last day of the period.

    Raises:
        CollectionNotFoundError: when the ``digests`` collection was never created — the caller
            asked for a summary in a store that has none, which is different from an unwritten one.
        VectorStoreError: when the stored point has no payload, which would mean it was written by
            something other than :func:`save_digest`.

    Returns:
        The stored digest, or ``None``.
    """
    require_collection(store.client, DIGESTS_COLLECTION)
    records = store.client.retrieve(
        DIGESTS_COLLECTION,
        [digest_point_id(start, end)],
        with_payload=True,
    )
    if not records:
        return None
    payload = records[0].payload
    if payload is None:
        raise VectorStoreError(f"stored digest for {start.isoformat()} has no payload")
    return digest_from_payload(payload)
