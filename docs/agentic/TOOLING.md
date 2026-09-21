# Tooling

> Phase 10.2. The tools actually used to build and check this repository, and the commands that stand
> in for the CI that deliberately does not exist. The conventions they enforce are in
> [`CONVENTIONS.md`](CONVENTIONS.md); the commands a review re-runs are in
> [`EVAL_OF_AGENT.md`](EVAL_OF_AGENT.md).

## Environment and packaging

One package, `numenews`, in a `src/` layout, on Python 3.14+, managed by
[`uv`](https://docs.astral.sh/uv/) and pinned by the committed `uv.lock`. `pyproject.toml` declares
the runtime dependencies, a `dev` dependency group (pytest, mypy, ruff, hypothesis, respx,
pre-commit, pytest-cov) and the `uv_build` backend; the comment above `dependencies` records which
phase introduced each package, and a dependency is added only by the phase that first imports it.

```bash
uv sync --all-extras        # make install — the only setup step
uv run numenews --version
uv run python -m numenews.cli
```

`uv run <tool>` always uses the versions in `uv.lock`, so a tool is never invoked from a global
install.

## Makefile

`make` with no target prints the self-documenting help; `.DEFAULT_GOAL := help`. Every target below is
verified against the `Makefile`:

| Target | Runs |
|---|---|
| `install` | `uv sync --all-extras` |
| `lint` | `ruff check .`, `ruff format --check .`, `mypy .` (strict) |
| `format` | `ruff format .`, `ruff check --fix .` |
| `test` | `pytest tests/unit tests/integration --cov=numenews --cov-report=term-missing`, then `coverage-check` |
| `test-unit` | `pytest tests/unit` |
| `test-integration` | `pytest tests/integration -m integration` |
| `test-eval` | builds `.venv-eval` if missing, then runs `pytest tests/eval -v --run-eval` with `RAGAS_DO_NOT_TRACK=true` |
| `eval-env` | builds `.venv-eval`: the lock without `pydantic-ai-slim`, plus `tests/eval/requirements-eval.txt` |
| `coverage` | `pytest … --cov-report=html:docs/coverage.html` |
| `coverage-check` | one `coverage report --include=… --fail-under=… --format=total` per layer group |
| `dev` | `docker compose up -d --wait --wait-timeout 180` |
| `dev-down` | `docker compose down` (keeps the volume) |
| `mcp` | `uv run python -m numenews.mcp` (silenced, stdio) |
| `run` | `uv run numenews today` (silenced; needs Qdrant and an LLM endpoint) |
| `clean` | `docker compose down -v --remove-orphans`, then removes `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.cache`, `htmlcov`, `.coverage`, `docs/coverage.html` and `.venv-eval` |

`make lint && make test` is the gate every commit has to pass. `mcp` and `run` are prefixed with `@`
on purpose: make would otherwise echo its recipe into stdout and break the "stdout carries JSON (or
JSON-RPC) and nothing else" contract. `make test` ends with `make coverage-check`, which enforces the
per-layer floors of ROADMAP 10.4; `pyproject.toml` keeps `fail_under = 0` because coverage.py has no
per-path threshold and the Makefile passes `--fail-under` once per include group instead.

## Ruff and mypy

- **Ruff** formats and lints: `line-length = 100`, `target-version = "py314"`, and a curated rule set
  (`E, W, F, I, N, UP, B, A, C4, SIM, ANN, RUF, PTH`) with `ANN401` ignored because `Any` is banned
  outright by `AGENTS.md`. `per-file-ignores` disables `RUF001/002/003` only where Cyrillic text is
  deliberate (`numerology/gematria.py`, `agents/prompts.py` and their tests).
- **Mypy** runs `strict = true` with the `pydantic.mypy` plugin (`init_typed`, `init_forbid_extra`),
  `mypy_path = ["src"]` and an override that ignores the missing `ragas` imports, which live only in
  `.venv-eval`.
- `.pre-commit-config.yaml` runs `ruff check --fix`, `ruff format` and a whole-project `uv run mypy .`
  through `uv` (so they match the lock), plus `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`,
  `check-merge-conflict` and `check-added-large-files --maxkb=1024`. Install it once with
  `uv run pre-commit install`; run everything with `uv run pre-commit run --all-files`.

