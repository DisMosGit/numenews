# 10. The MCP server: SDK v2, one lazy application context, and errors the model can read

## Status

Accepted (phase 6)

## Date

2026-09-21

## Context

MCP is the project's primary interface (`AGENTS.md`, and the target state in `ROADMAP.md`: nine tools
that Claude Desktop and Cursor can attach to). Phase 5 built the RAG pipeline the tools are meant to
be thin wrappers over, and deliberately left two questions open — how an MCP tool reports a failure
(`pipeline/steps.py`: "phase 6 decides how an MCP tool reports a failure") and how a long-lived
server owns a store, an embedder session and an LLM client.

Four forces shaped the implementation:

**Which SDK line?** `ROADMAP.md` 6.1 sketched `FastMCP("numenews")`. The current stable MCP Python
SDK is v2, where that class was renamed to `MCPServer` and `mcp.server.fastmcp` no longer exists;
v1.x lives on a maintenance branch and receives critical fixes only. New code belongs on v2, so the
roadmap's class name cannot be taken literally.

**The domain models cannot be tool parameters.** Every model in `numenews.models` is frozen and
`strict` on purpose (phase 1, [ADR 0002](0002-numerology-scope.md)): a Python `str` is never coerced
into a `date`, a `list` never into a `tuple`, a UUID string never into `NewsId`. JSON-RPC arguments
arrive in exactly those shapes, so passing `DateRange` or `Pattern` as a tool parameter fails
validation with "Input should be a valid date" before any tool code runs.

**The server must start without its dependencies.** Roadmap 6.1's definition of done is "`make mcp`
starts the server and does not fail on connection". `VectorStore.from_settings` health-checks Qdrant,
and every agent needs an LLM endpoint, so building everything at startup would make the server refuse
to boot on a machine that has neither — and would make the stdio handshake untestable.

**An MCP tool failure is a conversation turn, not a crash.** The SDK turns a raised `ToolError` into a
normal result with `is_error=True` whose message the model reads, while any other exception becomes a
sanitised "Error executing tool" plus an ERROR traceback in the log. Which of the two a missing
collection, an unset key or a mistyped id deserves is a product decision.

## Decision

We will add `numenews.mcp` as the interface layer, with the decisions below.

- **The official SDK v2, `mcp>=2.2,<3`, class `MCPServer`.** The transport is stdio; the entry point
  is `numenews.mcp.main.main`, reachable as `python -m numenews.mcp` and `make mcp`, with
  `numenews.mcp.__main__` delegating to it. The server object is built by `build_server()`, not at
  import time, so it can be handed a test context. The rename from the roadmap's `FastMCP` is
  recorded as a deviation in `ROADMAP.md` 6.1 and here.
- **One `AppContext`, built by the lifespan, whose collaborators are lazy, memoized and
  single-flight.** It holds settings, a `VectorStore`, an `ExtractNumbersAgent`, a `Pipeline`, a
  `NewsAggregator` and the one long-lived cached HTTP client; each is built on first use under one
  `asyncio.Lock`, and the blocking constructions (the Qdrant health check, the pipeline assembly) go
  through `asyncio.to_thread`, the bridge of [ADR 0003](0003-local-embeddings.md). The consequence is
  that each tool needs the smallest possible prerequisite set: the pure tools need nothing, extraction
  needs an LLM endpoint only, `fetch_news` needs the feeds only, the storage tools need Qdrant only,
  and `find_patterns`/`build_forecast` need both. The lifespan's `finally` closes what was built.
- **Wire schemas convert, the domain models do not bend.** `numenews.mcp.schemas` mirrors what
  `numenews.agents.schemas` does for model output: `DateRangeInput`, `NewsFilterInput` and
  `PatternInput` accept the JSON shapes, enforce the same rules the domain enforces (so `to_domain()`
  cannot fail), and convert into the frozen models. Tool *return* annotations are the domain models
  themselves, because validation on the way out is exactly what we want.
