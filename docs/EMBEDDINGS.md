# Embeddings

> Phase 3. The decision behind this document is [ADR 0003](adr/0003-local-embeddings.md); the
> collections that use these vectors are in [QDRANT_COLLECTIONS.md](QDRANT_COLLECTIONS.md).

## Local only

Every vector in numenews is computed on the machine with [`fastembed`](https://github.com/qdrant/fastembed),
which runs ONNX models through ONNX Runtime. No text is sent to an embedding API, no key is needed,
and the default demo path works offline once the weights are on disk — which is what `AGENTS.md`
requires and what makes the vector layer testable without a network.

## Two models, two jobs

| Wrapper | Model | Dimensions | Used by |
|---|---|---|---|
| `FastEmbedSmall` | `BAAI/bge-small-en-v1.5` | 384 | `numbers` |
| `FastEmbedBase` | `BAAI/bge-base-en-v1.5` | 768 | `news`, `patterns`, `forecasts`, `digests` |

The split is by text length. The `numbers` collection stores one sentence per point — the snippet a
number appeared in — and the small model is both sufficient and cheaper there. News items, pattern
interpretations and forecasts carry a paragraph or more, where the wider model's extra capacity pays
for itself. Each collection's vector size is built from the matching constant,
`embeddings.BASE_DIMENSION` / `SMALL_DIMENSION`, so a wrong embedder fails when the collection is
created instead of silently on the first query.

## Where the weights live

```bash
EMBEDDING_CACHE_DIR=.cache/fastembed   # Settings.embedding_cache_dir, gitignored
```

The first `embed` call downloads the quantized ONNX models — about 67 MB for the small one and
219 MB for the base one — and reuses them from that directory afterwards. `build_embedders(settings)`
always passes it; the wrappers themselves default to `cache_dir=None`, which leaves the location to
fastembed (its own directory under the system temporary directory), so `FastEmbedBase()` works
without configuration.

## Lazy loading

Importing `numenews.embeddings`, reading settings or building a `VectorStore` loads no model. Each
wrapper builds its ONNX session inside its first `embed` call and hands the same session back
afterwards, so:

- a process that only reads settings or creates collections pays nothing;
- `embed([])` returns `[]` without building a session — an empty batch is not a reason to download;
- a test that needs deterministic vectors uses `FakeEmbedder` (see below) and never touches a model.

The session is per wrapper instance, never a module-level singleton, so a test cannot accidentally
share a half-initialised model with production code.

## Determinism and threading

`bge` inference is deterministic on CPU: embedding the same text twice returns the same floats, which
is what makes a stored vector comparable with a later query (asserted in
`tests/integration/test_embeddings_fastembed.py`).

Embedding and Qdrant access are **synchronous**. The vector layer is built on `QdrantClient`, because
that is what `QdrantClient(":memory:")` supports for the test suite, and an ONNX session is a CPU-bound
object rather than an async one. Async callers (the pipeline of phase 5, the MCP tools of phase 6)
offload a blocking call to a worker thread — `asyncio.to_thread` for the pipeline and for the tools'
storage calls, and the SDK's own worker thread for a synchronous tool function. ADR 0003 records the
trade-off.

## Tests

| File | What it proves |
|---|---|
| `tests/unit/test_embeddings.py` | Lazy loading, session reuse, `list[list[float]]` conversion, empty batch — with `TextEmbedding` replaced by a fake |
| `tests/integration/test_embeddings_fastembed.py` | The real models: 384/768 dimensions, determinism, batch order |
| `tests/integration/fakes.py` | `FakeEmbedder` — deterministic one-hot vectors for the collection tests |

Only the integration file needs the weights on disk (downloaded on first run, ~286 MB in total, into
`.cache/fastembed`); everything else in the suite runs without them.
