"""Local embeddings via ``fastembed`` (384d and 768d).

Embeddings are computed on the machine — no external embedding API is allowed (AGENTS.md) — so the
pipeline works without keys and no news text leaves the host. Two ``bge`` models cover the two
jobs: ``bge-small-en-v1.5`` (384d) embeds the short number contexts, and ``bge-base-en-v1.5``
(768d) embeds news items, patterns and forecasts, where the wider vector earns its cost.

Nothing is loaded at import: each wrapper builds its ONNX session inside the first
:meth:`~numenews.embeddings.protocol.Embedder.embed` call, and the weights are downloaded once into
:attr:`Settings.embedding_cache_dir <numenews.config.Settings.embedding_cache_dir>`. See
``docs/EMBEDDINGS.md`` for the model choice and ADR 0003 for the decision.
"""

from __future__ import annotations

from numenews.embeddings.fastembed import (
    BASE_DIMENSION,
    BASE_MODEL_NAME,
    SMALL_DIMENSION,
    SMALL_MODEL_NAME,
    FastEmbedBase,
    FastEmbedSmall,
    build_embedders,
)
from numenews.embeddings.protocol import Embedder

__all__ = [
    "BASE_DIMENSION",
    "BASE_MODEL_NAME",
    "SMALL_DIMENSION",
    "SMALL_MODEL_NAME",
    "Embedder",
    "FastEmbedBase",
    "FastEmbedSmall",
    "build_embedders",
]
