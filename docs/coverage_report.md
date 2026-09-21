# Coverage report

> ROADMAP 10.4. The dated snapshot of the suite's coverage and the floors it is compared against.
> This is a static record, not something a pipeline regenerates: the project has no CI/CD by design
> (`AGENTS.md`), so the command below is the one to re-run, and the README badge is kept in sync with
> this file manually. [`TESTING.md`](TESTING.md) describes the levels behind the numbers.

**Run of 2026-09-21**, on the released tree (`v0.1.0`):

```bash
make test           # 677 passed, 8 skipped in ~40 s; writes .coverage, then runs `make coverage-check`
make coverage-check # the floors, one `coverage report` per layer group
make coverage       # the same run with an HTML report in docs/coverage.html (gitignored)
```

## The floors

| Layer | Floor | Required by | Measured | Command |
|---|---|---|---|---|
| `numerology/` | **95 %** | the pure layer is the product | **100 %** | `coverage report --include="src/numenews/numerology/*" --fail-under=95 --format=total` |
| `pipeline/` + `agents/` | **80 %** | application logic | **99 %** / **100 %** | `coverage report --include="src/numenews/agents/*" --include="src/numenews/pipeline/*" --fail-under=80 --format=total` |
| `vector/` + `news/` | **70 %** | infrastructure | **97 %** / **100 %** | `coverage report --include="src/numenews/vector/*" --include="src/numenews/news/*" --fail-under=70 --format=total` |

`make test` runs the third column's checks after pytest, and a regression below a floor fails the
gate. coverage.py has no per-path threshold, which is why `[tool.coverage.report] fail_under` stays
`0` and the Makefile passes `--fail-under` once per group.

## Every package

| Package | Statements | Missed | Branch | Partial | Coverage |
|---|---|---|---|---|---|
| `numerology/` | 145 | 0 | 32 | 0 | 100 % |
| `models/` | 148 | 0 | 8 | 0 | 100 % |
| `news/` | 501 | 0 | 84 | 0 | 100 % |
| `embeddings/` | 44 | 0 | 4 | 0 | 100 % |
| `agents/` | 231 | 0 | 22 | 0 | 100 % |
| `pipeline/` | 319 | 2 | 26 | 1 | 99 % |
| `mcp/` | 228 | 4 | 30 | 0 | 98 % |
| `cli/` | 155 | 2 | 8 | 0 | 99 % |
| `vector/` | 443 | 6 | 72 | 7 | 97 % |
| **Total** | **2275** | **14** | **290** | **8** | **99 %** |

## What is left uncovered, on purpose

The 14 missed statements are:

- **6 module entry points** — `src/numenews/cli/__main__.py` (2) and `src/numenews/mcp/__main__.py`
  (4). Their only statement delegates to a `main`; the behaviour behind it is covered by
  `tests/unit/test_smoke.py` and `tests/integration/test_mcp_stdio.py`.
- **`pipeline/steps.py:102-103`** — the `pipeline.step.failed` warning branch. A step that raises is
  covered by the retry tests; this line only runs when the failure reaches the timer's own log call.
- **`vector/client.py:57` and `vector/collections.py:131-132`** — the success path of
  `VectorStore.from_settings` and the `ensure_collections()` loop. The suite builds stores with
  `in_memory()` and creates collections through the write paths; the `.from_settings()` path needs
  the real server in `tests/integration/test_vector_docker.py`, which skips when `make dev` is not
  running (the 8 skips above).
- **`vector/digests.py:94` and `vector/forecasts.py:91`** — the `VectorStoreError` raised when a
  stored point has no payload. Reaching it needs a deliberately corrupted point, which the suite does
  not write.
- The 8 partial branches (`vector/history.py`, `vector/news.py`, `vector/patterns.py`,
  `vector/payloads.py`, `pipeline/steps.py`) are the second half of loop and page-through paths whose
  first half the tests execute.

`pyproject.toml` disables two known warnings rather than excluding code, so the only measurement gaps
are the ones listed here.

## See also

- [`TESTING.md`](TESTING.md) — the four levels, the doubles and the fixtures
- [`EVAL.md`](EVAL.md) and [`eval_report.md`](eval_report.md) — the quality measurement, dated the
  same way
- [`adr/0013-eval-isolation.md`](adr/0013-eval-isolation.md) — why the eval's dependencies are not in
  this measurement's environment
