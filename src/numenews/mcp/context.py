"""The application context the MCP tools share: one place that knows how to build the layers.

An MCP server is a long-lived process, so building a ``QdrantClient``, an embedding session or an
agent per tool call would be both slow and wrong — two stores would hold two views of the same
collections. Everything a call needs is therefore built once and reached through the lifespan
object, which is what roadmap 6.1 calls dependency injection through ``AppContext``.

The construction is *lazy*. The server must start even when neither Qdrant nor an LLM endpoint is
reachable (roadmap 6.1's DoD is "starts and does not fail on connection"), so nothing is built until
a tool that needs it runs; a failure then becomes a ``ToolError`` that says what to fix, instead of
a process that refuses to boot. Laziness also gives every tool the smallest prerequisite set:

* ``compute_numerology`` / ``check_master_numbers`` need nothing;
* ``extract_numbers`` needs an LLM endpoint only;
* ``fetch_news`` needs the news APIs only (GDELT alone works without keys);
* ``query_qdrant`` / ``save_pattern`` / ``get_history`` need Qdrant only;
* ``find_patterns`` / ``build_forecast`` need Qdrant and an LLM endpoint.

Every accessor is asynchronous and memoizes under one lock, so two concurrent tool calls cannot
build two stores. The blocking part of a construction — the Qdrant health check inside
``VectorStore.from_settings``, and the store and agents the ``Pipeline`` assembles — is offloaded
with :func:`asyncio.to_thread`, the same bridge the pipeline uses for the synchronous vector layer
(ADR 0003). The collaborators are injectable, which is how the tests run without a server, a key or
a model.
"""

from __future__ import annotations

import asyncio

from hishel.httpx import AsyncCacheClient

from numenews.agents import ExtractNumbersAgent
from numenews.config import Settings
from numenews.news import NewsAggregator, build_news_client
from numenews.pipeline import Pipeline
from numenews.vector import VectorStore


class AppContext:
    """What the server builds once: settings and the collaborators a tool call reaches.

    Args:
        settings: The validated configuration the defaults are built from.
        store: A vector store to use instead of building one. Injected by tests; never replaced.
        extract: An ``ExtractNumbersAgent`` to use instead of building one. Injected by tests.
        pipeline: A ``Pipeline`` to use instead of building one; its store then serves
            :meth:`store` too, so an injected pipeline and an injected store never disagree.
        aggregator: A ``NewsAggregator`` to use instead of building one. Injected by tests.
        client: The long-lived cached HTTP client the news adapters share. Built on first use when
            omitted, and closed by :meth:`aclose`.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        store: VectorStore | None = None,
        extract: ExtractNumbersAgent | None = None,
        pipeline: Pipeline | None = None,
        aggregator: NewsAggregator | None = None,
        client: AsyncCacheClient | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._extract = extract
        self._pipeline = pipeline
        self._aggregator = aggregator
        self._client = client
        self._lock = asyncio.Lock()

    @property
    def settings(self) -> Settings:
        """The configuration the default collaborators are built from."""
        return self._settings

    async def store(self) -> VectorStore:
        """Return the vector store, building and health-checking it on first use.

        Raises:
            VectorStoreError: when Qdrant does not answer; the message names ``make dev``.
        """
        async with self._lock:
            return await self._store_locked()

    async def extract(self) -> ExtractNumbersAgent:
        """Return the numbers reader, building it on first use.

        Raises:
            LLMConfigurationError: when neither ``OPENAI_API_KEY`` nor ``OPENAI_BASE_URL`` is set.
        """
        async with self._lock:
            return self._extract_locked()

    async def pipeline(self) -> Pipeline:
        """Return the RAG pipeline, building its store and agents on first use.

        The pipeline reuses this context's store and extract agent, so a tool that asks for the
        store and a tool that asks for the pipeline always see the same two objects.
        """
        async with self._lock:
            if self._pipeline is None:
                store = await self._store_locked()
                extract = self._extract_locked()
                self._pipeline = await asyncio.to_thread(
                    Pipeline, settings=self._settings, store=store, extract=extract
                )
            return self._pipeline

    async def news(self) -> NewsAggregator:
        """Return the news aggregator, building the shared cached client on first use."""
        async with self._lock:
            return self._news_locked()

    async def aclose(self) -> None:
        """Close everything this context built; safe to call twice.

        The news client is closed last: the pipeline owns the store and closes it, and a store built
        by :meth:`store` alone is closed here because nothing else will.
        """
        if self._pipeline is not None:
            self._pipeline.close()
        elif self._store is not None:
            self._store.close()
        if self._client is not None:
            await self._client.aclose()

    async def _store_locked(self) -> VectorStore:
        """Return the store, building it if needed. The caller holds the lock."""
        if self._store is None:
            if self._pipeline is not None:
                self._store = self._pipeline.store
            else:
                self._store = await asyncio.to_thread(VectorStore.from_settings, self._settings)
        return self._store

    def _extract_locked(self) -> ExtractNumbersAgent:
        """Return the extract agent, building it if needed. The caller holds the lock."""
        if self._extract is None:
            self._extract = ExtractNumbersAgent(settings=self._settings)
        return self._extract

    def _news_locked(self) -> NewsAggregator:
        """Return the aggregator over the shared client, building both if needed."""
        if self._aggregator is None:
            if self._client is None:
                self._client = build_news_client(self._settings)
            self._aggregator = NewsAggregator.from_settings(self._settings, self._client)
        return self._aggregator


__all__ = ["AppContext"]
