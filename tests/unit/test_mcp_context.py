"""The application context: lazy, memoized, single-flight (ROADMAP 6.1).

The server must start without Qdrant or an LLM endpoint, so nothing is built until a tool asks for
it; and once built, a collaborator is shared by every later call — two stores over the same
collections would be two views of the same state. These tests check both properties with injected
doubles, plus the ``aclose`` contract the lifespan relies on.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import cast

import pytest
from hishel.httpx import AsyncCacheClient
from pydantic import SecretStr

from numenews.agents import ExtractNumbersAgent
from numenews.config import Settings
from numenews.mcp.context import AppContext
from numenews.news import NewsAggregator, build_news_client
from numenews.pipeline import Pipeline
from numenews.vector import VectorStore

from .pipeline_fakes import (
    FakeStore,
    FrozenClock,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)


@pytest.fixture
def context_settings(settings: Settings) -> Settings:
    """Return hermetic settings with an LLM endpoint, so agent construction needs no key on disk."""
    return settings.model_copy(update={"openai_api_key": SecretStr("test-key")})


def _pipeline(store: FakeStore) -> Pipeline:
    """Return a pipeline whose every collaborator is a test double."""
    extract, _ = extract_agent([11])
    patterns, _ = pattern_agent([])
    forecaster, _ = forecast_agent()
    summarizer, _ = summarize_agent()
    return Pipeline(
        store=store,  # type: ignore[arg-type]  # FakeStore stands in for a VectorStore
        extract=extract,
        patterns=patterns,
        forecast_agent=forecaster,
        summarizer=summarizer,
        fetcher=fetcher_returning([]),
        clock=FrozenClock(),
    )


def test_the_context_exposes_the_settings_it_was_given(settings: Settings) -> None:
    """Settings are the one thing every built collaborator is derived from."""
    assert AppContext(settings).settings is settings


async def test_injected_collaborators_are_returned_unchanged(settings: Settings) -> None:
    """A test that injects everything never triggers a build."""
    store = FakeStore()
    pipeline = _pipeline(store)
    extract, _ = extract_agent([11])
    aggregator = NewsAggregator([])
    context = AppContext(
        settings,
        store=store,  # type: ignore[arg-type]  # FakeStore stands in for a VectorStore
        extract=extract,
        pipeline=pipeline,
        aggregator=aggregator,
    )

    assert await context.pipeline() is pipeline
    assert await context.extract() is extract
    assert await context.news() is aggregator
    assert await context.store() is pipeline.store


async def test_an_injected_pipeline_serves_the_store_accessor(settings: Settings) -> None:
    """A pipeline injected without a store still gives the storage tools the same store."""
    store = FakeStore()
    context = AppContext(settings, pipeline=_pipeline(store))

    assert await context.store() is store  # type: ignore[comparison-overlap]  # test double


async def test_a_store_is_built_only_once_even_under_concurrency(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two tool calls arriving together must not build two Qdrant clients."""
    built: list[Settings] = []
    store = FakeStore()

    def fake_from_settings(cls: type[VectorStore], resolved: Settings) -> VectorStore:
        built.append(resolved)
        return store  # type: ignore[return-value]  # FakeStore stands in for a VectorStore

    monkeypatch.setattr(VectorStore, "from_settings", classmethod(fake_from_settings))
    context = AppContext(settings)

    first, second = await asyncio.gather(context.store(), context.store())

    assert first is second
    assert built == [settings]


async def test_a_built_pipeline_reuses_the_contexts_store_and_extract_agent(
    context_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lazy build wires the same objects the standalone accessors would return."""
    store = FakeStore()
    monkeypatch.setattr(
        VectorStore,
        "from_settings",
        classmethod(lambda cls, resolved: store),
    )
    context = AppContext(context_settings)

    pipeline = await context.pipeline()

    assert pipeline.store is cast("VectorStore", store)
    assert pipeline.extract is await context.extract()
    assert await context.store() is cast("VectorStore", store)
    assert await context.pipeline() is pipeline
    assert isinstance(await context.extract(), ExtractNumbersAgent)


async def test_the_news_aggregator_shares_the_injected_client(
    settings: Settings,
) -> None:
    """One cached client serves every tool call, and ``aclose`` closes it."""
    client: AsyncCacheClient = build_news_client(settings)
    context = AppContext(settings, client=client)

    aggregator = await context.news()

    assert aggregator is await context.news()
    assert aggregator.sources  # GDELT needs no key, so one source is always configured
    await context.aclose()
    assert client.is_closed


async def test_the_context_builds_the_news_client_when_none_is_injected(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The long-lived client is the context's to create, and its to close."""
    built: list[AsyncCacheClient] = []

    def spy(resolved: Settings) -> AsyncCacheClient:
        client = build_news_client(resolved)
        built.append(client)
        return client

    monkeypatch.setattr("numenews.mcp.context.build_news_client", spy)
    context = AppContext(settings)

    aggregator = await context.news()
    await context.aclose()

    assert aggregator.sources
    assert len(built) == 1
    assert built[0].is_closed


async def test_aclose_closes_a_standalone_store(settings: Settings) -> None:
    """A store built by ``store()`` alone has no pipeline to close it, so the context does."""
    store = FakeStore()
    context = AppContext(settings, store=store)  # type: ignore[arg-type]  # test double

    await context.store()
    await context.aclose()

    assert store.closed


async def test_aclose_closes_the_pipeline_store_and_is_idempotent(settings: Settings) -> None:
    """The lifespan calls it on the way out; a second call must be harmless."""
    store = FakeStore()
    context = AppContext(settings, pipeline=_pipeline(store))

    await context.aclose()
    await context.aclose()

    assert store.closed


async def test_nothing_is_closed_when_nothing_was_built(settings: Settings) -> None:
    """A server that never served a request has nothing to tear down."""
    await AppContext(settings).aclose()


@pytest.fixture(autouse=True)
def _no_surprise_builds(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail loudly if a test reaches a real service: the suite has neither Qdrant nor an LLM."""
    monkeypatch.setattr(
        VectorStore,
        "from_settings",
        classmethod(lambda cls, resolved: pytest.fail("a test tried to build a real VectorStore")),
    )
    yield
