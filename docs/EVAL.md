# RAG evaluation (phase 9)

> `ROADMAP.md` is the authoritative status; this document records what the eval actually does, how to
> run it and how to read its report. The decision behind its isolation is in
> [ADR 0013](adr/0013-eval-isolation.md).

The evaluation answers one question: *does the production retrieval path find the right news, and is
the prose written from it grounded?* It is measured with [`ragas`](https://docs.ragas.io/) over a
committed corpus, and it is the only suite in this repository that makes real LLM calls.

## Two halves

| Test | Needs | What it proves |
|---|---|---|
| `tests/eval/test_retrieval.py` | no LLM, no key | the fixtures are consistent and the production hybrid search retrieves a relevant item for at least 80 % of the questions |
| `tests/eval/test_rag.py` | an LLM endpoint | the four ragas metrics over the retrieved contexts, gated at the phase-9 floors |

Both are marked `eval` and run only with `--run-eval`, which `make test-eval` passes.

## The isolated environment

`ragas` cannot share an environment with `pydantic-ai`: every `instructor` release pins
`jiter<0.15`, while `openai>=3.8` — required by `pydantic-ai-slim[openai]` — needs `jiter>=0.16`.
`uv lock` cannot resolve the two together, so ragas is deliberately **not** in `pyproject.toml`'s
dependency groups and **not** in `uv.lock`. It lives in `.venv-eval` (gitignored), built on demand:

```bash
make eval-env   # uv sync --no-install-package pydantic-ai-slim, then ragas from requirements-eval.txt
make test-eval  # builds .venv-eval if it is missing, then runs pytest in it
```

`make test-eval` invokes `.venv-eval/bin/python` directly rather than `uv run`, which would sync the
environment back to the lock and prune ragas from it. `make clean` removes `.venv-eval` as well,
after which the next `make test-eval` rebuilds it.

Inside `.venv-eval`:

- the locked runtime environment **minus** `pydantic-ai-slim`;
- everything in the `dev` group, so pytest and pytest-asyncio are there;
- `tests/eval/requirements-eval.txt` — `ragas==0.4.3` plus `langchain-community<0.4`, the pin that
  works around an upstream ragas bug (`ragas/llms/base.py` imports
  `langchain_community.chat_models.vertexai`, which langchain-community removed in 0.4.0).

Because the environment has no `pydantic-ai`, the eval's answer is written by ragas' own
`llm_factory` (instructor, JSON mode) instead of a `pydantic-ai` agent. The prompt is eval
scaffolding and lives in `tests/eval/judge.py`; the product's prompts stay in
`src/numenews/agents/prompts.py` and [`PROMPTS.md`](PROMPTS.md).

## Configuration

The metric half skips unless an endpoint is configured. It reads the same settings as the rest of
the project ([`.env.example`](../.env.example)):

| Variable | Meaning |
|---|---|
| `OPENAI_BASE_URL` | any OpenAI-compatible endpoint (`https://api.deepseek.com/v1`, OpenRouter, Ollama, …); blank means the OpenAI default |
| `OPENAI_API_KEY` | the key for that endpoint; a placeholder is sent when the endpoint ignores it |
| `LLM_MODEL` | the judge **and** answer model at that endpoint (default `gpt-4o-mini`) |

Example against a compatible endpoint:

```bash
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=... LLM_MODEL=deepseek-flash make test-eval
```

Without an endpoint, `make test-eval` runs the retrieval tests, skips the metrics with an
actionable message and leaves `docs/eval_report.md` untouched. `RAGAS_DO_NOT_TRACK=true` is set for
every run: the eval behaves like the rest of the project and calls no service it does not need.

## The fixtures

`tests/eval/fixtures/news.jsonl` holds 50 English articles, one JSON object per line:

```json
{"slug": "...", "title": "...", "text": "...", "source": "...",
 "date": "2026-03-02", "url": "https://example.test/...", "numbers": [11, 5]}
```

`numbers` is declared, not extracted: the eval must not depend on how good the extraction agent of
that moment is. `tests/eval/harness.py` validates every line — unique slug and URL, non-empty
numbers, every declared number written in the text, a non-empty gematria reading — and turns each
item into the production `NewsItem`: the id is `uuid5(NAMESPACE_URL, url)` (`news_id`) and
`numerology_value` comes from `compute_numerology`, exactly as ingest would compute them.

The corpus is **English** because both local embedders are (`BAAI/bge-base-en-v1.5`,
`BAAI/bge-small-en-v1.5`): a Russian corpus would measure the models' language limit rather than
retrieval quality. `docs/EMBEDDINGS.md` records the model choice.

`tests/eval/fixtures/questions.jsonl` holds 20 questions, one per line:

```json
{"id": "q01", "question": "...", "reference": "One or two grounded sentences.",
 "relevant": ["slug-a", "slug-b"]}
```

`reference` is the ground truth ragas compares against; `relevant` names the articles the question
is answerable from, which is what the deterministic `hit@5` check counts. To add a question, add the
line, point `relevant` at existing slugs, and keep the totals in `test_retrieval.py`
(`CORPUS_SIZE`, `QUESTION_COUNT`) in step. To add an article, add the line and make sure at least one
question's `relevant` uses it, or the retrieval floor stops meaning anything.

## The metrics

Each question retrieves its top-5 items through `hybrid_search_news`, the answerer writes one answer
from them, and four ragas metrics score the pair. `tests/eval/judge.py` holds the wiring:
`Faithfulness`, `ContextPrecisionWithReference`, `ContextRecall` and `AnswerRelevancy` from
`ragas.metrics.collections`, judged by `llm_factory` and — for answer relevancy — embedded by the
project's own 384d `fastembed` model through a `BaseRagasEmbedding` adapter, so no embedding API is
called (ADR 0003).

| Metric | Question it answers | Floor |
|---|---|---|
| `faithfulness` | is every claim in the answer supported by the retrieved contexts? | ≥ 0.7 |
| `context_precision` | do the useful contexts appear before the useless ones? | ≥ 0.6 |
| `context_recall` | do the contexts cover the reference answer? | reported |
| `answer_relevancy` | does the answer actually address the question? | reported |

A question whose answer is empty fails immediately rather than being scored, and a question attaches
the model's answer, the retrieved contexts and all four scores to the run.

## The report

Every metric run rewrites [`docs/eval_report.md`](eval_report.md) **before** it asserts anything, so
a below-floor score is still readable in the report that produced it. The report records the date,
the judge model and endpoint, the corpus and question counts, the per-metric score against its floor,
the retrieval hit rate, and a per-question table.

Scores come from a language model and move a few points between runs, endpoints and even reasoning
settings. A single question can drop to 0 when the judge's statement check misreads an answer the
contexts plainly support — seen on a question whose one-sentence answer restated a retrieved
sentence almost verbatim. That is why the suite gates the **mean** and keeps the per-question table
in the report: a lone zero is a judge artefact, a column of zeros is a retrieval problem. The floors
are floors, not targets: if the mean drops below one, the fix is the corpus, the retrieval or the
answer prompt — never a lowered threshold. The committed report is the record of the run that
closed the phase.

## Runtime and cost

The run makes roughly a dozen judge calls per question; with four questions in flight it takes a few
minutes and costs cents on a small model. Both numbers depend on the endpoint, which is why the
report names the model that produced it.

## Files

| Path | Role |
|---|---|
| `tests/eval/harness.py` | fixtures, the in-memory store, retrieval, the context strings |
| `tests/eval/judge.py` | the judge, the local ragas embeddings, the eval-only answer prompt |
| `tests/eval/test_retrieval.py` | deterministic fixtures and `hit@5` |
| `tests/eval/test_rag.py` | the four metrics, the floors and the report |
| `tests/eval/conftest.py` | eval fixtures and the ragas-absent collection guard |
| `tests/eval/fixtures/` | `news.jsonl`, `questions.jsonl` |
| `tests/eval/requirements-eval.txt` | the two eval-only pins |
| `docs/eval_report.md` | the latest real run |
