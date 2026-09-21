"""Roadmap 3.1 against the real ONNX models.

The only tests that load — and on the first run download, ~286 MB into ``.cache/fastembed`` — the
two ``bge`` models. They are marked ``integration`` because they need those files on disk, not
because they need a service, and they are the evidence for the phase's DoD:
``FastEmbedBase().embed(["hello"])`` has to come back as 768 floats.
"""

from __future__ import annotations

import pytest

from numenews.embeddings import BASE_DIMENSION, SMALL_DIMENSION, FastEmbedBase, FastEmbedSmall

pytestmark = pytest.mark.integration

SENTENCES = ("the sun rises over the city", "quantum physics is hard", "числа повсюду")


def test_small_embedder_returns_384_float_vectors(small_embedder: FastEmbedSmall) -> None:
    """The 384d model produces one 384-wide vector of floats per text."""
    vectors = small_embedder.embed(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == SMALL_DIMENSION == 384
    assert all(isinstance(value, float) for value in vectors[0])


def test_base_embedder_returns_768_float_vectors(base_embedder: FastEmbedBase) -> None:
    """Roadmap 3.1 DoD: ``FastEmbedBase().embed(["hello"])`` is a list of 768 floats."""
    vectors = base_embedder.embed(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == BASE_DIMENSION == 768
    assert all(isinstance(value, float) for value in vectors[0])


def test_the_same_text_embeds_to_the_same_vector(base_embedder: FastEmbedBase) -> None:
    """The model is deterministic: two calls are identical, so a stored vector stays comparable."""
    first = base_embedder.embed(["the sun rises over the city"])
    second = base_embedder.embed(["the sun rises over the city"])

    assert first == second


def test_a_batch_keeps_the_order_of_its_texts(base_embedder: FastEmbedBase) -> None:
    """Batching is not allowed to shuffle: a batch row equals the single-text embedding."""
    batch = base_embedder.embed(["a completely unrelated sentence", SENTENCES[0]])

    assert batch[1] == base_embedder.embed([SENTENCES[0]])[0]
    assert batch[0] != batch[1]


def test_an_empty_batch_returns_nothing(base_embedder: FastEmbedBase) -> None:
    """A caller with nothing to embed gets nothing back, not a shape error."""
    assert base_embedder.embed([]) == []
