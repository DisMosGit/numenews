"""The vector store's connection behaviour: health check, in-memory construction, closing.

Nothing here loads a model or needs Docker: the in-memory client is a real Qdrant engine, and the
unreachable-server case only needs a port nothing listens on (nothing listens on port 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from numenews.config import Settings
from numenews.embeddings import Embedder
from numenews.vector import VectorStore, VectorStoreError

pytestmark = pytest.mark.integration


def test_an_in_memory_store_starts_empty(vector_store: VectorStore) -> None:
    """A fresh in-memory instance exposes no collections."""
    assert vector_store.client.get_collections().collections == []


def test_health_check_passes_when_the_server_answers(vector_store: VectorStore) -> None:
    """An in-memory client is always reachable, so the check is a no-op that does not raise."""
    vector_store.health_check()


def test_health_check_reports_an_unreachable_server(
    fake_base_embedder: Embedder,
    fake_small_embedder: Embedder,
) -> None:
    """A server that does not answer becomes one clear error instead of a raw transport failure."""
    store = VectorStore(
        QdrantClient(url="http://127.0.0.1:1", timeout=1),
        base=fake_base_embedder,
        small=fake_small_embedder,
    )
    try:
        with pytest.raises(VectorStoreError, match="health check failed"):
            store.health_check()
    finally:
        store.close()


def test_from_settings_reports_an_unreachable_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`from_settings` reads QDRANT_URL and fails loudly when the server is not there."""
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:1")
    # The working directory is moved so the developer's `.env` cannot override the test's URL.
    monkeypatch.chdir(tmp_path)

    with pytest.raises(VectorStoreError, match="make dev"):
        VectorStore.from_settings(Settings())


def test_the_store_closes_as_a_context_manager(vector_store: VectorStore) -> None:
    """The `with` form closes the client, so a one-shot command leaks no connections."""
    with vector_store as store:
        assert store is vector_store

    with pytest.raises(RuntimeError):
        vector_store.client.get_collections()
