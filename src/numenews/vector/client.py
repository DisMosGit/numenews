"""The Qdrant connection the whole vector layer shares.

One :class:`VectorStore` bundles the three things every collection operation needs: the client
pointed at ``Settings.qdrant_url``, the 768d embedder and the 384d embedder. Passing it around
instead of the client alone means a collection function cannot be called with the wrong embedder,
and a test can build the same object over ``QdrantClient(":memory:")`` without a server or a model.

The layer is synchronous on purpose: ``QdrantClient`` — not ``AsyncQdrantClient`` — is what the
in-memory collections of the test suite support, and the callers that live in async code (the
pipeline of phase 5, the MCP tools of phase 6) can offload a blocking call to a worker thread. ADR
0003 records the decision.
"""

from __future__ import annotations

from types import TracebackType

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from numenews.config import Settings
from numenews.embeddings import Embedder, build_embedders
from numenews.logging import get_logger
from numenews.vector.errors import VectorStoreError

logger = get_logger(__name__)


class VectorStore:
    """A Qdrant client with the two local embedders the collections are built for."""

    def __init__(self, client: QdrantClient, *, base: Embedder, small: Embedder) -> None:
        self._client = client
        self._base = base
        self._small = small

    @classmethod
    def from_settings(cls, settings: Settings) -> VectorStore:
        """Connect to the Qdrant named by ``settings`` and prove it answers.

        Neither embedder is loaded here — :func:`~numenews.embeddings.build_embedders` only records
        the cache directory — so constructing a store costs no download and no ONNX session.

        Raises:
            VectorStoreError: when the server does not answer the health check, which is the
                first thing worth failing on: every later call would fail with a worse message.
        """
        small, base = build_embedders(settings)
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        store = cls(
            QdrantClient(url=str(settings.qdrant_url), api_key=api_key),
            base=base,
            small=small,
        )
        store.health_check()
        return store

    @classmethod
    def in_memory(cls, *, base: Embedder, small: Embedder) -> VectorStore:
        """Return a store over ``QdrantClient(":memory:")``, for tests and local experiments.

        No health check is needed or wanted: an in-memory client cannot be unreachable.
        """
        return cls(QdrantClient(":memory:"), base=base, small=small)

    @property
    def client(self) -> QdrantClient:
        """The underlying Qdrant client, for the operations that need it directly."""
        return self._client

    @property
    def base(self) -> Embedder:
        """The 768d embedder of ``news``, ``patterns`` and ``forecasts``."""
        return self._base

    @property
    def small(self) -> Embedder:
        """The 384d embedder of ``numbers``."""
        return self._small

    def health_check(self) -> None:
        """Raise :class:`VectorStoreError` unless the server returns its collection list.

        ``get_collections`` is the cheapest call that proves both reachability and a working HTTP
        API, and its answer is what a caller would fetch next anyway.

        Raises:
            VectorStoreError: when the request fails or the server answers with an error status.
        """
        try:
            collections = self._client.get_collections().collections
        except (ResponseHandlingException, UnexpectedResponse) as error:
            raise VectorStoreError(
                f"Qdrant health check failed ({error}): start the server with `make dev` and "
                "check QDRANT_URL in .env"
            ) from error
        logger.debug("vector.health_check.ok", collections=len(collections))

    def close(self) -> None:
        """Close the underlying client and release its connections."""
        self._client.close()

    def __enter__(self) -> VectorStore:
        """Return the store itself, so it can be used as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the store on the way out, whatever happened inside the block."""
        self.close()
