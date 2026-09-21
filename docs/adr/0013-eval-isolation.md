# 13. Isolate the ragas evaluation in its own environment

## Status

Accepted (phase 9)

## Date

2026-09-21

## Context

Phase 9 measures RAG quality with `ragas`. Doing that needs an LLM judge and an embedding model, and
neither may enter the runtime environment:

- `ragas` declares `langchain`, `langchain-core`, `langchain-community`, `langchain-openai`,
  `langgraph` and `instructor` as hard dependencies, and `AGENTS.md` rules LangChain and LangGraph
  out — `pydantic-ai` is the orchestrator of this project.
- A dependency group in `pyproject.toml` does not solve it. `pydantic-ai-slim[openai]>=2.46` needs
  `openai>=3.8.0`, which needs `jiter>=0.16`; every `instructor` release (a ragas dependency) pins
  `jiter<0.15` and, below 1.15, `openai<3.0`. The two sets cannot be satisfied at once, so
  `uv lock` fails with the group present and `uv pip install -e . ragas` fails outright. The lock is
  also universal over `requires-python = ">=3.14"`, and the conflict surfaces as an unsatisfiable
  split for 3.15 and later even before the 3.14 resolution is considered.
- ragas 0.4.3 is additionally broken against the newest LangChain: `ragas/llms/base.py` imports
  `langchain_community.chat_models.vertexai`, a module `langchain-community` removed in 0.4.0.
- The project's own precedent (phases 2, 4, 5) is that no live LLM run exists in the repository: the
  suite closes on test doubles and `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`. An eval that
  never runs is not an eval, so phase 9 has to make the real run possible without weakening the
  runtime environment.

## Decision

We will keep `ragas` out of `uv.lock` and out of `.venv`, and run the evaluation in a separate,
gitignored `.venv-eval` built by `make eval-env`:

1. `UV_PROJECT_ENVIRONMENT=.venv-eval uv sync --no-install-package pydantic-ai-slim` installs the
   locked runtime environment minus `pydantic-ai-slim`, which is the one package that makes ragas
   unresolvable.
2. `uv pip install --python .venv-eval/bin/python -r tests/eval/requirements-eval.txt` adds ragas
   (pinned) and `langchain-community<0.4` (the pin that works around the upstream import).
3. `make test-eval` runs `.venv-eval/bin/python -m pytest tests/eval --run-eval` directly. It never
   uses `uv run`, which would sync the environment back to the lock and prune ragas.
4. The eval corpus is English, because both local embedders are English-only
   (`BAAI/bge-base-en-v1.5`, `BAAI/bge-small-en-v1.5`): a Russian corpus would measure the known
   language limit of the models rather than retrieval quality.
5. The answer that ragas scores is written by the configured OpenAI-compatible endpoint through
   ragas' own `llm_factory`, not by a `pydantic-ai` agent: `pydantic-ai` is absent from `.venv-eval`
   by construction. The prompt lives in `tests/eval/judge.py` and is explicitly eval scaffolding —
   numenews has no question-answering agent, and adding a fifth product agent to serve a test would
   be scope creep. Product prompts stay in `src/numenews/agents/prompts.py` and `docs/PROMPTS.md`.
6. The metrics are used through `ragas.metrics.collections` (the maintained API in ragas 0.4:
   `Faithfulness`, `ContextPrecisionWithReference`, `ContextRecall`, `AnswerRelevancy` with
   `ascore`), not through the deprecated `ragas.evaluate`. The roadmap named `ragas.evaluate` before
   ragas moved on; this ADR records the deviation.
7. `answer_relevancy` embeds with the project's own 384d `fastembed` model through a small
   `BaseRagasEmbedding` adapter, so no embedding API is called (ADR 0003).

## Consequences

- The runtime environment stays LangChain-free: `.venv` never contains `ragas`, `langchain*` or
  `langgraph`, and `uv sync` / `uv lock` behave exactly as before. Phase 9 adds no dependency to
  `[project]` and no group to `[dependency-groups]`.
- The eval environment is not covered by `uv.lock`. Its two top-level pins live in
  `tests/eval/requirements-eval.txt`, and a transitive change in ragas' stack can break it without a
  lockfile diff — the price of keeping the eval out of the runtime resolution. `make eval-env`
  rebuilds it from scratch.
- `make test-eval` needs an LLM endpoint (`OPENAI_API_KEY` or `OPENAI_BASE_URL`, `LLM_MODEL`). When
  none is configured the ragas test skips with an actionable message while the deterministic
  retrieval test still runs; `make test-eval` then reports a skip rather than a fake score.
- `make clean` also removes `.venv-eval`; rebuilding it is one command.
- `tests/conftest.py` guards its `pydantic_ai` import, and `pyproject.toml` tells mypy to ignore
  missing `ragas` imports: `make lint` and `make test` run in `.venv`, where ragas is not installed.
- `pytest_ignore_collect` in `tests/eval/conftest.py` keeps `test_rag.py` out of collection in the
  main environment, so a bare `uv run pytest` stays green.
- Scores are judge-dependent. The floors (`faithfulness >= 0.7`, `context_precision >= 0.6`) are
  kept below the reported values rather than tuned to one run, and `docs/eval_report.md` records the
  model and the date of the run that produced them.

## References

- [`ROADMAP.md`](../../ROADMAP.md) phase 9
- [`docs/EVAL.md`](../EVAL.md) and [`docs/eval_report.md`](../eval_report.md)
- [`docs/adr/0003-local-embeddings.md`](0003-local-embeddings.md) — no embedding API
- [`docs/adr/0004-pydantic-ai-choice.md`](0004-pydantic-ai-choice.md) — `pydantic-ai` as the orchestrator
- [ragas](https://docs.ragas.io/) — `llm_factory`, `metrics.collections`