- **Expected domain failures become `ToolError`; anything else is left to crash.** `mcp/errors.py`
  maps `AgentError`, `NewsSourceError`, `PipelineError` and `VectorStoreError` (their subclasses
  included) to a `ToolError` carrying the original message, so the model can fix a missing collection
  or an unset key. A defect in our own code keeps the SDK's sanitised crash and the ERROR traceback,
  following the rule of phase 2.8: never hide a defect behind a thinner result.
- **Nine plain functions registered through one registry.** `mcp/tools.py` defines the nine tools and
  `TOOLS`; `build_server()` registers them with `add_tool`. A tool is an ordinary function whose name,
  docstring and type hints are the contract, so a unit test can import and call the context-free ones
  and the server test can assert the surface without a transport.
- **`query_qdrant` is a `Literal["news", "patterns"]` search returning a typed result.**
  `numenews.models` bans dicts at boundaries, so the tool returns `CollectionQueryResult` holding
  `NewsItem | Pattern` entities instead of the roadmap's `list[dict]`, and the collection set is the
  two the vector layer actually has semantic read paths for. `number_history` is read exactly by
  `get_history`; `numbers`, `forecasts` and `digests` have no read path yet and are not offered.
- **`save_pattern` returns the saved `Pattern`.** The roadmap named a `SavedPattern`; the value the
  vector layer returns *is* a `Pattern` with `discovered_at` stamped, and a second type would only
  restate it.
- **`get_history(number, days=30)`.** The roadmap wrote `get_history(number)`; the read is a window,
  so the window length is a parameter whose default matches phase 8's 30-day memory.

## Consequences

Easier: the tools are thin, because the pipeline owns the order of the chain and the vector layer owns
the schema (the phase-5 bet paid off); the server starts on a machine with no Qdrant and no key, which
makes `make mcp` and the stdio test work in CI and in a fresh checkout; the nine tools are testable
twice over — in memory through the SDK's own `Client`, and over a real subprocess in
`tests/integration/test_mcp_stdio.py`, which replaces the roadmap's manual "open it in Claude Desktop"
check; and every failure mode has one place to change (`mcp/errors.py`).

Harder and worth remembering:

- `MCPServer` is a new dependency surface with its own release cadence. A major bump means re-reading
  the SDK migration guide, and the phase-6 code assumes v2's `Context[AppContext]` lifespan access,
  `add_tool` and `ToolError` locations.
- Because collaborators are lazy, a misconfiguration surfaces on the first tool call rather than at
  startup. That is the point, but it means the failure has to stay readable — hence the error
  translation, which names `make dev`, `OPENAI_API_KEY`/`OPENAI_BASE_URL`, or the missing collection.
- A second, looser schema layer now exists for arguments (`mcp/schemas.py`). It must be kept in step
  with the domain models it converts to; the tests assert the mirrored rules (reversed ranges, a
  `strength` outside the unit interval, an unknown pattern type).
- The strict-model boundary is a general lesson for any future interface: `numerology` can stay
  strict because it is called in-process, but every JSON-speaking surface needs its own DTOs.
- `query_qdrant` promises less than its name suggests: two collections today. Adding the others means
  building their read paths in `vector/` first — which is the right order, but it is follow-up work
  the doc has to state plainly.
- No live run against Claude Desktop or Cursor happens in this environment. The stdio integration
  test proves the transport and `ROADMAP.md` records the substitution.

## References

- `ROADMAP.md` phase 6 (6.1–6.12) and phase 7.8 (`numenews mcp --transport stdio`)
- [`docs/MCP_TOOLS.md`](../MCP_TOOLS.md) — the tool surface, its prerequisites and the client configs
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) — the interface layer and the boundary rules
- [ADR 0002](0002-numerology-scope.md) — `numerology` is pure; the strict domain models
- [ADR 0003](0003-local-embeddings.md) — the synchronous vector layer and the `asyncio.to_thread` bridge
- [ADR 0011](0011-rag-pipeline-orchestration.md) — the pipeline the tools call
- [MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/) and its
  [migration guide](https://py.sdk.modelcontextprotocol.io/migration/) — the `FastMCP` → `MCPServer`
  rename and the v2 testing client
