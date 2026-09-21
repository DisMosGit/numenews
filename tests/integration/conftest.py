"""Integration fixtures.

Qdrant runs in memory here (`QdrantClient(":memory:")`), so these tests exercise the vector
layer without Docker; the container from `docker-compose.yml` is exercised by the manual
checks in ROADMAP.md and, from phase 3, by the client's health check. The news layer needs no
service at all: `respx` answers its HTTP calls, while the `news_client` fixture exercises the real
`hishel` cache against a sqlite file in the test's temporary directory. The embedding model is
genuinely local but not free: `small_embedder`/`base_embedder` download the ~286 MB of weights on
the first run and reuse them from `.cache/fastembed` afterwards.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from hishel.httpx import AsyncCacheClient
from qdrant_client import QdrantClient

from numenews.config import Settings
from numenews.embeddings import FastEmbedBase, FastEmbedSmall
from numenews.news import build_news_client, http
from numenews.vector import VectorStore, VectorStoreError

from .fakes import FakeEmbedder

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "news"

# `fastembed` keeps the two bge ONNX models (~286 MB together) in this directory. It lives inside
# the project (and is gitignored) so that a second run starts from the cache instead of downloading
# again, and the path is absolute on purpose: the `settings` fixture moves the working directory, so
# a relative one would download the weights per test.
EMBEDDING_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "fastembed"


@pytest.fixture
def fake_base_embedder() -> FakeEmbedder:
    """Return a fake 768d embedder for the news, patterns and forecasts collections."""
    return FakeEmbedder(768)


@pytest.fixture
def fake_small_embedder() -> FakeEmbedder:
    """Return a fake 384d embedder for the numbers collection."""
    return FakeEmbedder(384)


@pytest.fixture
def vector_store(
    fake_base_embedder: FakeEmbedder,
    fake_small_embedder: FakeEmbedder,
) -> Iterator[VectorStore]:
    """Yield an in-memory store with fake embedders: no Docker, no model, real Qdrant semantics."""
    store = VectorStore.in_memory(base=fake_base_embedder, small=fake_small_embedder)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture(scope="session")
def docker_store() -> Iterator[VectorStore]:
    """Yield a store over the Qdrant ``make dev`` starts, skipping when it is not running.

    Unlike every other fixture here, this one reads the developer's own configuration — testing the
    configured container is the point. Payload indexes are the one thing the in-memory engine
    ignores, so the checks that depend on them live in `test_vector_docker.py`.
    """
    try:
        store = VectorStore.from_settings(Settings())
    except VectorStoreError as error:
        pytest.skip(f"Qdrant from `make dev` is not reachable: {error}")
    try:
        yield store
    finally:
        store.close()


@pytest.fixture(scope="session")
def small_embedder() -> FastEmbedSmall:
    """Return the 384d embedder; the model is loaded, and on the first run downloaded, on demand."""
    return FastEmbedSmall(cache_dir=EMBEDDING_CACHE_DIR)


@pytest.fixture(scope="session")
def base_embedder() -> FastEmbedBase:
    """Return the 768d embedder; the model is loaded, and on the first run downloaded, on demand."""
    return FastEmbedBase(cache_dir=EMBEDDING_CACHE_DIR)


@pytest.fixture
def instant_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the retry backoff with an immediate retry, so the suite spends no seconds asleep."""
    monkeypatch.setattr(http, "_wait", lambda retry_state: 0.0)


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
