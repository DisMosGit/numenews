# numenews

[![coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)](docs/coverage_report.md)
![python](https://img.shields.io/badge/python-3.14%2B-blue)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE.md)

**MCP server and one-shot CLI that reads the news numerologically.**

numenews fetches news from several public APIs, extracts numbers, dates and names, computes
numerology (digit reduction, master numbers 11/22/33, gematria), finds patterns with hybrid
vector search in Qdrant, and builds a daily forecast — while keeping every number activation as
long-term memory.

It is a pet project that takes its subject seriously and itself not very: the numerology layer is
pure, deterministic and property-tested, the retrieval is a real hybrid search over a real vector
store, and the default demo path needs no API keys at all. `v0.1.0` is out and both interfaces work.

## What it does

- **Nine MCP tools** over stdio, so Claude Desktop, Cursor or any MCP host can fetch news, extract
  numbers, find patterns, build a forecast and query the memory.
- **Six one-shot commands** — `today`, `forecast`, `history`, `search`, `patterns`, `mcp` — each
  printing one JSON document on stdout and nothing else, so they pipe straight into `jq`.
- **Five news sources** (GDELT, NewsAPI, GNews, Mediastack, Currents) behind one `NewsSource`
  Protocol, with an aggregator that degrades gracefully when a feed is down or rate-limited, and an
  RFC 9111 cache so a repeated run does not re-hit the network.
- **Local embeddings only** — two `bge` models through `fastembed`. No embedding API, ever.
- **Six Qdrant collections** with semantic and hybrid (reciprocal-rank-fusion) search, and payload
  indexes that make filtered queries cheap.
- **Four `pydantic-ai` agents** — extract numbers, find patterns, build the forecast, summarise old
  news — every one returning a validated Pydantic model rather than free-form JSON.
- **A pipeline that composes them**: `ingest → analyze → forecast`, with a sliding window over the
  last week and a digest for everything older.
- **Long-term memory**: every number activation is logged, folded into a per-day frequency, and fed
  back into the forecast over a thirty-day window.
- **A ragas evaluation** of the retrieval path, isolated in its own environment so LangChain never
  reaches the runtime.

## Quick start

```bash
uv sync --all-extras        # install the environment (Python 3.14+, uv)
make dev                    # start Qdrant (Docker Compose) and wait until healthy
cp .env.example .env        # optional: the default demo path needs no API keys
make lint && make test      # ruff + mypy --strict, pytest with coverage
```

Qdrant's dashboard is then at <http://localhost:6333/dashboard>.

### Over the CLI

`today` needs Qdrant and an LLM endpoint; `history`, `search` and `patterns` need Qdrant only. The
full command surface is in [`docs/USER_FLOW.md`](docs/USER_FLOW.md).

```bash
uv run numenews today | jq .dominant_number   # ingest the window and read the day
uv run numenews forecast --date tomorrow      # a stored/derived reading, no fetch
uv run numenews history --number 11 --days 30 # when 11 was active
uv run numenews search -q "число 7 и деньги"  # hybrid search over stored news
uv run numenews patterns --min-strength 0.7   # the strong patterns, strongest first
uv run numenews --help
```

### Over MCP

The server starts without Qdrant or an API key and builds each dependency on the first tool call
that needs it, so it can be attached to a host right away. Cursor's project config ships in
[`.cursor/mcp.json`](.cursor/mcp.json); Claude Desktop takes the same command in its own
`claude_desktop_config.json`. The nine tools, their examples and the failure semantics are in
[`docs/MCP_TOOLS.md`](docs/MCP_TOOLS.md).

```bash
make mcp                                            # serve stdio (Ctrl-D to stop)
uv run pytest tests/integration/test_mcp_stdio.py   # the same handshake, as a test
```

### What the output looks like

The pipeline builds this, the CLI serializes it, and stdout is always JSON:

```json
{
  "date": "2026-09-21",
  "dominant_number": 11,
  "master_active": true,
  "patterns": [
    {
      "id": "8bb3a3e4-53cd-5333-92ab-5309c63d3b78",
      "type": "resonance",
      "numbers": [11, 22],
      "news_ids": ["b371bc46-7b4b-5b38-92db-cdf94a550f33"],
      "strength": 0.87,
      "interpretation": "Числа 11 и 22 резонируют в новостях о технологиях",
      "discovered_at": "2026-09-21T12:00:00Z"
    }
  ],
  "forecast": "День благоприятен для начинаний, связанных с коммуникацией",
  "advice": "Избегайте конфликтов — число 11 усиливает эмоции",
  "warnings": ["Возможны повторяющиеся события из прошлого"]
}
```

## How OpenSpec is used here

Specs are the source of truth for behaviour, and they live in the repository next to the code.

- [`openspec/specs/`](openspec/specs/) holds what the project **ships** today, one capability per
  directory. Two exist so far: `mcp-surface` (the nine tools — inputs, return shapes, error
  reporting) and `cli-surface` (the six commands — JSON-only stdout, the `--date` grammar, exit
  codes, idempotency). The internals are not specified yet; they get a capability the first time a
  change really touches them.
- [`openspec/changes/`](openspec/changes/) holds work **in flight**: a proposal, the spec deltas it
  would make, a design when the approach needs deciding, and a task list.
- The loop is **propose → review → implement → archive**. `openspec list` shows what is active,
  `openspec validate "<name>" --strict` checks a change, and archiving merges its spec deltas into
  `openspec/specs/`.
- New work starts as a change, not as an edit. An idea that is not a change yet lives in a GitHub
  issue.

`docs/MCP_TOOLS.md` and `docs/USER_FLOW.md` remain the narrative companions to the two specs: the
specs say what the behaviour must be, those documents show how to use it.

## Project layout

```
src/numenews/
├── config.py       # pydantic-settings
├── logging.py      # structlog + contextvars correlation
├── models/         # Pydantic v2 domain models
├── numerology/     # pure logic: reduction, master numbers, gematria (no I/O)
├── news/           # GDELT, NewsAPI, GNews, Mediastack, Currents behind one Protocol
├── embeddings/     # fastembed wrapper
├── vector/         # Qdrant client, collections, hybrid search
├── agents/         # pydantic-ai: extract, pattern, forecast, summarize
├── pipeline/       # the RAG chain, the sliding window, step timings
├── mcp/            # MCP server and 9 tools
└── cli/            # one-shot Typer commands

openspec/
├── specs/          # behaviour that ships, one capability per directory
└── changes/        # proposals in flight
```

| Layer | Choice |
|---|---|
| Package manager | `uv`, single package, `src/` layout |
| Types | `pydantic` v2 + `mypy --strict` |
| Vector store | Qdrant (Docker Compose; `:memory:` in tests) |
| Embeddings | `fastembed` (`bge-small-en-v1.5` 384d, `bge-base-en-v1.5` 768d) — local, no API keys |
| LLM orchestration | `pydantic-ai` with structured output |
| MCP server | Python `mcp` SDK v2 (`MCPServer`), nine tools over stdio |
| HTTP | `httpx` + `hishel` (RFC 9111 cache) + `tenacity` |
| Config / logs | `pydantic-settings` / `structlog` (stderr, JSON in prod) |
| CLI | Typer + Rich, **JSON-only stdout** |
| Tests | `pytest` + `pytest-asyncio` + `respx` + `hypothesis` + `ragas` (eval) |

### Commands

```bash
make help          # list every target
make install       # uv sync --all-extras
make lint          # ruff check + format check + mypy
make test          # unit + integration (with coverage)
make test-eval     # ragas evaluation in .venv-eval (needs an LLM endpoint; see docs/EVAL.md)
make eval-env      # build .venv-eval (ragas; ADR 0013)
make dev           # docker compose up -d --wait
make dev-down      # stop Qdrant, keep the volume
make clean         # stop Qdrant, delete volumes and caches
make run           # sample one-shot CLI run (needs Qdrant and an LLM endpoint)
make mcp           # start the MCP server (stdio)
```

`make test` runs the unit and integration suites with coverage and then checks the per-layer floors
(numerology ≥ 95 %, pipeline/agents ≥ 80 %, vector/news ≥ 70 %); the levels, the doubles and the
dated coverage snapshot are in [`docs/TESTING.md`](docs/TESTING.md).

### Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the layers, the data flow and the runtime topology
- [`docs/STACK.md`](docs/STACK.md) — every tool, why it was chosen and what it costs
- [`docs/TESTING.md`](docs/TESTING.md) — the test levels, the doubles and the coverage floors
- [`docs/coverage_report.md`](docs/coverage_report.md) — the dated coverage snapshot and the floors
- [`docs/TOOL_USE.md`](docs/TOOL_USE.md) — which MCP tool answers which question
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — MCP, RAG, gematria, master number and the rest
- [`docs/FAQ.md`](docs/FAQ.md) — "why numerology?", "do I need API keys?", "how do I connect Cursor?"
- [`docs/NUMEROLOGY.md`](docs/NUMEROLOGY.md) — terminology and rules
- [`docs/NEWS_SOURCES.md`](docs/NEWS_SOURCES.md) — the five news APIs, their limits and the cache
- [`docs/QDRANT_COLLECTIONS.md`](docs/QDRANT_COLLECTIONS.md) — the six collections, payloads and indexes
- [`docs/EMBEDDINGS.md`](docs/EMBEDDINGS.md) — the local models, the cache and why two of them
- [`docs/PROMPTS.md`](docs/PROMPTS.md) — every agent prompt, verbatim, with its rationale
- [`docs/RAG_PIPELINE.md`](docs/RAG_PIPELINE.md) — the chain, its degradation rules and its tests
- [`docs/CONTEXT_MANAGEMENT.md`](docs/CONTEXT_MANAGEMENT.md) — the window, the history and the digest
- [`docs/MCP_TOOLS.md`](docs/MCP_TOOLS.md) — the nine MCP tools, their examples and the client configs
- [`docs/USER_FLOW.md`](docs/USER_FLOW.md) — the one-shot CLI, its commands and their JSON
- [`docs/EVAL.md`](docs/EVAL.md) — the ragas evaluation: how to run it and how to read the report
- [`docs/eval_report.md`](docs/eval_report.md) — the latest committed eval run
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`docs/agentic/`](docs/agentic/) — how AI coding agents work here, and their guardrails
- [`AGENTS.md`](AGENTS.md) — the rules for AI coding agents in this repository

## Contributing

It is a solo pet project, so there is no ceremony — but there is a workflow, and
[`CONTRIBUTING.md`](CONTRIBUTING.md) spells it out. The short version: work starts as an OpenSpec
change rather than a direct edit, one `tasks.md` item is one atomic task, and `make lint && make
test` has to be green. Issues and ideas are welcome; there is no CI, on purpose, which is why the
commands are the gate.

## License

[MIT](LICENSE.md)
