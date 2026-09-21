# Architecture

> **Phase 0 template.** The layer map, the boundary rules and the state model below are settled;
> the data-flow diagram describes the *target* pipeline and is filled in as its steps land
> (phases 2–6, all of which are done). The full document is written in phase 10.1.

## One pipeline, two interfaces

numenews is a single package with two entry points over the same code:

- **MCP server** (`numenews.mcp`, phase 6) — nine tools an LLM client calls, each returning a
  Pydantic model.
- **One-shot CLI** (`numenews.cli`, phase 7) — the same operations once per invocation, JSON on
  stdout, nothing else.

Both are thin: the work lives in the pipeline, and all persistent state lives in Qdrant, so a
command must be idempotent and resumable (AGENTS.md).

## Layers

| Layer | Package | May import | Responsibility |
|---|---|---|---|
| Pure logic | `numerology` | `models` | reduction, master numbers, gematria, date resonance, dominant number, regex fallback |
| Boundaries | `models` | nothing | Pydantic v2 types crossing every module boundary |
| Adapters | `news`, `embeddings` | `models` | five news APIs behind one Protocol; local `fastembed` vectors |
| Storage | `vector` | `models`, `embeddings`, `numerology` | Qdrant client, collections, payload indexes, hybrid search |
| Reasoning | `agents` | `numerology`, `models` | `pydantic-ai` agents: extract, pattern, forecast, summarize |
| Composition | `pipeline` | everything above | the RAG chain, the sliding window, step timing and retries |
| Interfaces | `mcp`, `cli` | everything above; `cli` also uses `mcp` | tool and command surfaces, JSON serialization |

Two rules keep this acyclic and testable:

1. `numerology` is pure — no I/O, and never imports `news`, `vector`, `agents`, `pipeline` or `mcp`;
   it depends only on `models` for the types of its results (ADR 0002), so its invariants can be
   property-tested without any infrastructure.
2. State crosses boundaries as Pydantic models only — no dicts, no dataclasses, no free-form JSON
   from an LLM.

`vector` is the one layer that reads two others: `embeddings` for the `Embedder` Protocol its
collections embed with, and `numerology` for `is_master`, which derives the filterable
`master_number` payload field. Both are leaves, so the graph stays acyclic and 11/22/33 stays defined
once (ADR 0003).

`pipeline` is the one layer that reads all of them, which is what makes the interfaces thin: it owns
the order of the chain and nothing else — no numerology, no storage schema, no HTTP — and it is
asynchronous while `vector` stays synchronous, bridged only by `asyncio.to_thread` (ADR 0011).

`cli` is the one interface that imports the other: roadmap 7.8's `numenews mcp` proxies into
`numenews.mcp.main`, and the one-shot commands share the MCP server's lazy `AppContext` as their
container instead of growing a second one — the two surfaces build the store, the agents and the news
client the same way, once (ADR 0006).

`config` and `logging` sit below every layer: settings are validated once at start, and logs go to
stderr so stdout stays machine-readable.

## Data flow

```mermaid
flowchart TD
    A[news APIs: GDELT, NewsAPI, GNews, Mediastack, Currents] --> B[fetch_news + hishel cache]
    B --> C[extract_numbers: pydantic-ai + regex fallback]
    C --> D[compute_numerology: pure logic]
    D --> E[fastembed 384d/768d]
    E --> F[(Qdrant: news, numbers)]
    F --> G[find_patterns: hybrid search + LLM]
    G --> H[build_forecast: LLM + number_history]
    H --> I[(Qdrant: patterns, forecasts, number_history)]
    F --> K[summarize_news: older than the window]
    K --> L[(Qdrant: digests)]
    I --> J[JSON to CLI stdout / MCP client]
```

All of it is driven by `numenews.pipeline`, which is the only layer that knows this order. Context
management: a sliding seven-day window feeds the agents, older items are summarised into a
numerological digest, and `number_history` carries activations across sessions — see
[`CONTEXT_MANAGEMENT.md`](CONTEXT_MANAGEMENT.md).

## State

