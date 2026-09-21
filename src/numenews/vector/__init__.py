"""Qdrant: client, collections, payload indexes and hybrid search.

Payload indexes are created before any ingest, and a filter goes inside ``Prefetch`` in multi-stage
queries. :class:`~numenews.vector.client.VectorStore` owns the connection and the two local
embedders; the collection modules build on it, one module per collection, and this package's
``__all__`` is the surface the pipeline (phase 5) and the MCP tools (phase 6) call.
"""

from __future__ import annotations

from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    NEWS_COLLECTION,
    NUMBERS_COLLECTION,
    create_news_collection,
    create_numbers_collection,
    ensure_collections,
    require_collection,
)
from numenews.vector.errors import CollectionNotFoundError, VectorStoreError
from numenews.vector.filters import build_news_filter
from numenews.vector.news import search_news, upsert_news
from numenews.vector.numbers import upsert_number_patterns

__all__ = [
    "NEWS_COLLECTION",
    "NUMBERS_COLLECTION",
    "CollectionNotFoundError",
    "VectorStore",
    "VectorStoreError",
    "build_news_filter",
    "create_news_collection",
    "create_numbers_collection",
    "ensure_collections",
    "require_collection",
    "search_news",
    "upsert_news",
    "upsert_number_patterns",
]
