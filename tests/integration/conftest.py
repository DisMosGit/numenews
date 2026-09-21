"""Integration fixtures.

Qdrant runs in memory here (`QdrantClient(":memory:")`), so these tests exercise the vector
layer without Docker; the container from `docker-compose.yml` is exercised by the manual
checks in ROADMAP.md and, from phase 3, by the client's health check.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from qdrant_client import QdrantClient


@pytest.fixture
def qdrant_in_memory() -> Iterator[QdrantClient]:
    """Yield an in-memory Qdrant client and close it after the test."""
    client = QdrantClient(":memory:")
    try:
        yield client
    finally:
        client.close()
