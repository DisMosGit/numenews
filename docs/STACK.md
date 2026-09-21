# Stack

> Why each tool is here, and what it costs. [`ROADMAP.md`](../ROADMAP.md) is the authoritative
> status; the decisions with lasting architectural weight are recorded in [`docs/adr/`](adr/) and
> linked from the rows below.

The stack is deliberately small: one package manager, one type system, one vector store, one LLM
orchestrator, and local models only. Every dependency is either used on the default demo path or is
a test tool; nothing is installed "for later".

## Runtime

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| **Python 3.14** | the whole package | modern typing (`type` aliases, `Self`), free-threaded-ready, and the version the lockfile is resolved for | newer than most deployment images |
| **`uv` + `uv_build`** | environment, lockfile, build backend | one tool for sync/lock/build, fast, and the lock is checked in so every checkout resolves identically | a tool most contributors have to install |
| **`pydantic` v2** | every boundary: settings, models, agent output, MCP schemas | validation at the edge plus structured output for the agents; frozen and strict models make a wrong shape fail where it is produced | models must be kept small and explicit |
| **`pydantic-settings`** | `Settings` from `.env` and the environment | one validated object instead of scattered `os.environ` reads; `.env.example` documents the surface | one more dependency under every layer |
| **`structlog`** | logs on stderr, JSON in prod | the CLI's stdout must stay machine-readable, and structured fields are what make a pipeline run greppable | JSON logs are less pleasant to read than `print` |

## Domain

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| pure Python `numerology/` | reduction, master numbers, gematria, date resonance | the rules are small and testable; a library for numerology would hide the rules that are the product | the algorithms are ours to defend (ADR 0002) |
| **`regex` + stdlib parsing** | number/date extraction fallback | no dependency, and it is the degradation path when the LLM is unavailable | regex fallback is intentionally shallow |

## Data

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| **Qdrant** (`qdrant-client`) | six collections, payload indexes, hybrid search | the Query API with `Prefetch` and RRF is exactly the retrieval shape this project needs, and `QdrantClient(":memory:")` makes the whole vector layer testable without Docker | a container on the default path; see [ADR 0003](adr/0003-local-embeddings.md) and [ADR 0007](adr/0007-qdrant-hybrid-search.md) |
| **`fastembed`** | 384d and 768d local embeddings | local-only by rule (`AGENTS.md`), ONNX instead of torch, and the `bge` family is enough for English news text | ~286 MB of weights on first use; English-only ([ADR 0008](adr/0008-fastembed-vs-openai.md), [`EMBEDDINGS.md`](EMBEDDINGS.md)) |
| **`httpx`** | one async client for five feeds | async, typed, and the transport `respx` mocks in tests | — |
| **`hishel`** | RFC 9111-shaped cache on that client | the only widely used `httpx` cache, and its filter mode plus `default_ttl` is what makes a fifteen-minute TTL possible without freshness headers | a sqlite file per checkout ([ADR 0009](adr/0009-hishel-caching.md)) |
| **`tenacity`** | retries with backoff and `Retry-After` | declarative retry policy that can ask the exception whether another attempt is worth it | retry policy has to be reasoned about per error class |
| **`respx`** | mock transport for the news tests | intercepts `httpx` at the transport layer, so the real cache, retry and error mapping are exercised | — |

## Reasoning

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| **`pydantic-ai-slim[openai]`** | the four agents (extract, pattern, forecast, summarize) | structured output as a first-class concept, model-agnostic through any OpenAI-compatible endpoint, and it fits the Pydantic-everywhere posture | the `slim[openai]` extra rather than the meta-package keeps Anthropic/Google/Logfire out ([ADR 0004](adr/0004-pydantic-ai-choice.md)) |
| **OpenAI-compatible endpoint** | the LLM itself | one client shape covers OpenAI, OpenRouter, Ollama, vLLM and LM Studio, so the demo runs without a key against a local server | requires an endpoint for agent-backed commands; `gpt-4o-mini` is the default name |
| **`mcp` (Python SDK v2)** | the nine tools over stdio | the official SDK, and v2's `MCPServer` is the maintained server class (`FastMCP` was the v1 name) | a young API surface ([ADR 0010](adr/0010-use-mcp-server.md)) |

## Interface

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| **Typer** | the six CLI commands | Python-function-to-CLI with type hints, and it leaves stdout alone for JSON ([ADR 0005](adr/0005-json-only-output.md)) | brings `rich`, `shellingham` and `annotated-doc`; `rich` is used only for `--help` |
| **`rich`** | `--help` rendering | a Typer dependency, not imported by the package | it is on the dependency list without being imported directly |
| JSON on stdout | the CLI's only output format | pipes into `jq`, no rendering logic, no terminal assumptions | progress has to go to stderr ([ADR 0006](adr/0006-one-shot-vs-repl.md)) |

## Quality

| Tool | What it does here | Why this one | Cost |
|---|---|---|---|
| **ruff** | lint and format | one fast tool for both, configured in `pyproject.toml` | a curated rule set rather than "all" ([`AGENTS.md`](../AGENTS.md)) |
| **mypy --strict** + pydantic plugin | static checking of every boundary | strict mode plus the plugin understands generated `__init__` signatures; `warn_unreachable` catches dead branches | slow on the whole project, which is why it runs in pre-commit and `make lint` |
| **pytest + pytest-asyncio** | the suite | `asyncio_mode = "auto"` keeps async tests plain functions | — |
| **hypothesis** | property tests of the pure numerology layer | the invariants (reduction always lands on 1–9 or 11/22/33, order-independence, idempotence) hold for arbitrary inputs | slower than example-based tests; used only where invariants exist |
| **pytest-cov / coverage.py** | the per-layer coverage floors | branch coverage is what the floors are stated in | thresholds have to be passed per include, which is why the Makefile owns them ([`TESTING.md`](TESTING.md)) |
| **pre-commit** | the same checks on every commit | the gate runs locally, since there is no CI by design | `mypy` on the whole project per commit |
| **Docker Compose** | Qdrant for development | one command (`make dev`) with a healthcheck and a named volume | Docker is required for the full suite and the demo |
| **ragas** (`.venv-eval` only) | the RAG quality metrics | measured faithfulness and retrieval quality instead of a vibe | cannot share an environment with `pydantic-ai`, so it lives in `.venv-eval` ([ADR 0013](adr/0013-eval-isolation.md)) |

## Deliberately absent

- **No CI/CD, Kubernetes or Terraform** — out of scope by `AGENTS.md`; `make lint && make test` and
  pre-commit are the gate, and the coverage badge is a static number kept honest by
  [`coverage_report.md`](coverage_report.md).
- **No LangChain, LlamaIndex or LangGraph** in the runtime — `pydantic-ai` is the orchestrator. The
  eval's LangChain tree is transitive inside `.venv-eval` and never enters `.venv` or `uv.lock`.
- **No external embedding API or cloud vector database** — a design constraint, not a preference.
- **No web framework or database ORM** — the interfaces are stdio MCP and a one-shot CLI, and the
  state is Qdrant.
- **No task queue or scheduler** — "one-shot and idempotent" is the operating model
  ([ADR 0006](adr/0006-one-shot-vs-repl.md)).

## See also

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how the layers above fit together
- [`TESTING.md`](TESTING.md) — how the quality tools are used
- [`EVAL.md`](EVAL.md) — the ragas half of the stack
- [`AGENTS.md`](../AGENTS.md) — the rules that constrain the choices
