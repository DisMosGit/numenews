# Contributing

It is a pet project, so this is short. The one rule that matters: **work starts as an OpenSpec
change, not as an edit to the code.**

## The workflow

New behaviour goes through [`openspec/`](openspec/), and the loop has four steps:

1. **Propose** — `/openspec-propose` (or `openspec new change "<name>"`) writes a change under
   [`openspec/changes/`](openspec/changes/): why it is worth doing, which capabilities it touches,
   the spec deltas, a design when the approach needs deciding, and a `tasks.md`.
2. **Review** — read the artifacts, not just the diff, and make `openspec validate "<name>" --strict`
   pass. If the plan is wrong, fix the plan; do not start coding around it.
3. **Implement** — one `tasks.md` item per atomic task, its checkbox ticked as part of that task. If a
   task turns out to be bigger than its spec delta describes, stop and update the artifacts rather
   than widening it silently.
4. **Archive** — `openspec archive "<name>"` once every box is ticked. That merges the spec deltas
   into [`openspec/specs/`](openspec/specs/), which is what makes the new behaviour the documented
   baseline.

Not every thought is a change yet. An idea with no proposal belongs in a GitHub issue, and the issue
templates route feature requests back to step 1.

The specs in `openspec/specs/` describe *behaviour* — inputs, outputs, error conditions, defaults and
guarantees, each with testable scenarios. Narrative documentation (how to use a tool, what a JSON
payload looks like) stays in `docs/`, and the two cross-reference each other rather than duplicating.

### Where the old roadmap went

Until `v0.1.0` the work was sequenced by a root `ROADMAP.md`, phase by phase. It is gone, and not
archived anywhere on purpose: every commit it sequenced is in `git log`, the `v0.1.0` tag marks the
end of it, and the archived [`adopt-openspec-workflow`](openspec/changes/archive/) change records how
each phase was carried over. The ADRs and the "How it was built" narrative in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) still use phase numbers — that is history, and it is
fine.

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

The subject is the whole message: no body. Write one only when explicitly asked for it — the reason
belongs in the change's artifacts or an ADR, not in `git log`.

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
3. Add an ADR in `docs/adr/` for architectural decisions.
4. One logical change per PR. Squash-merge.

## Releases

There is deliberately no `CHANGELOG.md`. A release is a tag, and its content is `git log`;
`version` in `pyproject.toml` is the version number. The history written before 0.2 lives in that
file's last committed state, which the `v0.1.0` tag still holds:

```bash
git show v0.1.0:CHANGELOG.md
```

Release notes in any other form — annotated tag messages, GitHub Releases, a history page under
`docs/` — are a new change to propose, not a restore.

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
