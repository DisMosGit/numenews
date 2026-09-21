"""Qdrant: client, the five collections, payload indexes and hybrid search.

Payload indexes are created before any ingest, and a filter goes inside ``Prefetch`` in multi-stage
queries. :class:`~numenews.vector.client.VectorStore` owns the connection and the two local
embedders; the collection modules build on it, one module per collection.
"""

from __future__ import annotations

from numenews.vector.client import VectorStore
from numenews.vector.errors import CollectionNotFoundError, VectorStoreError

__all__ = [
    "CollectionNotFoundError",
    "VectorStore",
    "VectorStoreError",
]
