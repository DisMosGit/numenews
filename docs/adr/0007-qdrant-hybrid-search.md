# 7. Qdrant hybrid search: filters inside the prefetch, RRF, no sparse retriever yet

## Status

Accepted (phase 3)

## Date

2026-09-21

## Context

Phase 3 needs retrieval that answers two different questions at once: *which stored news is closest
to this query*, and *which stored news satisfies these exact constraints* (a date range, a source, a
numerology value, a master number). The first is a vector question, the second is a payload
question, and Qdrant can answer either alone.

The roadmap wrote "hybrid search" as **dense + filter**, while the private design brief wrote it as
**dense + sparse**. They are different architectures: the first is one vector ranking narrowed by a
payload filter, the second is two rankings (a dense embedding and a lexical/BM25 signal) fused into
one. Phase 3 has exactly one retriever — the `fastembed` dense model — so the two readings had to be
reconciled before the search paths could be written, and the decision had to survive Qdrant's own
API split.

That split is the second force. `search` takes a `query_filter` next to the vector, while the
multi-stage Query API (`query_points` with `prefetch`) builds each stage explicitly. Where the
filter sits changes what the database does: a top-level filter is applied to the *result* of the
HNSW walk, so a query that matches only a handful of payloads can come back short; a filter inside a
`Prefetch` is applied *during* that stage's walk, so the stage collects `limit` matching points
before anything is fused. `AGENTS.md` and `ROADMAP.md` 3.3 also require payload indexes to exist
**before** ingest, which is what makes an inside-the-prefetch filter cheap.

Finally, repeated ingest (phase 5) must be idempotent without a lookup table: the same article
stored twice must overwrite its own point rather than duplicate it.

## Decision

We will keep one dense retriever in phase 3, place every payload filter inside the stage it belongs
to, and fuse with RRF:

1. **Two search entry points, one schema.** `search_news(store, query, filters, limit)` passes the
   filter as the top-level `query_filter` — one vector ranking, narrowed. `hybrid_search_news(...)`
   builds the multi-stage Query API with the filter **inside each `Prefetch`** and fuses the
   prefetched rankings with Reciprocal Rank Fusion (`Fusion.RRF`). Both return the same
   `list[NewsItem]` and read the same `news` collection, so a caller chooses a cost, not a schema.
2. **"Hybrid" means dense + filtered pre-fetching in phase 3.** The `Prefetch` list is the extension
   point for a lexical retriever: a sparse/BM25 `Prefetch` added to that list needs no change to the
   collection's dense vector, no payload change and no caller change — the RRF step is already
   there. Phase 3 does not add one (see Consequences).
3. **Payload indexes before the first point.** `vector/collections.py` declares every index;
   each write path calls its idempotent `create_*` first and each read path calls
   `require_collection`, so a filtered query never runs against an unindexed collection. With an
   index Qdrant pre-filters inside the HNSW walk; without one the same filter degrades to
   post-filtering and can silently shorten the result.
4. **Deterministic point ids make ingest idempotent.** A news point id is `uuid5` over the item's
   URL, a pattern's over its content, so a repeated ingest overwrites its own points and no
   duplicate-detection table is needed (phase 5 relies on this).
5. **Filters stay typed and collection-specific.** `NewsFilter` is the only filter model, it is
   validated as a Pydantic model, and `query_qdrant` rejects a filter for a collection that has no
   filter schema rather than guessing.

## Consequences

- **What becomes easier.** The same `NewsFilter` works in both code paths, so a behavioural
  difference between `search_news` and `hybrid_search_news` would be a bug in one of them, not a
  schema mismatch. Retrieval is testable without Docker: `QdrantClient(":memory:")` is a real engine
  and the in-memory tests assert the filter semantics, while `tests/integration/test_vector_docker.py`
  asserts the payload indexes exist on a real server. The eval scores the production path directly
  (`tests/eval/test_retrieval.py` hits `hybrid_search_news`, hit@5 20/20 on the committed corpus).
- **What becomes harder.** With one retriever, RRF merges a single ranking: results come back
  RRF-ordered, which is a different order from a plain similarity score, and a caller that wants a
  raw score cannot get one from `hybrid_search_news`. A sparse retriever would change the ranking
  and therefore the eval numbers, so it needs its own measurement, not just a code change.
- **What we explicitly did not do.** No sparse vector field, no BM25, no external reranker. No
  top-level filter in the multi-stage path. No filter on `numbers`, `patterns`, `forecasts` or
  `digests`: the filter schema exists for `news` only, and a request for another collection is a
  tool error.
- **Follow-up work.** A sparse/lexical `Prefetch` is the natural first extension and belongs to a
  phase that can measure it against the eval; `docs/QDRANT_COLLECTIONS.md` is where its schema would
  be documented.

## References

- [ADR 0003](0003-local-embeddings.md) — the vector layer, where this decision was first recorded in
  passing (items 4, 7 and 8)
- [`docs/QDRANT_COLLECTIONS.md`](../QDRANT_COLLECTIONS.md) — the collections, payload indexes and the
  search examples
- [`docs/EVAL.md`](../EVAL.md) — the retrieval quality measured over the production path
- [`ROADMAP.md`](../../ROADMAP.md) — phase 3, tasks 3.3, 3.8 and 3.9
- [Qdrant — hybrid queries and fusion](https://qdrant.tech/documentation/concepts/hybrid-queries/)
