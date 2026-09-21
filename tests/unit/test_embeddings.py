"""The ``fastembed`` wrapper's own behaviour, with the model backend faked.

Loading a real ONNX session belongs to the integration suite; what is under test here is the
wrapper around it — nothing is built at construction, the session is built once and reused, the
output is ``list[list[float]]`` whatever the backend yields, and an empty batch never touches the
model at all. That is also what keeps this file fast: no weights, no network.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from numenews.config import Settings
from numenews.embeddings import BASE_DIMENSION, SMALL_DIMENSION, FastEmbedBase, FastEmbedSmall
from numenews.embeddings import fastembed as fastembed_module


class _FakeSession:
    """One fake ONNX session: it records the batches it was asked to embed."""

    def __init__(self, *, model_name: str, cache_dir: str | None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> Iterator[list[float]]:
        """Return one short vector per text, in order."""
        self.calls.append(list(texts))
        return iter([[0.5, 0.25, 0.125] for _ in texts])


class _FakeBackend:
    """Stand-in for ``fastembed.TextEmbedding`` that records how sessions were built."""

    def __init__(self) -> None:
        self.sessions: list[_FakeSession] = []

    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str | None,
        local_files_only: bool,
    ) -> _FakeSession:
        """Return a new fake session; ``local_files_only`` is recorded for the assertion below."""
        assert local_files_only is False
        session = _FakeSession(model_name=model_name, cache_dir=cache_dir)
        self.sessions.append(session)
        return session


@pytest.fixture
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> _FakeBackend:
    """Replace ``fastembed.TextEmbedding`` with the recording fake for one test."""
    fake = _FakeBackend()
    monkeypatch.setattr(fastembed_module, "TextEmbedding", fake)
    return fake


def test_nothing_is_loaded_until_the_first_embed(fake_backend: _FakeBackend) -> None:
    """Constructing a wrapper records the cache directory but builds no model."""
    embedder = FastEmbedBase()

    assert fake_backend.sessions == []
    assert embedder._model is None  # the lazy field is the behaviour under test

    embedder.embed(["hello"])

    assert len(fake_backend.sessions) == 1


def test_the_model_is_built_once_and_reused(fake_backend: _FakeBackend) -> None:
    """A second batch goes through the session the first batch created."""
    embedder = FastEmbedSmall()

    embedder.embed(["one"])
    embedder.embed(["two", "three"])

    assert len(fake_backend.sessions) == 1
    assert fake_backend.sessions[0].calls == [["one"], ["two", "three"]]


def test_an_empty_batch_returns_nothing_and_loads_nothing(fake_backend: _FakeBackend) -> None:
    """Embedding nothing is not a reason to download or build a model."""
    embedder = FastEmbedBase()

    assert embedder.embed([]) == []
    assert fake_backend.sessions == []


def test_vectors_are_plain_floats_whatever_the_backend_yields(
    fake_backend: _FakeBackend,
) -> None:
    """The wrapper converts each backend value into a Python float, not the array's scalar type."""
    vectors = FastEmbedBase().embed(["hello"])

    assert len(vectors) == 1
    assert all(isinstance(value, float) for value in vectors[0])
    assert vectors[0] == [0.5, 0.25, 0.125]


def test_the_two_wrappers_declare_their_model_and_dimension() -> None:
    """The names and widths the collections are built with live on the wrappers."""
    assert FastEmbedSmall.model_name == "BAAI/bge-small-en-v1.5"
    assert FastEmbedSmall.dimension == SMALL_DIMENSION == 384
    assert FastEmbedBase.model_name == "BAAI/bge-base-en-v1.5"
    assert FastEmbedBase.dimension == BASE_DIMENSION == 768


def test_build_embedders_passes_the_settings_cache_dir(
    fake_backend: _FakeBackend,
    settings: Settings,
) -> None:
    """Production wiring puts the weights where the configuration says."""
    small, base = fastembed_module.build_embedders(settings)

    small.embed(["one"])
    base.embed(["two"])

    assert [session.cache_dir for session in fake_backend.sessions] == [
        str(settings.embedding_cache_dir),
        str(settings.embedding_cache_dir),
    ]


def test_both_wrappers_can_share_one_cache_directory() -> None:
    """Nothing in the wrappers forces a second download location."""
    cache_dir = Path("/tmp/nothing-here")

    small = FastEmbedSmall(cache_dir=cache_dir)
    base = FastEmbedBase(cache_dir=cache_dir)

    assert small._cache_dir == base._cache_dir == cache_dir  # wiring under test
