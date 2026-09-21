# Contributing

## Branches

`main` is protected. Use short-lived branches:

- `feat/<name>` — new feature
- `fix/<name>` — bug fix
- `chore/<name>` — tooling, deps
- `docs/<name>` — documentation
- `refactor/<name>` — refactoring
- `test/<name>` — tests only

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `chore`, `revert`.

Scopes: `numerology`, `news`, `embeddings`, `vector`, `agents`, `mcp`, `cli`, `models`, `docs`, `deps`.

Examples:

```
feat(numerology): add master number 33 reduction
fix(vector): apply payload filter inside Prefetch for hybrid search
docs(adr): add ADR-0004 qdrant hybrid search
```

## Local development

Requirements: Python 3.14+, [uv](https://docs.astral.sh/uv/), Docker + Compose v2.

```bash
uv sync --all-extras
docker compose up -d qdrant
cp .env.example .env
uv run pre-commit install
```

Common commands:

```bash
make install    # uv sync
make lint       # ruff + mypy --strict
make test       # unit + integration
make test-eval  # ragas eval in .venv-eval (needs an LLM endpoint; docs/EVAL.md)
make eval-env   # build .venv-eval (ragas cannot share an env with pydantic-ai; ADR 0013)
make run        # sample one-shot CLI
make mcp        # start MCP server (stdio)
make clean      # stop Qdrant, drop volumes
```

## Pull requests

1. Rebase on `main`.
2. Run `make lint && make test`.
3. Update `CHANGELOG.md` under `[Unreleased]` if user-facing.
4. Add an ADR in `docs/adr/` for architectural decisions.
5. One logical change per PR. Squash-merge.

## Code style

- Ruff (lint + format), Mypy strict, full type hints.
- Async everywhere; no blocking calls in the event loop.
- Pydantic v2 for all boundaries: MCP tools, agents, config.
- No `print()` — use `structlog` (JSON to stderr).
- CLI stdout is JSON only.

Import rules:

```
numerology ← depends on nothing
models     ← depends on nothing
news       ← depends on models
embeddings ← depends on models
vector     ← depends on models
agents     ← depends on numerology + models
mcp        ← depends on all
cli        ← depends on all
```

No `import-linter` is installed or configured. The guard is the subprocess/AST tests in
`tests/unit/test_numerology_api.py`
(`test_numerology_does_not_import_the_layers_above_it`,
`test_models_depend_on_nothing_beyond_the_package_root`), together with the layer table in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the rule in [`AGENTS.md`](AGENTS.md). The naming
and layering conventions that go with them are in
[`docs/agentic/CONVENTIONS.md`](docs/agentic/CONVENTIONS.md), and the prohibitions an agent must
respect when touching a layer are in
[`docs/agentic/GUARDRAILS.md`](docs/agentic/GUARDRAILS.md).

## Tests

| Level | Path | Marker |
|-------|------|--------|
| Unit | `tests/unit/` | — |
| Integration | `tests/integration/` | `@pytest.mark.integration` |
| Eval (RAG) | `tests/eval/` | `@pytest.mark.eval` |

No `time.sleep()` — use `freezegun` or `anyio`. Qdrant tests use `:memory:`.
