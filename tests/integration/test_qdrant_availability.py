"""The `qdrant_in_memory` fixture: vector tests need no Docker."""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient


@pytest.mark.integration
def test_in_memory_client_starts_empty(qdrant_in_memory: QdrantClient) -> None:
    """A fresh in-memory instance exposes no collections."""
    assert qdrant_in_memory.get_collections().collections == []
