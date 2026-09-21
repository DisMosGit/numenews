# Guardrails: what an agent must not do

> Phase 10.2. The hard prohibitions, each with the reason it exists, the rule that owns it and what to
> do instead. Most come from the `Do not` list in [`AGENTS.md`](../../AGENTS.md) or the import rules
> in [`CONTRIBUTING.md`](../../CONTRIBUTING.md); the architectural ones have an ADR in
> [`../adr/`](../adr/). Breaking one of these is not a style discussion — it is a defect, and it is
> reverted rather than negotiated. The conventions these rules protect are in
> [`CONVENTIONS.md`](CONVENTIONS.md).

**No external embedding API and no cloud vector database.**
*Why:* local-only embeddings are a design constraint, not a fallback: the default demo path needs no
API keys, and the vector layer must work offline. *Owner:* `AGENTS.md` (`Do not`), ADR 0003
(`docs/adr/0003-local-embeddings.md`) and ADR 0008 (`docs/adr/0008-fastembed-vs-openai.md`).
*Instead:* embed through the `Embedder` Protocol in `src/numenews/embeddings/`, which wraps the two
local `fastembed` `bge` models (384d and 768d), and keep vectors in the Qdrant instance from
`docker-compose.yml`.

**No raw LLM SDK calls and no free-form JSON parsing of a model answer.**
*Why:* structured output is what makes an agent's answer a typed domain object; `openai`, `anthropic`
and `httpx` calls that parse JSON by hand bypass validation and cannot be tested with a scripted
model. *Owner:* `AGENTS.md` (`All LLM calls go through pydantic-ai`), ADR 0004
(`docs/adr/0004-pydantic-ai-choice.md`). *Instead:* add or change an agent in `src/numenews/agents/`
(`extract`, `pattern`, `forecast`, `summarize`), keep its prompt in `agents/prompts.py` and its draft
schema in `agents/schemas.py`, and test it with a `pydantic_ai` test model — never with a live call.

**No LangChain, LlamaIndex or LangGraph anywhere in the package, the lockfile or `.venv`.**
*Why:* `pydantic-ai` is the chosen orchestrator, and ragas' transitive LangChain tree is unresolvable
next to it. *Owner:* `AGENTS.md` (`Do not`), ADR 0013 (`docs/adr/0013-eval-isolation.md`).
*Instead:* import an existing `pydantic-ai` agent. LangChain may appear only inside
`tests/eval/` and only when it is installed in the isolated `.venv-eval` built by `make eval-env`; a
new dependency that pulls LangChain into `.venv` or `uv.lock` is a rejected change.

**No numerology logic outside `src/numenews/numerology/`.**
*Why:* reduction, master numbers, gematria, date resonance and the regex fallback are the project's
one pure, property-tested layer; a second definition of "reduce" in an agent, a CLI handler or a
Qdrant filter drifts from the first. *Owner:* `AGENTS.md`
(`Put numerology logic in agents or CLI handlers — it belongs in numerology/`). *Instead:* add the
function to `numerology/`, export it through `numerology/__init__.py`, and call it from the layer that
needs it; `vector/` may import `is_master` (ADR 0003), and nothing else may reach into the module's
internals.

**No dicts and no dataclasses across a module boundary.**
*Why:* a boundary value must be validated, frozen and documented once; a dict has no schema, and a
dataclass is not the project's vocabulary. *Owner:* `AGENTS.md`, `CONTRIBUTING.md` (Code style).
*Instead:* define the type once in `src/numenews/models/` and import it. A wire shape that differs
from the domain model (MCP arguments, camelCase JSON) gets its own Pydantic input schema in
`mcp/schemas.py` or `cli/schemas.py` and converts into the strict domain model at the edge.

**No `print()` — logs go through `structlog` to stderr.**
*Why:* stdout is a machine-readable stream, and a stray `print` corrupts the JSON a caller parses.
*Owner:* `CONTRIBUTING.md` (Code style: `No print() — use structlog (JSON to stderr)`) and
`AGENTS.md`. *Instead:* `get_logger(__name__).info(...)` from `numenews.logging`. The two
`sys.stdout.write` calls in `cli/output.py` are the sanctioned exception, and they exist so that
nothing else needs one.

**CLI stdout is one JSON document and nothing else.**
*Why:* every command must pipe into `jq`; progress, warnings and make output belong on stderr.
*Owner:* `AGENTS.md`, ADR 0005 (`docs/adr/0005-json-only-output.md`). *Instead:* answer with a
Pydantic model (or `ErrorReport`) and let `numenews.cli.output.print_json` be the only writer; the
Makefile's `run` and `mcp` targets are silenced with `@` for the same reason. Do not print a banner,
a table or a Rich panel to stdout.

