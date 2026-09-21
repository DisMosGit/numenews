"""The Docker Qdrant that ``make dev`` starts.

The in-memory engine is a real Qdrant but ignores payload indexes, so the checks that prove the
schemas of phase 3 belong here. The fixture skips the whole file when the container is not running,
which keeps `make test` green on a machine without Docker; run `make dev` first for the full set.

Running this file provisions the collections in the developer's Qdrant: it creates what is missing
and never deletes anything, exactly like a pipeline run would.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from qdrant_client.models import PayloadSchemaType

from numenews.vector import (
    FORECASTS_COLLECTION,
    NEWS_COLLECTION,
    NUMBERS_COLLECTION,
    PATTERNS_COLLECTION,
    VectorStore,
)
from numenews.vector.collections import (
    FORECASTS_PAYLOAD_INDEXES,
    NEWS_PAYLOAD_INDEXES,
    NUMBERS_PAYLOAD_INDEXES,
    PATTERNS_PAYLOAD_INDEXES,
)

pytestmark = pytest.mark.integration

#: Collection → the payload indexes it must have on a real server. This is the one place where the
#: indexes of phase 3 are checked for real; every collection added to the schema is added here.
EXPECTED_INDEXES: Mapping[str, Mapping[str, PayloadSchemaType]] = {
    NEWS_COLLECTION: NEWS_PAYLOAD_INDEXES,
    NUMBERS_COLLECTION: NUMBERS_PAYLOAD_INDEXES,
    PATTERNS_COLLECTION: PATTERNS_PAYLOAD_INDEXES,
    FORECASTS_COLLECTION: FORECASTS_PAYLOAD_INDEXES,
}


def test_the_configured_qdrant_answers(docker_store: VectorStore) -> None:
    """Roadmap 3.2: the client health-checks the container named by ``Settings.qdrant_url``."""
    docker_store.health_check()


def test_ensuring_collections_is_idempotent(docker_store: VectorStore) -> None:
    """A second run re-declares the same schema instead of failing on an existing collection."""
    docker_store.ensure_collections()
    docker_store.ensure_collections()

    assert docker_store.client.collection_exists(NEWS_COLLECTION)


@pytest.mark.parametrize(
    ("collection", "indexes"),
    sorted(EXPECTED_INDEXES.items()),
    ids=sorted(EXPECTED_INDEXES),
)
def test_a_collection_carries_its_payload_indexes(
    docker_store: VectorStore,
    collection: str,
    indexes: Mapping[str, PayloadSchemaType],
) -> None:
    """Roadmap 3.3 DoD: on a real server — not in local mode — the indexes exist before ingest."""
    docker_store.ensure_collections()

    info = docker_store.client.get_collection(collection)

    assert {key: value.data_type for key, value in info.payload_schema.items()} == dict(indexes)
