# numenews

**MCP server and one-shot CLI that reads the news numerologically.**

numenews fetches news from several public APIs, extracts numbers, dates and names, computes
numerology (digit reduction, master numbers 11/22/33, gematria), finds patterns with hybrid
vector search in Qdrant, and builds a daily forecast — while keeping every number activation as
long-term memory.

> **Status: Phase 2 — news sources.** The tooling, configuration, logging, the domain models, the
> pure numerology layer and the five news sources behind one Protocol exist; the vector layer,
> agents, MCP server and CLI land in phases 3–10. See [`ROADMAP.md`](ROADMAP.md) for the
> phase-by-phase plan and what is done.

## Quick start

```bash
uv sync --all-extras        # install the environment (Python 3.14+, uv)
make dev                    # start Qdrant (Docker Compose) and wait until healthy
cp .env.example .env        # optional: the default demo path needs no API keys
make lint && make test      # ruff + mypy --strict, pytest with coverage
```

Qdrant's dashboard is then at <http://localhost:6333/dashboard>.

## Example output

This is the shape `numenews today` will produce once the pipeline lands (Phase 7); stdout is
always JSON, so it pipes straight into `jq`:

```json
{
  "date": "2026-09-21",
  "dominant_number": 11,
  "master_number_active": true,
  "patterns": [
    {
      "type": "resonance",
      "numbers": [11, 22],
      "strength": 0.87,
      "interpretation": "Числа 11 и 22 резонируют в новостях о технологиях"
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
| MCP server | Python `mcp` SDK (`FastMCP`) |
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
├── agents/         # pydantic-ai: extract, pattern, forecast
├── mcp/            # MCP server and 9 tools
└── cli/            # one-shot Typer commands
```

## Commands

```bash
make help          # list every target
make install       # uv sync --all-extras
make lint          # ruff check + format check + mypy
make test          # unit + integration (with coverage)
make test-eval     # ragas evaluation (needs --run-eval)
make dev           # docker compose up -d --wait
make dev-down      # stop Qdrant, keep the volume
make clean         # stop Qdrant, delete volumes and caches
make run           # sample one-shot CLI run
make mcp           # start the MCP server (stdio)
```

## Documentation

- [`ROADMAP.md`](ROADMAP.md) — phases 0–10, atomic tasks, definitions of done
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layers and data flow
- [`docs/NUMEROLOGY.md`](docs/NUMEROLOGY.md) — terminology and rules
- [`docs/NEWS_SOURCES.md`](docs/NEWS_SOURCES.md) — the five news APIs, their limits and the cache
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`AGENTS.md`](AGENTS.md) — how AI coding agents work in this repository
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branches, commits, local workflow

## License

[MIT](LICENSE.md)
