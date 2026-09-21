# Glossary

> Every term that appears in more than one document, defined once and linked to the document that
> owns it. Alphabetical; the domain terms come first because they are the product, the technical
> terms after.

## Domain

- **Activation** — one occurrence of a number in one news item, recorded as a `NumberActivation`
  with the number, the day, the item and the sentence around it. Activations are the rows of
  `number_history` and the material of the memory window.
  See [`CONTEXT_MANAGEMENT.md`](CONTEXT_MANAGEMENT.md).
- **Date resonance** — two dates whose reduced values coincide. `reduce_date(date(2026, 9, 21))` is
  22. See [`NUMEROLOGY.md`](NUMEROLOGY.md).
- **Digit sum** — the sum of a number's decimal digits: `124 → 1 + 2 + 4 = 7`.
- **Dominant number** — the number a set of readings rests on: the most frequent reduced value, with
  ties going to the larger one. A day with no news falls back to `reduce_date(day)`.
- **Gematria** — a letter-by-letter sum: Latin `A = 1 … Z = 26`, Cyrillic by alphabet position.
  Non-alphabet characters are ignored, case is irrelevant, and a text with no letters reads `0`.
- **Master number** — `11`, `22` or `33`: reduction stops there and does not continue to `2`, `4` or
  `6`. `MASTER_NUMBERS` is the only definition in the code.
- **Reading** — the result of `compute_numerology`: the gematria sum, the reduced value, and the
  rendered steps between them.
- **Reduction** — repeated digit sums until a single digit remains, with the master numbers as the
  only stop: `29 → 2 + 9 = 11` stops at 11.
- **Resonance** — a pattern whose evidence is that two or more activated numbers share a reading.
  One of the five `Pattern.type` values.
- **Sentinel** — `0` in the gematria layer means "no letters to sum"; it is not a value that can be
  reduced or vote for a dominant number.

## Pipeline and storage

- **Aggregator** — the `news` layer's `fetch_news`: it queries every configured source concurrently,
  filters the range once and de-duplicates on `(title, source, date)`.
- **Collection** — one Qdrant collection: `news`, `numbers`, `patterns`, `forecasts`,
  `number_history`, `digests`. See [`QDRANT_COLLECTIONS.md`](QDRANT_COLLECTIONS.md).
- **Digest** — a numerological summary of everything older than the sliding window, stored in
  `digests`. Opt-in via `Pipeline.summarize`.
- **Hybrid search** — in this project, dense retrieval with the payload filter inside a `Prefetch`
  and RRF fusion over the prefetch list. See [ADR 0007](adr/0007-qdrant-hybrid-search.md).
- **Ingest** — the first pipeline step: fetch, extract, compute, embed and store, writing `news`,
  `numbers` and `number_history` together. Idempotent by `news_id`.
- **Memory window** — `Pipeline.history_days`, thirty days by default: how far back the forecast may
  cite activations. Independent of the seven-day news window.
- **Payload index** — the Qdrant index over a payload field, created **before** the first point so a
  filter narrows the HNSW walk instead of post-filtering it.
- **Pipeline** — `numenews.pipeline`, the only layer that knows the order of the chain
  (`ingest → analyze → forecast`, with opt-in `summarize`). It owns no state; Qdrant does.
- **Point id** — a deterministic `uuid5` value: over a news URL for `news`, over its content for a
  pattern, over the date for a forecast. What makes re-running a command idempotent.
- **Sliding window** — the day and the six before it (`Pipeline.window_days`, seven by default). The
  news the pattern and forecast steps actually see.
- **Timing** — one `Timing` per pipeline step, returned inside the result rather than only logged,
  because the roadmap keeps step profiling as part of the answer.

## Interfaces and model calls

- **`AppContext`** — the lazily built container the MCP server and the CLI share: settings, the
  vector store, the extract agent, the pipeline and the cached news client, each built on first use.
- **JSON-only stdout** — the CLI's contract: exactly one JSON document per command on stdout, logs
  and progress on stderr. See [ADR 0005](adr/0005-json-only-output.md).
- **MCP** — the Model Context Protocol: a client (Cursor, Claude Desktop, a script) launches the
  server as a child process and calls its tools over JSON-RPC on stdio. See
  [`MCP_TOOLS.md`](MCP_TOOLS.md) and [ADR 0010](adr/0010-use-mcp-server.md).
- **`pydantic-ai`** — the agent runtime: an agent declares a result type, the model is asked for
  structured output, and the result is validated before it becomes a domain model.
  See [ADR 0004](adr/0004-pydantic-ai-choice.md).
- **RAG** — retrieval-augmented generation: the agents are shown retrieved news, stored patterns and
  activation history before they write a reading, instead of relying on their own memory.
  See [`RAG_PIPELINE.md`](RAG_PIPELINE.md).
- **Structured output** — the agent's answer as a declared Pydantic type, never free-form JSON
  parsed by hand. Enforced at every boundary.
- **`ToolError`** — the MCP failure shape for an expected condition, carrying a message the model can
  act on (`set OPENAI_API_KEY`, `start the server with make dev`). Only expected domain errors are
  translated; a bug stays a bug and is logged.

## Models, caching and evaluation

- **`bge`** — the embedding model family used locally: `BAAI/bge-small-en-v1.5` (384d) for
  `numbers`, `BAAI/bge-base-en-v1.5` (768d) for the paragraph-sized collections.
  See [`EMBEDDINGS.md`](EMBEDDINGS.md).
- **`fastembed`** — the local ONNX runtime wrapper that runs the `bge` models; the only place an
  embedding is computed. See [ADR 0008](adr/0008-fastembed-vs-openai.md).
- **Faithfulness** — a ragas metric: how much of the answer is supported by the retrieved contexts.
  The eval's floor is 0.7. See [`EVAL.md`](EVAL.md).
- **`hishel`** — the `httpx` cache used for the news feeds, in filter mode with a fifteen-minute
  storage TTL because none of the five APIs sends freshness headers.
  See [ADR 0009](adr/0009-hishel-caching.md).
- **RRF** — reciprocal rank fusion: `1 / (60 + rank)`, the score Qdrant uses to merge several
  prefetched rankings into one.
- **`.venv-eval`** — the isolated environment that holds `ragas` and its transitive LangChain
  dependencies, which cannot be resolved together with `pydantic-ai`.
  See [ADR 0013](adr/0013-eval-isolation.md).

## See also

- [`NUMEROLOGY.md`](NUMEROLOGY.md) — the rules with worked examples
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the layers these terms live in
- [`FAQ.md`](FAQ.md) — the questions the terms provoke
