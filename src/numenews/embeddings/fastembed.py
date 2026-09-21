"""The local ``fastembed`` wrappers for the two bge models.

Both models run on the machine through ONNX Runtime — no embedding API is called (AGENTS.md) — and
both are built lazily: the constructor only records where the model lives, and the ONNX session is
created by the first :meth:`~numenews.embeddings.fastembed._FastEmbedder.embed`. Importing the
package, reading settings or creating a :class:`~numenews.vector.client.VectorStore` therefore costs
nothing until something is actually embedded.

Which model is used where is a property of the collection, not of the caller: the short number
contexts of ``numbers`` use the smaller 384d model, while ``news``, ``patterns`` and ``forecasts``
use the 768d one. ``docs/EMBEDDINGS.md`` records the reasoning, and
``Settings.embedding_cache_dir`` is where the downloaded weights are kept.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastembed import TextEmbedding

from numenews.config import Settings

SMALL_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SMALL_DIMENSION = 384
BASE_MODEL_NAME = "BAAI/bge-base-en-v1.5"
BASE_DIMENSION = 768


class _FastEmbedder:
    """Shared shape of the two wrappers: a model name, a dimension and a lazy session."""

    model_name: str
    dimension: int

    def __init__(self, *, cache_dir: Path | None = None, local_files_only: bool = False) -> None:
        self._cache_dir = cache_dir
        self._local_files_only = local_files_only
        self._model: TextEmbedding | None = None

    def _load(self) -> TextEmbedding:
        """Build the ONNX session on first use, then hand the same one back.

        Loading is per instance and never global, so two wrappers cannot share a half-initialised
        model, and the expensive call happens inside :meth:`embed` instead of at import time.

        ``cache_dir=None`` leaves the location to ``fastembed`` itself (its own directory under the
        system temporary directory); production code reaches here through
        :func:`build_embedders`, which always passes ``Settings.embedding_cache_dir``.
        """
        if self._model is None:
            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(self._cache_dir) if self._cache_dir is not None else None,
                local_files_only=self._local_files_only,
            )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in order, as plain ``list[float]``.

        An empty batch returns an empty list without building the model: a caller with nothing to
        embed should not pay for a download or an ONNX session.
        """
        if not texts:
            return []
        vectors = self._load().embed(list(texts))
        return [[float(value) for value in vector] for vector in vectors]


class FastEmbedSmall(_FastEmbedder):
    """``bge-small-en-v1.5``, 384d — the ``numbers`` collection."""

    model_name = SMALL_MODEL_NAME
    dimension = SMALL_DIMENSION


class FastEmbedBase(_FastEmbedder):
    """``bge-base-en-v1.5``, 768d — the ``news``, ``patterns`` and ``forecasts`` collections."""

    model_name = BASE_MODEL_NAME
    dimension = BASE_DIMENSION


def build_embedders(settings: Settings) -> tuple[FastEmbedSmall, FastEmbedBase]:
    """Return both embedders from ``settings``, with neither model loaded yet."""
    return (
        FastEmbedSmall(cache_dir=settings.embedding_cache_dir),
        FastEmbedBase(cache_dir=settings.embedding_cache_dir),
    )
