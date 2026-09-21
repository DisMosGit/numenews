"""The one interface the vector layer talks to the local models through.

``Embedder`` is a Protocol rather than an abstract base class, for the same reason
:class:`~numenews.news.protocol.NewsSource` is: the two wrappers share a shape, not an
implementation worth inheriting, and a test double satisfies it without importing ``fastembed`` at
all. ``mypy --strict`` proves both wrappers match the shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """A local text embedder with a fixed output dimension."""

    @property
    def dimension(self) -> int:
        """Width of every vector this embedder returns.

        The vector layer needs it to build a collection with the matching size, so a mismatch
        between an embedder and a collection is caught at creation instead of at the first query.
        """
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in the order the texts were given.

        The result is plain Python floats rather than the backend's array type, because it crosses
        into the Qdrant client and into tests that must not depend on ``numpy``.
        """
        ...
