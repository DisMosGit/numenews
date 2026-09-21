"""Integration smoke test: Qdrant runs in memory, without Docker.

Phase 0.8 replaces the inline client with the shared ``qdrant_in_memory`` fixture; this test
exists from the first Makefile commit so that ``make test-integration`` is a valid target.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient


@pytest.mark.integration
def test_in_memory_client_starts_empty() -> None:
    """A fresh in-memory Qdrant exposes no collections."""
    client = QdrantClient(":memory:")
    try:
        assert client.get_collections().collections == []
    finally:
        client.close()
