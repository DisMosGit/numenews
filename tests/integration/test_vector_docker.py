"""The Docker Qdrant that ``make dev`` starts.

The in-memory engine is a real Qdrant but ignores payload indexes, so the checks that prove the
schemas of phase 3 belong here. The fixture skips the whole file when the container is not running,
which keeps `make test` green on a machine without Docker; run `make dev` first for the full set.
"""

from __future__ import annotations

import pytest

from numenews.vector import VectorStore

pytestmark = pytest.mark.integration


def test_the_configured_qdrant_answers(docker_store: VectorStore) -> None:
    """Roadmap 3.2: the client health-checks the container named by ``Settings.qdrant_url``."""
    docker_store.health_check()
