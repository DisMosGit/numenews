# numenews

[![coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)](docs/coverage_report.md)
![python](https://img.shields.io/badge/python-3.14%2B-blue)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE.md)

**MCP server and one-shot CLI that reads the news numerologically.**

numenews fetches news from several public APIs, extracts numbers, dates and names, computes
numerology (digit reduction, master numbers 11/22/33, gematria), finds patterns with hybrid
vector search in Qdrant, and builds a daily forecast — while keeping every number activation as
long-term memory.

> **Status: v0.1.0 — phases 0–10 complete.** The tooling, configuration, logging, the domain models,
> the pure numerology layer, the five news sources behind one Protocol, the vector layer (the two
> local `bge` models, the six Qdrant collections, semantic and hybrid search), the four `pydantic-ai`
> agents (extract numbers, find patterns, build the forecast, summarise old news), the pipeline that
> composes them (`ingest → analyze → forecast`, with the sliding window and the digest), the MCP
> server with its nine tools, the one-shot CLI (`today`, `forecast`, `history`, `search`, `patterns`,
> `mcp`), the long-term memory of number activations (`number_history`, its per-day frequency and the
> forecast's thirty-day memory window), and the ragas evaluation in its isolated environment all
> exist. See [`ROADMAP.md`](ROADMAP.md) for the phase-by-phase plan and what is done.

## Quick start

```bash
uv sync --all-extras        # install the environment (Python 3.14+, uv)
make dev                    # start Qdrant (Docker Compose) and wait until healthy
cp .env.example .env        # optional: the default demo path needs no API keys
make lint && make test      # ruff + mypy --strict, pytest with coverage
```

Qdrant's dashboard is then at <http://localhost:6333/dashboard>.

## Quick start over the CLI

Every command answers with one JSON document on stdout and logs on stderr, so the output pipes
straight into `jq`. `today` needs Qdrant and an LLM endpoint; `history`, `search` and `patterns` need
Qdrant only. The full command surface is in [`docs/USER_FLOW.md`](docs/USER_FLOW.md).

```bash
uv run numenews today | jq .dominant_number   # ingest the window and read the day
uv run numenews forecast --date tomorrow      # a stored/derived reading, no fetch
uv run numenews history --number 11 --days 30 # when 11 was active
uv run numenews search -q "число 7 и деньги"  # hybrid search over stored news
uv run numenews patterns --min-strength 0.7   # the strong patterns, strongest first
uv run numenews --help
```

## Quick start over MCP

The server starts without Qdrant or an API key and builds each dependency on the first tool call
that needs it, so it can be attached to a host right away. Cursor's project config ships in
[`.cursor/mcp.json`](.cursor/mcp.json); Claude Desktop takes the same command in its own
`claude_desktop_config.json`. The nine tools, their examples and the failure semantics are in
[`docs/MCP_TOOLS.md`](docs/MCP_TOOLS.md).

```bash
make mcp                                            # serve stdio (Ctrl-D to stop)
uv run pytest tests/integration/test_mcp_stdio.py   # the same handshake, as a test
```

## Example output

This is the shape `numenews today` produces — the pipeline builds it, the CLI serializes it, and
stdout is always JSON, so it pipes straight into `jq`:

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

## Stack

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
```

## Commands

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

## Documentation

- [`ROADMAP.md`](ROADMAP.md) — phases 0–10, atomic tasks, definitions of done
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the layers, the data flow and the runtime topology
- [`docs/STACK.md`](docs/STACK.md) — every tool, why it was chosen and what it costs
- [`docs/TESTING.md`](docs/TESTING.md) — the test levels, the doubles and the coverage floors
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
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`docs/agentic/`](docs/agentic/) — how AI coding agents work here, and their guardrails
- [`AGENTS.md`](AGENTS.md) — the rules for AI coding agents in this repository
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branches, commits, local workflow

## License

[MIT](LICENSE.md)
