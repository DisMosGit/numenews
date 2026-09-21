"""Test doubles the vector tests share.

They live in a module rather than in ``conftest.py`` so a test can import the class itself — a test
that wants to say *which* vector a text maps to needs the concrete type, not just the fixture name.
"""

from __future__ import annotations

from collections.abc import Sequence


def basis_vector(dimension: int, index: int) -> list[float]:
    """Return a one-hot vector of ``dimension`` floats with ``index`` set.

    Orthogonal vectors let a vector test say exactly which item is the nearest neighbour without
    loading a model: cosine similarity is 1 against the same axis and 0 against any other.
    """
    vector = [0.0] * dimension
    vector[index] = 1.0
    return vector


class FakeEmbedder:
    """A deterministic stand-in for an ``Embedder``.

    Texts registered in ``vectors`` get the vector they were registered with; anything else maps to
    the first axis, so a test that only cares about filtering needs no registration.
    """

    def __init__(self, dimension: int, vectors: dict[str, list[float]] | None = None) -> None:
        self._dimension = dimension
        self._vectors = dict(vectors or {})
        self.calls: list[list[str]] = []

    @property
    def dimension(self) -> int:
        """Width of every vector this fake returns."""
        return self._dimension

    def register(self, text: str, vector: list[float]) -> None:
        """Return ``vector`` for ``text``, so a test states the geometry it searches in."""
        assert len(vector) == self._dimension
        self._vectors[text] = vector

    def register_axis(self, text: str, index: int) -> None:
        """Map ``text`` to a one-hot vector: cosine similarity is then exactly 1 or exactly 0."""
        self.register(text, basis_vector(self._dimension, index))

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the registered vector per text, recording the batch for assertions."""
        self.calls.append(list(texts))
        fallback = basis_vector(self._dimension, 0)
        return [list(self._vectors.get(text, fallback)) for text in texts]
