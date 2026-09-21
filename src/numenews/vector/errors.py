"""Failures the vector layer reports.

The shape follows ``news/errors.py``: one base class so a caller that only needs to know the store
is unusable catches a single thing, plus one subclass for the failure that actually has a fix. The
distinction matters to the pipeline (phase 5): "Qdrant is not running" is an environment problem,
while "the collection was never created" is a missing setup step.
"""

from __future__ import annotations


class VectorStoreError(Exception):
    """Base class for every failure inside the vector layer."""


class CollectionNotFoundError(VectorStoreError):
    """A collection was read before it existed.

    Raised instead of the raw ``ValueError`` (local mode) or 404 (server) so a caller gets one
    message that says what to do: create it with ``VectorStore.ensure_collections``, which every
    write path already calls before its first upsert.
    """
