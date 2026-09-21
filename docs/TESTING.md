# Testing

> `ROADMAP.md` is the authoritative status; this document records how the suite is organised, what
> each level is allowed to assume, and how the coverage floors are enforced. The eval's isolation is
> in [ADR 0013](adr/0013-eval-isolation.md).

The suite answers one question per level: *is the pure logic right* (unit), *do the adapters hold up
against a real engine* (integration), *does the production path retrieve the right news and is the
prose grounded* (eval). There is no live-API level: the five feeds are mocked with `respx`, the LLM
is a pydantic-ai test model, and the only two things that are genuinely real in the default suite are
Qdrant's in-memory engine and the `fastembed` weights.

## The four levels

| Level | Path | Marker | What it may assume |
|---|---|---|---|
| Unit | `tests/unit/` | — | no network, no Qdrant, no model load, no `sleep` |
| Integration | `tests/integration/` | `@pytest.mark.integration` | in-memory Qdrant, `respx`, test models, one sqlite cache in a temp dir |
| Docker-only | `tests/integration/test_vector_docker.py` | `@pytest.mark.integration` | the container `make dev` starts; the module **skips** when it is unreachable |
| Eval | `tests/eval/` | `@pytest.mark.eval` | the committed corpus, real `fastembed` models, and — for the ragas half — a live LLM endpoint |

```bash
make test           # unit + integration, with coverage and the per-layer floor checks
make test-unit      # tests/unit only
make test-integration  # tests/integration -m integration
make coverage       # the same run plus an HTML report in docs/coverage.html (gitignored)
make coverage-check # re-check the floors against the existing .coverage
make test-eval      # tests/eval --run-eval, in .venv-eval (needs an LLM endpoint)
```

## What is real, and what is a double

| Collaborator | In the suite | Why |
|---|---|---|
| Qdrant | `qdrant_in_memory` / `VectorStore.in_memory` (`QdrantClient(":memory:")`) | a real engine with real filter and search semantics, without Docker |
| Qdrant payload indexes | `docker_store` in `test_vector_docker.py` | the in-memory engine warns that indexes have no effect, so only the Docker store can assert them |
| Embeddings | `FakeEmbedder` (`tests/integration/fakes.py`) | deterministic geometry, no 286 MB download per run |
| Real embeddings | `small_embedder` / `base_embedder` fixtures and `tests/integration/test_embeddings_fastembed.py` | proves laziness, determinism and the real dimension |
| News HTTP | `respx` routes over recorded fixtures (`tests/fixtures/news/`) | exercises the real cache, retry and error mapping |
| The cache | a real `hishel` sqlite file in the test's temporary directory | the cache is the code under test, so it is not faked |
| LLM | `TestModel` / `FunctionModel` from `pydantic-ai` | agent wiring and prompt shape, no network |
| A stray LLM request | `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py` | an accidental real call fails loudly instead of silently passing |
| Retry backoff | `instant_retries` monkeypatches `news.http._wait` | the retry *policy* is still exercised; the suite loses no seconds |

## Fixtures

`tests/conftest.py` holds the two hermetic fixtures every level shares:

- `settings` — a `Settings` built with the process environment and `.env` cleared, so a result does
  not depend on the machine;
- `tmp_cache_dir` — a temporary `Settings.cache_dir`, so `hishel` and `fastembed` never touch the
  developer's `.cache/`.

`tests/integration/conftest.py` adds the engine- and transport-level fixtures above, and
`tests/eval/conftest.py` deliberately does the opposite of hermetic: `eval_settings` reads the
developer's real settings, because the eval is the one suite that must reach an LLM endpoint.

## Markers and gating

Two markers are registered in `pyproject.toml`:

- `integration` — needs a reachable service (in practice, the Docker-only module);
- `eval` — the ragas metrics, skipped unless `--run-eval` is passed.

`--run-eval` is registered in `tests/conftest.py`, and `pytest_ignore_collect` in
`tests/eval/conftest.py` keeps `test_rag.py` out of collection entirely when `ragas` is not
installed. Both exist for the same reason: a bare `uv run pytest` in `.venv` must stay green even
though the eval's dependencies and endpoint are absent.

## Coverage

The floors are per layer, and they are part of `make test`:

| Layer | Floor | Measured at release |
|---|---|---|
| `numerology/` | 95 % | 100 % |
| `pipeline/` + `agents/` | 80 % | 99 % / 100 % |
| `vector/` + `news/` | 70 % | 97 % / 100 % |

coverage.py has no per-path threshold, so `make coverage-check` passes `--fail-under` once per
include group; `make test` runs it after pytest. The dated snapshot of the numbers and the command
that produced them is [`coverage_report.md`](coverage_report.md).

Two things are deliberately outside the floors: the `__main__` modules (`cli/__main__.py`,
`mcp/__main__.py`), whose only statement delegates to a `main`, and the branches that need a real
Docker Qdrant or a live endpoint.

## Conventions

- **A test asserts behaviour, not implementation.** A test that has to be weakened to pass is a bug
  report, not a fix — see [`agentic/EVAL_OF_AGENT.md`](agentic/EVAL_OF_AGENT.md).
- **No `time.sleep` and no real waiting.** Retry timing is monkeypatched (`instant_retries`) and
  clocks are injected (`today=`, `SystemClock`).
- **Time and ids are inputs.** `extract_dates_regex`, `get_history` and the pipeline accept a
  `today`; point ids are deterministic `uuid5` values, so a test never depends on a wall clock or a
  random id.
- **Hermetic unless the point is reality.** Use `settings`/`tmp_cache_dir`; touch the developer's
  environment only in the Docker and eval modules, and skip rather than fail when the service is
  absent.
- **The pure layer has its own guarantees.** `tests/unit/test_numerology_api.py` asserts that
  `numerology` imports none of the higher layers and that `models` imports nothing but the package
  root; property tests assert the invariants (the reduced set, idempotence, order-independence,
  case-insensitivity).
- **One test belongs to one level.** If it needs no I/O it is a unit test; if it needs an engine or a
  transport it is an integration test; if it needs an LLM it is an eval test.

## Adding a test

| Change | Where it goes |
|---|---|
| numerology rule or invariant | `tests/unit/test_<area>.py`, with a `hypothesis` property when one exists |
| agent prompt or draft-schema mapping | `tests/unit/test_agents_*.py`, against `FunctionModel` |
| collection, payload, filter, search | `tests/integration/test_vector_*.py` over the in-memory store; payload-index assertions in `test_vector_docker.py` |
| feed adapter | `tests/integration/test_news_*.py` with a recorded fixture answered by `respx` |
| pipeline step | `tests/integration/test_pipeline_*.py`, with `FakeEmbedder` and test models |
| MCP tool or CLI command | `tests/unit/test_mcp_*.py` / `tests/unit/test_cli_*.py` for shape, `tests/integration/` for the stdio and end-to-end paths |

`make lint` (ruff + `mypy --strict`) applies to tests as well: the test files are typed and checked
like the package.

## See also

- [`EVAL.md`](EVAL.md) — the ragas half in detail
- [`coverage_report.md`](coverage_report.md) — the measured floors at release
- [`STACK.md`](STACK.md) — why the test tools are pytest, hypothesis, respx and coverage.py
- [`agentic/EVAL_OF_AGENT.md`](agentic/EVAL_OF_AGENT.md) — how agent-generated tests are reviewed