**No API key or secret in a log line, an error message or a cache key.**
*Why:* logs are read by a model and shipped off the machine, and hishel keys the cache by URL, so a
credential in a query string is persisted. *Owner:* `AGENTS.md` (`No API keys required …`),
`CONTRIBUTING.md`. *Instead:* read secrets as `SecretStr` from `Settings` and send them in a header —
`X-Api-Key` (NewsAPI, GNews) or `Authorization: Bearer` (Currents) — and log the endpoint without its
query string. Mediastack is the documented exception: its only auth form is the `access_key` query
parameter, so the key does reach the hashed cache key; `docs/NEWS_SOURCES.md` and the adapter record
that, and it still never appears in a log line. Add no new exception silently.

**No CI/CD, no Kubernetes, no Terraform.**
*Why:* this is a local-first portfolio project; the local commands are the gate, and there is
deliberately no `.github/workflows`. *Owner:* `AGENTS.md` (`Do not`). *Instead:* make the change pass
`make lint && make test` (and `make test-eval` when the eval is touched) and record the command output
in your report. Do not add a workflow file, a chart or a `.tf` file to "help".

**No new dependency without the phase that needs it.**
*Why:* `pyproject.toml` documents which phase introduced each dependency, so the environment stays
honest about what the code actually imports and `uv.lock` stays resolvable. *Owner:* `AGENTS.md`
(`Stack`), `pyproject.toml`'s dependency comment, ADR 0013. *Instead:* add the dependency in the task
that first imports it, put it in `[project]` only if the package imports it (otherwise the `dev`
group), and update the phase comment in `pyproject.toml` in the same commit. If it conflicts with the
lock, isolate it the way ragas is isolated.

**Never weaken, skip or delete a test to make a check pass.**
*Why:* a green suite that no longer asserts anything is worse than a red one; the tests are the
evidence that a task's Definition of Done holds. *Owner:* `AGENTS.md` (a task is not done until its
DoD holds), [`EVAL_OF_AGENT.md`](EVAL_OF_AGENT.md). *Instead:* fix the code, or if the test encodes a
superseded decision, change it deliberately in its own task with the reason in the commit message and
an ADR when the decision was architectural. Deleting an assertion and reporting "tests pass" is the
single most common way an agent's work is rejected here.

**`numerology/` stays pure — no I/O, and no imports from the layers above it.**
*Why:* the layer's invariants are checked without infrastructure only while it imports nothing but
`models`. *Owner:* `AGENTS.md`, ADR 0002. *Enforced by:*
`tests/unit/test_numerology_api.py::test_numerology_does_not_import_the_layers_above_it` and
`::test_models_depend_on_nothing_beyond_the_package_root`, which run a fresh interpreter and inspect
`sys.modules`. *Instead:* pass data in as arguments and return a model. An ambient value (the current
year, the current day) is injectable — `extract_dates_regex(..., today=...)`,
`get_history(..., days=...)`, `Pipeline`'s `Clock` — so no test depends on the wall clock.

**No network calls and no `time.sleep()` in unit tests.**
*Why:* unit tests must pass with the network off and without a service; a sleep makes the suite slow
and flaky. *Owner:* `CONTRIBUTING.md` (`No time.sleep() — use freezegun or anyio`), `AGENTS.md`.
*Instead:* mock HTTP with `respx`, mock the model with `pydantic-ai`'s test models, use Qdrant
`:memory:` or the `FakeStore` doubles, and inject the clock. Mark anything that needs a real service
`@pytest.mark.integration` and let it skip when the service is absent.

**Do not commit `.env` or `.cache/`.**
*Why:* `.env` holds optional API keys and a personal endpoint; `.cache/` holds the hishel responses,
the downloaded `fastembed` weights and the hypothesis database. *Owner:* `.gitignore`,
`AGENTS.md` (`No API keys required for the default demo path`). *Instead:* commit `.env.example` when
a variable is added and leave the real `.env` local. `git status` is clean of both before a task is
reported done.

**Do not invent a roadmap task or a phase.**
*Why:* `ROADMAP.md` is the single source of truth for what is built and in what order; an implicit
backlog makes status unreadable and lets a task skip its Definition of Done. *Owner:* `AGENTS.md`
(`Roadmap`), the `Правила работы с роадмапом` section of `ROADMAP.md`. *Instead:* add the task to its
phase in `ROADMAP.md` (with a DoD, a size and the `🧪`/`📝` labels) in the same commit that builds it,
and do not start a phase before the previous one is closed.