## pytest

`pytest` is configured in `pyproject.toml`: `asyncio_mode = "auto"` (no `@pytest.mark.asyncio`
needed), `asyncio_default_fixture_loop_scope = "function"`, `testpaths = ["tests"]` and
`--strict-markers --strict-config`.

| Marker | Where | Gate |
|---|---|---|
| *(none)* | `tests/unit/` | always runs; no network, no `time.sleep` |
| `integration` | `tests/integration/` | always runs; Qdrant `:memory:` or Docker, HTTP and LLMs mocked |
| `eval` | `tests/eval/` | only with `--run-eval`, which `make test-eval` passes; needs an LLM endpoint |

The `--run-eval` flag is registered in `tests/conftest.py`, which also holds the hermetic `settings`
and `tmp_cache_dir` fixtures and the in-memory Qdrant fixtures. The eval suite is documented in
[`../EVAL.md`](../EVAL.md).

## Docker Compose, Qdrant and the two environments

`docker-compose.yml` runs `qdrant/qdrant:v1.19.1` with the HTTP port `6333`, the gRPC port `6334`, a
named `qdrant_storage` volume and a TCP-Probe healthcheck (the image has no `curl`). `make dev` waits
until it is healthy; `make dev-down` stops it; `make clean` also drops the volume.

There are two virtual environments, on purpose (ADR 0013,
[`../adr/0013-eval-isolation.md`](../adr/0013-eval-isolation.md)):

- **`.venv`** — the locked runtime plus dev tools, used by `uv run` and every `make` target except the
  eval. `ragas`, and therefore LangChain, never enters it or `uv.lock`.
- **`.venv-eval`** — gitignored, built by `make eval-env`, holding the lock minus `pydantic-ai-slim`
  plus ragas. `make test-eval` calls `.venv-eval/bin/python` directly, because `uv run` would sync the
  environment back to the lock and prune ragas.

## The MCP server as an editor tool

The server is a normal stdio child process, launched by the editor from `.cursor/mcp.json`:

```json
{"mcpServers": {"numenews": {"command": "uv", "args": ["run", "python", "-m", "numenews.mcp"]}}}
```

`make mcp` runs the same process from a terminal. The nine tools, their argument schemas, their
failures and the Claude Desktop equivalent are in [`../MCP_TOOLS.md`](../MCP_TOOLS.md); the automated
stand-in for a manual client check is `tests/integration/test_mcp_stdio.py`.

## The agent harness

Agents work this repository through the DeepSeek Harness CLI, `dsh` (a Node tool installed outside the
project, not a `uv` dependency and not part of `uv.lock`). `dsh web` boots the web GUI, `dsh --profile
tui` a terminal client, and `dsh --profile headless "<task>"` answers one task and exits; whichever
profile is used, the harness reads `AGENTS.md` and the workspace, and the rules in
[`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md) apply unchanged. The harness checkout is separate from this
working directory; nothing in the package imports or depends on it.

## One task end to end

```bash
make install                          # once
docker compose up -d qdrant           # or make dev, when the task needs the vector layer
# 1. pick the task in ROADMAP.md, read AGENTS.md and the docs it names
# 2. plan (PROMPTING_PLAYBOOK.md, prompt 1), then implement (prompt 2)
make format                           # optional: apply ruff fixes while iterating
make lint && make test                # the gate; test ends with the per-layer coverage floors
make test-eval                        # only when the eval is touched
make coverage && open docs/coverage.html
make dev && uv run numenews today     # the live check, when the task needs it
# 3. tick the checkboxes, update CHANGELOG.md and the docs, one atomic commit
```

## No CI/CD, by design

There is no `.github/workflows` and no pipeline configuration: `AGENTS.md` rules CI/CD, Kubernetes and
Terraform out of scope. The local commands are the gate, which is why every task's Definition of Done
is phrased as a command that must pass and why a review re-runs `make lint`, `make test` and
`make test-eval` rather than trusting a report.
