"""Fixtures for the ragas evaluation (phase 9).

The eval has one requirement the rest of the suite deliberately does not: it must talk to the
developer's configured LLM endpoint, so it reads :class:`~numenews.config.Settings` straight from
the environment instead of using the hermetic ``settings`` fixture of ``tests/conftest.py``.

`ragas` is installed only in ``.venv-eval`` (ADR 0013) and is not part of ``uv.lock``, so
:func:`pytest_ignore_collect` keeps the metric module out of collection in the main environment: a
bare ``uv run pytest`` collects the deterministic retrieval test and ignores the ragas one instead
of failing to import it.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from numenews.config import Settings
from numenews.models import NewsItem
from numenews.vector import VectorStore

from .harness import EvalQuestion, build_store, load_news, load_questions

#: The module that needs `ragas`; the others run everywhere.
RAGAS_MODULE = "test_rag.py"

#: ragas reports usage to its own endpoint by default; this project is local-only, and the eval is
#: about the corpus, not about telemetry.
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    """Ignore the ragas metrics when `ragas` is not installed in this environment."""
    if collection_path.name != RAGAS_MODULE:
        return False
    return importlib.util.find_spec("ragas") is None


@pytest.fixture(scope="session")
def eval_settings() -> Settings:
    """Return the developer's real settings: the eval is the suite that must reach an endpoint."""
    return Settings()


@pytest.fixture(scope="session")
def eval_news() -> dict[str, NewsItem]:
    """Return the fixture corpus, validated, keyed by slug."""
    return load_news()


@pytest.fixture(scope="session")
def eval_questions(eval_news: dict[str, NewsItem]) -> list[EvalQuestion]:
    """Return the fixture questions, checked against the corpus."""
    return load_questions(eval_news)


@pytest.fixture(scope="session")
def eval_store(eval_news: dict[str, NewsItem]) -> Iterator[VectorStore]:
    """Yield the in-memory store holding the corpus, embedded with the real local models."""
    store = build_store(eval_news.values())
    try:
        yield store
    finally:
        store.close()
