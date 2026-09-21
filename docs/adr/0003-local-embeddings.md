# 3. Local embeddings and the shape of the vector layer

## Status

Accepted (phase 3)

## Date

2026-09-21

## Context

Phase 3 gives numenews its storage: five Qdrant collections, vectors for every news item, number
context, pattern and forecast, and hybrid search over them. Three decisions had to be made together,
because each constrains the others.

**Where do the vectors come from?** `AGENTS.md` rules out external embedding APIs — local-only is a
design constraint, not a preference — so the choice is among local runtimes: `sentence-transformers`
(torch), `fastembed` (ONNX), or a cloud service we are not allowed to call. The default demo path also
has to work with no keys at all, and the README already promises `fastembed` with the two `bge` models.

**How wide are the vectors, and does one model serve every collection?** The collections differ in the
text they hold: a number context is one sentence, a news item or a pattern interpretation is a
paragraph. One model would either overpay for the short texts or underserve the long ones.

**How does the layer interact with the async pipeline?** Qdrant has both `QdrantClient` and
`AsyncQdrantClient`, and the news layer (phase 2) is `async`. The vector layer has to be usable from
the pipeline of phase 5 and the MCP tools of phase 6 without forcing either into an awkward shape.

Two smaller questions followed from the storage schema. A `datetime` payload index accepts an RFC 3339
timestamp, while the domain models' `date` is a calendar day — which of the two shapes is the stored
one? And phase 3's "hybrid search" is written as "dense + filter" in `ROADMAP.md` but as dense + sparse
in the private design brief: which of them is it?

Finally, `ROADMAP.md` 3.3 and 3.4 require payload indexes to exist *before* ingest. That makes the
collection schema a piece of code with a rule attached, not just configuration: whoever writes a point
must first have created the index it will be filtered by.

## Decision

We will compute every embedding locally through `fastembed`, and we will shape the vector layer as
follows.

1. **Two `bge` models, chosen by text length.** `BAAI/bge-small-en-v1.5` (384d) embeds the number
   contexts of `numbers`; `BAAI/bge-base-en-v1.5` (768d) embeds `news`, `patterns` and `forecasts`.
   Both are wrapped by `embeddings/` behind an `Embedder` Protocol (`dimension` + `embed`) whose
   implementations are the only code in the project that imports `fastembed`. `build_embedders`
   returns both; a collection's vector size is built from the matching dimension constant, so a
   mismatched embedder fails at collection creation.

2. **Nothing is loaded at import.** Each wrapper builds its ONNX session on the first `embed` call and
   reuses it; `embed([])` returns `[]` without building anything. Weights are downloaded once into
   `Settings.embedding_cache_dir` (`.cache/fastembed`, gitignored; ~286 MB in total), which
   `build_embedders` always passes to the wrappers.

3. **The vector layer is synchronous**, built on `QdrantClient` rather than `AsyncQdrantClient`. The
   in-memory engine the tests depend on (`QdrantClient(":memory:")`) is what makes the collection
   tests need no Docker at all, and ONNX inference is CPU-bound rather than I/O-bound. Async callers
   offload a blocking call: `asyncio.to_thread` in the pipeline of phase 5, and FastMCP's own worker
   thread for a synchronous MCP tool function in phase 6.

4. **One `VectorStore` owns the connection and both embedders.** `VectorStore.from_settings(settings)`
   builds the client from `Settings.qdrant_url`/`qdrant_api_key` and health-checks it immediately,
   raising `VectorStoreError` (which names `make dev`) instead of letting the first upsert fail with a
   transport error. `VectorStore.in_memory(base=..., small=...)` builds the same object over the
   in-memory engine for tests. Collection functions take the store, never a raw client, so a
   collection cannot be given the wrong embedder.

5. **Payload indexes are declared in code and created before the first point.**
   `vector/collections.py` holds the schema of every collection; each write path calls the matching
   `create_*` (which is idempotent via `collection_exists`) before its first upsert, and every read
   path calls `require_collection`, which raises `CollectionNotFoundError` instead of leaking a
   `ValueError` from local mode or a 404 from the server.

6. **A calendar day is stored as the RFC 3339 start of that day.** `date` payload fields are written
   as `2026-09-21T00:00:00Z` — the only shape a `datetime` index accepts — and read back by slicing to
   `YYYY-MM-DD` before strict model validation. Filters compare against `datetime` bounds with an
   exclusive upper bound for an inclusive `date_to`, so a day range cannot silently drop the items of
   its own last day.

7. **"Hybrid" means dense + filtered pre-fetching, in both of Qdrant's forms.**
   `search_news` passes the filter as `query_filter`; `hybrid_search_news` builds the multi-stage Query
   API with the filter *inside* each `Prefetch` and fuses the rankings with RRF. Phase 3 has one dense
   retriever, so the fusion merges a single ranking and results come back RRF-ordered; a sparse/BM25
   retriever would be a second `Prefetch` in the same list, with no schema change beyond a sparse
   vector field.

8. **The layer table gains a row.** `docs/ARCHITECTURE.md` now lets `vector` import `models`,
   `embeddings` and `numerology`. `models` remains the shared vocabulary, `embeddings` supplies the
   `Embedder` Protocol and its implementations, and `numerology` supplies `is_master` for the derived
   `master_number` payload field — the pure layer is a leaf, so this direction introduces no cycle and
   keeps 11/22/33 defined exactly once.

## Consequences

- **What becomes easier.** The whole vector layer is testable without a network or a service:
  `QdrantClient(":memory:")` is a real engine, and `FakeEmbedder` (tests/integration/fakes.py) states
  the embedding geometry explicitly, so a similarity test fails because of the collection and not
  because a model changed its mind. Collection schemas live in one module, so the five payload
  contracts can be reviewed together and asserted against the real server in one parametrized test.
  Idempotency is a property of derived point ids rather than of a lookup table, which is what phase
  5's repeated ingest relies on.
- **What becomes harder.** The first test run on a fresh machine downloads ~286 MB and takes minutes;
  after that the weights are cached. Two embedding models mean two caches and two failure modes, and a
  future model swap requires a new collection rather than an in-place migration.
- **What we explicitly did not do.** No sparse vector or BM25 retriever in phase 3 (the `Prefetch`
  list is where it goes). No `AsyncQdrantClient`. No external embedding API, ever — `AGENTS.md`
  rules it out, and this ADR repeats it as a constraint on future changes rather than a phase-3
  detail. No vector in `number_history`: exact questions about dates are answered by payload filters,
  and similarity is not evidence about time.
- **Follow-up work.** Phase 5.2 writes `news`, `numbers` and `number_history` in one ingest and must
  keep the three in step; phase 5.4 reads `forecasts` before re-running the forecast agent. The
  coverage floors of phase 10 apply to `vector/` and `embeddings/` as infrastructure (≥ 70%).

## References

- [ADR 0002](0002-numerology-scope.md) — the pure numerology layer whose `is_master` the payload
  derivation reuses
- [`docs/QDRANT_COLLECTIONS.md`](../QDRANT_COLLECTIONS.md) — the five payload schemas and the search
  entry points
- [`docs/EMBEDDINGS.md`](../EMBEDDINGS.md) — the models, the cache and the threading decision
- [`ROADMAP.md`](../../ROADMAP.md) — phase 3, tasks 3.1–3.9
- [`fastembed`](https://github.com/qdrant/fastembed) — the local ONNX embedding library
