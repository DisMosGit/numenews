# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

**numenews** — MCP server and one-shot CLI that fetches news, extracts numbers, dates, and names, computes numerology (reduction, master numbers 11/22/33, gematria), and finds patterns via hybrid search in Qdrant. Builds a daily numerology forecast and keeps number activation history as long-term memory.

## Stack

- Python 3.14+, `uv` (single package, src-layout)
- MCP Python SDK v2 (`MCPServer`) + `pydantic-ai`
- Qdrant (Docker Compose) + `fastembed` (local embeddings)
- `httpx` + `hishel` (RFC 9111 cache), `pydantic-settings`, `structlog`
- Typer + Rich for CLI (JSON-only stdout)
- Ruff + Mypy (strict) + pytest-asyncio + respx + hypothesis + ragas
- Makefile for all developer commands

## Layout

- `src/numenews/numerology/` — pure domain logic: reduction, master numbers, gematria (no I/O)
- `src/numenews/news/` — adapters for GDELT, NewsAPI, GNews, Mediastack, Currents behind one Protocol
- `src/numenews/embeddings/` — `fastembed` wrapper (384d and 768d)
- `src/numenews/vector/` — Qdrant client, collections, hybrid search, payload-index setup
- `src/numenews/agents/` — `pydantic-ai` agents: extract, pattern, forecast, summarize
- `src/numenews/mcp/` — MCP server (`MCPServer`), the nine tools and the `AppContext`
- `src/numenews/cli/` — one-shot Typer commands
- `src/numenews/models/` — Pydantic v2 domain models
- `docs/` — architecture, ADRs, MCP tools, Qdrant schema, RAG pipeline
- `tests/` — unit, integration, eval

## Rules

- Numerology layer is pure: no imports from `news`, `vector`, `agents`, or `mcp`.
- Every MCP tool returns a Pydantic model — no dicts, no dataclasses across boundaries.
- All LLM calls go through `pydantic-ai` agents; no raw SDK calls.
- All embeddings are local via `fastembed`; no external embedding APIs.
- Qdrant payload indexes must exist before ingest; filters go inside `Prefetch` for hybrid search.
- CLI stdout is JSON only. Logs and progress go to stderr via `structlog`.
- State lives in Qdrant, not in process memory — one-shot commands must be idempotent.
- Type hints are mandatory. `mypy --strict` must pass.
- No `Any`, no `# type: ignore` without an inline comment explaining why.
- No API keys required for the default demo path; `.env` only for optional news APIs.

## Roadmap

`ROADMAP.md` is the single source of truth for what is built and in what order: phases 0–10, one atomic commit per task, Definition of Done per task. Statuses are `[ ]` not started, `[~]` in progress, `[x]` done, `[-]` cancelled.

- Do not start a phase before the previous one is closed; tasks inside a phase are independent unless a `depends on` is given.
- A task is not done until its DoD holds and its checkboxes are ticked in `ROADMAP.md`.
- Architectural decisions get an ADR in `docs/adr/` (`template.md`); the reason is recorded, never only the change.
- `.docs/plan.md` is the private design brief (gitignored). Where it disagrees with this file or `ROADMAP.md`, the latter two win: the package is `numenews`, the CLI is `numenews`, not `numerology_news`/`nn`.

## Commands

Both interfaces are implemented: the MCP server and its nine tools (Phase 6), served by `make mcp`
over stdio, and the one-shot CLI (Phase 7), whose commands each print one JSON document on stdout.
`make run` exercises `numenews today`, which needs Qdrant and an LLM endpoint.

```
uv sync --all-extras           # install
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy .                  # typecheck (strict is configured in pyproject.toml)
uv run pytest tests/unit tests/integration -v
make test-eval                 # ragas eval in .venv-eval (needs an LLM endpoint; docs/EVAL.md)
make eval-env                  # build .venv-eval: ragas, isolated from pydantic-ai (ADR 0013)
docker compose up -d --wait qdrant   # start Qdrant
uv run numenews today          # sample one-shot CLI run (needs Qdrant + an LLM endpoint)
uv run numenews --help         # the six commands (today, forecast, history, search, patterns, mcp)
uv run numenews mcp            # start MCP server, stdio
make install lint test run mcp # shortcut targets
```

## When changing code

- Add an ADR in `docs/adr/` for any architectural decision.
- Update `docs/MCP_TOOLS.md` when adding or renaming an MCP tool.
- Update `docs/QDRANT_COLLECTIONS.md` when changing a collection or payload schema.
- Update `docs/PROMPTS.md` when changing extract, pattern, or forecast prompts.
- Write a unit test for numerology logic; an integration test for I/O (respx + Qdrant `:memory:`).
- Keep commits conventional: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`.

## Do not

- Add external embedding APIs or cloud vector DBs — local-only is a design constraint.
- Bypass `pydantic-ai` structured output with free-form JSON parsing.
- Put numerology logic in agents or CLI handlers — it belongs in `numerology/`.
- Add CI/CD, Kubernetes, or Terraform — out of scope.
- Introduce LangChain, LlamaIndex, or LangGraph — `pydantic-ai` is the chosen orchestrator. The one
  exception is the ragas evaluation, whose dependency tree pulls LangChain transitively; it is kept
  out of `.venv`, `uv.lock` and `[project]` and lives only in the isolated `.venv-eval` (ADR 0013).
