# 8. `fastembed` instead of OpenAI embeddings

## Status

Accepted (phase 3)

## Date

2026-09-21

## Context

Every collection in the vector layer needs vectors, and the cheapest implementation would have been
to call a hosted embedding API: no model to download, no ONNX session to manage, and an almost
identical quality for the English news text this project stores. That option is closed by
`AGENTS.md`, which rules out external embedding APIs as a design constraint rather than a
preference: the default demo path must work with no API keys at all, and the project must run
entirely on the machine it is installed on.

With hosted models out, the remaining candidates were local runtimes:

- `sentence-transformers`, which pulls PyTorch (multiple gigabytes of wheels and a GPU-shaped
  installation problem) and usually needs the same model weights anyway;
- `fastembed`, which runs the same `bge` family through ONNX Runtime and ships as a normal Python
  dependency;
- a hand-rolled model, which is not a serious option for a portfolio project.

Two further questions followed. Which vector width, given that the collections hold texts of very
different lengths (a number context is a sentence; a news item or a pattern interpretation is a
paragraph)? And when is the model loaded, given that the MCP server and the CLI build their
collaborators lazily and must not block on a download at import?

## Decision

We will compute every embedding locally through `fastembed`, with two `bge` models chosen by text
length:

1. **`fastembed` (ONNX), not `sentence-transformers` (torch).** It is the smallest dependency tree
   that can run the `bge` family locally, it needs no CUDA and no separate model server, and it fits
   the project's "no keys, no cloud" constraint (`AGENTS.md`). The price is a first-use download
   (see Consequences).
2. **Two models, chosen by the collection, not by the caller.** `BAAI/bge-small-en-v1.5` (384d)
   embeds the short number contexts of `numbers`; `BAAI/bge-base-en-v1.5` (768d) embeds `news`,
   `patterns`, `forecasts` and `digests`. One model would either overpay for a sentence or underserve
   a paragraph. The mapping lives in `vector/collections.py`, and a collection's vector size is built
   from the embedder's `dimension`, so giving a collection the wrong embedder fails at creation
   rather than at query time.
3. **`Embedder` is the only place that imports `fastembed`.** `embeddings/protocol.py` defines the
   two-method Protocol (`dimension`, `embed`); `embeddings/fastembed.py` implements it;
   `vector/` accepts the Protocol and never the library, and the tests substitute `FakeEmbedder`.
4. **Nothing is loaded at import.** The constructor records the cache directory; the ONNX session is
   built by the first `embed` call and reused. `embed([])` returns `[]` without building anything, so
   an empty ingest does not trigger a download. `build_embedders(settings)` always passes
   `Settings.embedding_cache_dir` (`.cache/fastembed`, gitignored), which keeps the weights inside
   the checkout instead of a machine-global directory.
5. **English-only is an accepted limit, not an oversight.** The `bge-*-en-v1.5` models are English;
   the eval corpus is English for that reason (ADR 0013), and Russian news text is stored and
   reduced by the numerology layer but not embedded with a language guarantee.

## Consequences

- **What becomes easier.** Installation is `uv sync --all-extras` with no model server and no keys;
  the whole vector stack is testable offline (`FakeEmbedder` in `.memory`) while the real models are
  exercised in `tests/integration/test_embeddings_fastembed.py`; and the same `Embedder` Protocol
  makes a future model swap a new collection plus a new implementation of two methods.
- **What becomes harder.** The first run on a fresh machine downloads roughly 286 MB into
  `.cache/fastembed` and can take minutes; after that the weights are cached. Two models mean two
  caches and two failure modes, ONNX inference is CPU-bound (which is why the vector layer is
  synchronous and callers offload it with `asyncio.to_thread`), and a model change is not an
  in-place migration: it invalidates every stored vector and needs a new collection.
- **What we explicitly did not do.** No external embedding API, in the runtime or the eval
  (`answer_relevancy` embeds through the local 384d model, ADR 0013). No `sentence-transformers`,
  no torch, no GPU dependency. No multi-lingual model: the English limit is documented rather than
  papered over.
- **Follow-up work.** A multi-lingual model would be a new ADR and a new collection; the cache
  directory is part of `Settings`, so a CI or container image would have to pre-seed it (there is no
  CI in this project by design).

## References

- [ADR 0003](0003-local-embeddings.md) — the vector layer decision this ADR expands
- [ADR 0013](0013-eval-isolation.md) — why the eval corpus is English and which embedder scores it
- [`docs/EMBEDDINGS.md`](../EMBEDDINGS.md) — the models, the cache, lazy loading and threading
- [`src/numenews/embeddings/`](../../src/numenews/embeddings/) — the Protocol and the two wrappers
- [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) and
  [`BAAI/bge-base-en-v1.5`](https://huggingface.co/BAAI/bge-base-en-v1.5) — the model cards
