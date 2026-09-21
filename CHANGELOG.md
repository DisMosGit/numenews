# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project skeleton (phase 0): `src/` layout with the eight subpackages, the `uv` environment
  (`uv.lock`, Python 3.14) and `uv_build` packaging.
- Configuration via `pydantic-settings` (`Settings`, `get_settings`) with `.env.example`, and
  `structlog` logging: JSON on stderr in `prod`, readable in `dev`, correlation ids through
  `contextvars`.
- Tooling: ruff, `mypy --strict` with the pydantic plugin, pytest + pytest-asyncio, branch
  coverage, pre-commit hooks, and a self-documenting Makefile (`install`, `lint`, `format`,
  `test*`, `coverage`, `dev`, `dev-down`, `mcp`, `run`, `clean`).
- Qdrant 1.19.1 through Docker Compose, with a named volume, a healthcheck and the
  `qdrant_in_memory` test fixture.
- Test scaffolding: hermetic `settings` and `tmp_cache_dir` fixtures, `--run-eval` gating for the
  future ragas suite, and contract smoke tests for the CLI and MCP placeholders.
- Documentation: `docs/ARCHITECTURE.md`, `docs/NUMEROLOGY.md`, `docs/adr/` (ADR 0001 and the
  template) and `docs/agentic/AGENT_WORKFLOW.md`.
- Domain models (phase 1.1): `NewsItem`, `ExtractedNumbers`, `NumerologyResult`,
  `MasterCheckResult`, `Pattern`, `Forecast` and `NumberActivation`, plus the `NewsId`, `PatternId`
  and `ForecastId` wrappers — every one frozen and strict, in `numenews.models`.
- Pure numerology (phase 1.2–1.7): digit reduction with the 11/22/33 master stop, gematria for
  Latin (`A=1 … Z=26`) and the 33-letter Russian alphabet, date resonance, the regex extraction
  fallback (ISO dates, `DD.MM.YYYY`, Russian month names) and `compute_numerology` as the layer's
  entry point. The package imports only `numenews.models`, performs no I/O, and is 100% covered by
  unit and hypothesis property tests.
- Documentation for the layer: a complete `docs/NUMEROLOGY.md` and ADR 0002 recording the scope
  (reduction, master numbers, gematria, date resonance, regex fallback) and its limits.
- News layer (phases 2.1–2.8): the `Topic`/`DateRange` query models, the `NewsSource` Protocol and
  the `NewsSourceError` hierarchy (`HTTPError`, `AuthError`, `RateLimitError`, `TransportError`,
  `ParseError`), one `hishel`-cached `httpx` client with a `tenacity` retry policy, five adapters
  (GDELT, NewsAPI, GNews, Mediastack, Currents) that map to `NewsItem` with a deterministic
  `uuid5` id and a UTC date, and `fetch_news(topic, date_range)` over a `NewsAggregator` that
  queries every configured source concurrently, filters the range once and de-duplicates on
  `(title, source, date)`.
- Configuration for the four optional news keys (`NEWSAPI_KEY`, `GNEWS_KEY`, `MEDIASTACK_KEY`,
  `CURRENTS_KEY`); GDELT needs none, so the demo path still runs unconfigured.
- Embeddings (phase 3.1): `numenews.embeddings` — an `Embedder` Protocol and the two local
  `fastembed` wrappers (`bge-small-en-v1.5` 384d, `bge-base-en-v1.5` 768d) that build their ONNX
  session on the first `embed`, never at import, and keep the weights in
  `Settings.embedding_cache_dir`.
- Vector layer (phases 3.2–3.8): `numenews.vector` — `VectorStore` (a health-checked `QdrantClient`
  plus both embedders, with an in-memory form for tests), the five collections with their payload
  indexes created before the first point (`news`, `numbers`, `patterns`, `forecasts`,
  `number_history`), model⇄payload conversion with RFC 3339 dates and deterministic point ids, the
  typed `NewsFilter`, and the search paths: `search_news`, `hybrid_search_news` (filter inside
  `Prefetch` plus RRF fusion), `find_similar_patterns` and `get_history` (a calendar-day window with
  an injectable `today`). `Pattern` gains the `discovered_at` field its collection indexes.
- Documentation for the vector layer: `docs/QDRANT_COLLECTIONS.md` (payload schemas, point ids,
  search examples, the local-mode caveat) and `docs/EMBEDDINGS.md` (models, cache, lazy loading,
  threading), with ADR 0003 recording the local-embeddings and layer decisions.

### Changed
- `docs/ARCHITECTURE.md`: the `numerology` layer may import `models` (the result types it returns),
  the "implemented so far" section now covers phases 0–2, and the `vector` layer may import
  `models`, `embeddings` and `numerology` (ADR 0003).
- Dependencies: `httpx`, `hishel[httpx]` and `tenacity` join the runtime set, `respx` the dev group;
  `fastembed` joins the runtime set in phase 3, bringing ONNX Runtime and the Hugging Face hub client
  with it.
- `.env.example` ships the four news keys uncommented and explains that a missing key means the
  source is not queried at all; `EMBEDDING_CACHE_DIR` joins the template in phase 3. `README.md` and
  the package docstring track the implemented phases.
- Documentation for the news layer: `docs/NEWS_SOURCES.md` records the five APIs, their free tiers
  and request shapes, the cache design and what the layer deliberately leaves out.

### Deprecated
-

### Removed
-

### Fixed
-

### Security
-

## [0.0.0] — 2026-01-01

### Added
- Initial commit. Repository bootstrap.