| Collection | Vector | Payload indexes |
|---|---|---|
| `news` | 768d (`bge-base-en-v1.5`) | `date`, `source`, `numerology_value`, `master_number` |
| `numbers` | 384d (`bge-small-en-v1.5`) | `number`, `context` |
| `patterns` | 768d | `type`, `strength`, `discovered_at` |
| `forecasts` | 768d | `date`, `dominant_number` |
| `number_history` | — (payload only) | `number`, `date` |
| `digests` | 768d | `period_start`, `period_end` |

Payload indexes are created **before** ingest: with an index Qdrant pre-filters inside the HNSW
walk, without one it degrades to post-filtering. In multi-stage (hybrid) queries the filter belongs
inside each `Prefetch`.

A `date` payload field holds the RFC 3339 start of the day (`2026-09-21T00:00:00Z`), because the
`datetime` index accepts nothing shorter; `vector/payloads.py` writes that shape and reads it back
as the domain models' `date`. `docs/QDRANT_COLLECTIONS.md` documents every payload field.

## Implemented so far

Phase 0: configuration (`config.py`), logging (`logging.py`), the package skeleton and the test
scaffolding. Phase 1: the domain models (`models/`, frozen and strict) and the pure numerology layer
(`numerology/`, 100% covered) with `docs/NUMEROLOGY.md` and ADR 0002. Phase 2: the news layer
(`news/`, 100% covered) — one `NewsSource` Protocol, five adapters (GDELT, NewsAPI, GNews,
Mediastack, Currents), one `hishel`-cached `httpx` client with a `tenacity` retry policy, and
`fetch_news` as the aggregating entry point, documented in `docs/NEWS_SOURCES.md`. Phase 3: the
vector layer — `embeddings/` wraps the two local `bge` models behind an `Embedder` Protocol
(downloaded once into `.cache/fastembed`, never at import), and `vector/` owns the Qdrant connection,
the five collections with their payload indexes, the model↔payload conversion and the four search
paths (`search_news`, `hybrid_search_news`, `find_similar_patterns`, `get_history`), documented in
`docs/QDRANT_COLLECTIONS.md` and `docs/EMBEDDINGS.md` with ADR 0003. Phase 4: the reasoning layer —
`agents/` builds any OpenAI-compatible chat model from `Settings`, runs the three `pydantic-ai`
agents (`ExtractNumbersAgent` with its regex fallback, `PatternAgent`, `ForecastAgent`), and turns
each model answer into a domain model through the draft schemas of `agents/schemas.py`; the prompts
and the `agents/` tests are documented in `docs/PROMPTS.md` with ADR 0004. Phase 5: the composition
layer — `pipeline/` owns the chain (`ingest → analyze → forecast`, plus the opt-in `summarize`), the
seven-day sliding window and the step timings, bridges the async pipeline to the synchronous vector
layer with `asyncio.to_thread`, and adds the sixth collection `digests` for the summary of the news
the window leaves behind; documented in `docs/RAG_PIPELINE.md` and `docs/CONTEXT_MANAGEMENT.md` with
ADR 0011. Phase 6: the interface layer — `mcp/` builds one `MCPServer` over stdio around the nine
tools, with an `AppContext` whose collaborators (the store, the extract agent, the pipeline and the
cached news client) are built lazily on first use, JSON-shaped argument schemas that convert into the
strict domain models, and a failure policy that turns expected domain errors into `ToolError`s the
model can read; documented in `docs/MCP_TOOLS.md` with ADR 0010. Phase 7: the second interface — the
one-shot CLI (`cli/`) with six commands (`today`, `forecast`, `history`, `search`, `patterns`, `mcp`),
one JSON document per command on stdout and logs on stderr, a `--date` grammar of absolute and
relative days, an `ErrorReport` for expected failures, and the exact `read_patterns` read of the
`patterns` collection; it reuses the MCP server's `AppContext` as its container and proxies
`numenews mcp` into `numenews.mcp.main`; documented in `docs/USER_FLOW.md` with ADR 0005 and 0006.
`ROADMAP.md` is the authoritative status; `docs/adr/` records the decisions.
