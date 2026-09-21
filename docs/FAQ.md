# FAQ

> Short answers with a pointer to the document that owns the detail. `ROADMAP.md` is the
> authoritative status.

## What is this, in one paragraph?

An MCP server and a one-shot CLI that fetch news, extract the numbers, dates and names in it, compute
a numerological reading (digit reduction, master numbers 11/22/33, gematria), find patterns across
articles with hybrid vector search in Qdrant, and write a daily reading — keeping every number
activation as long-term memory. See [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Why numerology?

Because it is a domain with real, testable rules — reduction, master numbers, gematria, date
resonance — that produce something to show without a large model budget, and because it makes a good
demonstration of a RAG system whose retrieval is measurably good. The product is the *pipeline*, not
a claim about the future. See [`NUMEROLOGY.md`](NUMEROLOGY.md) and
[ADR 0002](adr/0002-numerology-scope.md).

## Do I need API keys?

No, not for the default path. GDELT needs none, and embeddings run locally through `fastembed` with
no key and no network. The four other feeds (NewsAPI, GNews, Mediastack, Currents) and the LLM
endpoint are optional: the news layer queries every *configured* source, and the agents need an
OpenAI-compatible endpoint (`OPENAI_API_KEY`, or `OPENAI_BASE_URL` for a local server such as Ollama,
vLLM or LM Studio). See [`NEWS_SOURCES.md`](NEWS_SOURCES.md) and [`EVAL.md`](EVAL.md).

## Is this a prediction?

No. A "forecast" here is a numerological reading of a day assembled from retrieved news, patterns
and activation history; the model is instructed to ground its prose in that evidence, and the eval
measures exactly that faithfulness. The numbers are interpretation, not inference.

## How do I connect it to Cursor?

Cursor reads the project-scoped [`.cursor/mcp.json`](../.cursor/mcp.json), which runs
`uv run python -m numenews.mcp`. Restart Cursor and the nine tools appear. Claude Desktop needs the
same entry with the absolute path of your checkout in its own `claude_desktop_config.json`; the
JSON for both is in [`MCP_TOOLS.md`](MCP_TOOLS.md#connecting-a-client). Without a GUI,
`make mcp` serves the same server over stdio.

## Which tool should I use — MCP or the CLI?

The CLI when you want one machine-readable answer, or when you need to ingest (fetch **and** store) a
window; MCP when a host is driving the conversation. The two share the same container and code. The
selection logic per question is in [`TOOL_USE.md`](TOOL_USE.md).

## What does "hybrid search" mean here?

Dense retrieval with the payload filter applied *inside* each `Prefetch`, fused with reciprocal rank
fusion. Phase 3 has one retriever, so the fusion merges a single ranking; the shape is what makes a
sparse/BM25 retriever a second entry in the same list. See
[ADR 0007](adr/0007-qdrant-hybrid-search.md).

## Why is the corpus English? Can it read Russian news?

The local `bge-*-en-v1.5` models are English. The numerology layer handles Cyrillic gematria and
Russian date strings, and Russian text is stored and reduced, but semantic search is only as good as
the model's language. The eval corpus is English for the same reason. See
[`EMBEDDINGS.md`](EMBEDDINGS.md) and [ADR 0008](adr/0008-fastembed-vs-openai.md).

## What happens when a feed or the LLM is down?

The pipeline degrades instead of failing silently: one news source failing thins the result, the
extract agent falls back to the regex pass, and a pattern/forecast model failure is retried once and
then reported as a named error — nothing is fabricated or stored. Qdrant being unreachable fails the
health check before the first step. See [`RAG_PIPELINE.md`](RAG_PIPELINE.md).

## How much does a run cost?

One `numenews today` makes a handful of HTTP requests (cached for fifteen minutes) and a few LLM
calls; embeddings cost CPU time and a one-off ~286 MB model download. There is no per-query
embedding bill by design.

## Where does my data live?

In Qdrant, in the Docker named volume (`numenews-qdrant`, dashboard at
<http://localhost:6333/dashboard>), plus two local caches: `.cache/hishel` (the feed cache) and
`.cache/fastembed` (the model weights). Nothing is sent anywhere except the news APIs you configured
and the LLM endpoint you configured.

## How do I reset state?

`make clean` stops Qdrant, deletes its volume and removes the local caches (including `.venv-eval`).
`make dev-down` stops the container but keeps the volume.

## Can I add a news source or an agent?

Yes — a new feed implements the `NewsSource` Protocol and is registered with the aggregator; a new
agent follows the existing four and its prompt goes in `docs/PROMPTS.md`. Both are
architecturally visible changes, so they need an ADR and a ROADMAP task, not a quiet patch.

## Why is the coverage badge a static number?

There is no CI/CD in this project by design (`AGENTS.md`), so nothing regenerates a badge
automatically. The number is kept honest by [`coverage_report.md`](coverage_report.md), which records
the dated run and the command behind it, and by the per-layer floors that `make test` enforces
([`TESTING.md`](TESTING.md)).

## How do I run the evaluation?

`make test-eval` builds `.venv-eval` if needed and runs `tests/eval`; the ragas half needs a
configured LLM endpoint and skips with a message when there is none, while the deterministic
retrieval half always runs. See [`EVAL.md`](EVAL.md).

## Where is the project going next?

`ROADMAP.md` — phases 0–10 are planned there, one atomic commit per task. Anything not in the
roadmap is not a plan yet.
