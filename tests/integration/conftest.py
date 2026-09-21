"""Integration fixtures.

Qdrant runs in memory here (`QdrantClient(":memory:")`), so these tests exercise the vector
layer without Docker; the container from `docker-compose.yml` is exercised by the manual
checks in ROADMAP.md and, from phase 3, by the client's health check. The news layer needs no
service at all: `respx` answers its HTTP calls, while the `news_client` fixture exercises the real
`hishel` cache against a sqlite file in the test's temporary directory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from hishel.httpx import AsyncCacheClient
from qdrant_client import QdrantClient

from numenews.config import Settings
from numenews.news import build_news_client

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "news"


@pytest.fixture
def qdrant_in_memory() -> Iterator[QdrantClient]:
    """Yield an in-memory Qdrant client and close it after the test."""
    client = QdrantClient(":memory:")
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
async def news_client(settings: Settings) -> AsyncIterator[AsyncCacheClient]:
    """Yield the cached news client, with its database inside the temporary cache directory."""
    client = build_news_client(settings)
    try:
        yield client
    finally:
        await client.aclose()


def news_fixture(name: str) -> bytes:
    """Return the raw bytes of a recorded API response fixture."""
    return (FIXTURES_DIR / name).read_bytes()
