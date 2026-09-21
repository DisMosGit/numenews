"""Qdrant: client, collections, payload indexes and hybrid search.

Payload indexes are created before any ingest, and a filter goes inside ``Prefetch`` in multi-stage
queries. :class:`~numenews.vector.client.VectorStore` owns the connection and the two local
embedders; the collection modules build on it, one module per collection, and this package's
``__all__`` is the surface the pipeline (phase 5) and the MCP tools (phase 6) call.
"""

from __future__ import annotations

from numenews.vector.client import VectorStore
from numenews.vector.collections import (
    FORECASTS_COLLECTION,
    NEWS_COLLECTION,
    NUMBER_HISTORY_COLLECTION,
    NUMBERS_COLLECTION,
    PATTERNS_COLLECTION,
    create_forecasts_collection,
    create_news_collection,
    create_number_history_collection,
    create_numbers_collection,
    create_patterns_collection,
    ensure_collections,
    require_collection,
)
from numenews.vector.errors import CollectionNotFoundError, VectorStoreError
from numenews.vector.filters import build_news_filter
from numenews.vector.forecasts import get_forecast, save_forecast
from numenews.vector.history import get_history, record_activation
from numenews.vector.news import search_news, upsert_news
from numenews.vector.numbers import upsert_number_patterns
from numenews.vector.patterns import find_similar_patterns, save_pattern

__all__ = [
    "FORECASTS_COLLECTION",
    "NEWS_COLLECTION",
    "NUMBERS_COLLECTION",
    "NUMBER_HISTORY_COLLECTION",
    "PATTERNS_COLLECTION",
    "CollectionNotFoundError",
    "VectorStore",
    "VectorStoreError",
    "build_news_filter",
    "create_forecasts_collection",
    "create_news_collection",
    "create_number_history_collection",
    "create_numbers_collection",
    "create_patterns_collection",
    "ensure_collections",
    "find_similar_patterns",
    "get_forecast",
    "get_history",
    "record_activation",
    "require_collection",
    "save_forecast",
    "save_pattern",
    "search_news",
    "upsert_news",
    "upsert_number_patterns",
]
