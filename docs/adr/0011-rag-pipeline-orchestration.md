# 11. The RAG pipeline layer, its window, and where a digest lives

## Status

Accepted (phase 5)

## Date

2026-09-21

## Context

Phase 5 is the first time the four layers below meet. Phases 1–4 built a pure numerology layer, five
news adapters, a Qdrant vector layer and three `pydantic-ai` agents, and kept them deliberately
ignorant of each other; nothing so far has known the order of the chain
`fetch → extract → compute → embed → find patterns → read memory → forecast → save`.

Roadmap 5.1 asks for a `Pipeline` class, but four decisions underneath it had no answer in the code
and could not be guessed from the roadmap's one-line tasks.

**Where does the layer live, and in which direction does it import?** `docs/ARCHITECTURE.md` lists
five layers and two rules, and the pipeline is in neither. It has to import all four below it, which
is fine as long as numerology stays pure and no leaf learns about the composition.

**How does an async pipeline call a synchronous layer?** The vector layer is synchronous on purpose
— `QdrantClient` is what the in-memory test engine supports, and the decision is recorded in
[ADR 0003](0003-local-embeddings.md) — while `fetch_news` and every agent method are coroutines.

**Where does the day's number come from?** `Forecast` carries `dominant_number` and `master_active`,
and nothing computes either. `reduce_date` exists, but the private design brief's own example —
2026-09-22 read under `11` — does not match it (`reduce_date` gives `5`, and 2026-09-21 gives `22`),
so the brief is either wrong or the number comes from somewhere else.

**Where does "the news outside the window" go?** Roadmap 5.5 requires summarising older news into a
"numerological digest" and storing it in Qdrant. The five collections of phase 3 hold news items,
number activations, patterns, forecasts and activations; none of them can hold a summary without
changing a payload schema that has already been documented and shipped.

Two smaller questions came with the same task: whether `Pipeline.forecast(day)` should re-derive the
day's patterns or read them back, and what a repeated run must cost when the project's rule is that
"state lives in Qdrant, not in process memory" and a command must be idempotent.

## Decision

We will add `numenews.pipeline` as the composition layer, with the decisions below.

- **One new layer, between "Reasoning" and "Interfaces".** `pipeline` may import `news`, `agents`,
  `vector`, `numerology`, `models`, `config` and `logging`; nothing below it may import `pipeline`.
  The two layer rules of `docs/ARCHITECTURE.md` are untouched, in particular that `numerology` stays
  pure and never imports `news`, `vector`, `agents` or `mcp`.
- **The pipeline is async; the vector layer stays synchronous.** Every call into `store` goes
  through `Pipeline.run_blocking`, which is `asyncio.to_thread` — the exact bridge ADR 0003 predicted
  for phase 5. It is the only place in the layer that touches a thread.
- **The day's number is derived from the day's news, not from the date.** `numerology.dominant_number`
  returns the most frequent reduced value of the window's items, with ties going to the larger value,
  and `reduce_date(day)` is the fallback for a day with no news, because a reading always has a number
  to rest on. The rule lives in `numerology/` (AGENTS.md keeps numerology out of the pipeline) and
  answers roadmap 5.3's "resonance" reading as well: a day whose articles all read as 11 is a
  resonance day, and its master number is active.
- **A sixth collection `digests` holds the summaries.** 768d COSINE, like `patterns` and
  `forecasts`, with `period_start` and `period_end` indexed as `DATETIME`; the point id is `uuid5`
  over the period, so re-summarising a range replaces its point. `docs/QDRANT_COLLECTIONS.md`,
  `docs/ARCHITECTURE.md` and `tests/integration/test_vector_docker.py` (which asserts every
  collection's payload indexes against the real server) are updated with it.
- **`summary_limit` bounds the prompt, not the period.** The model is shown at most 50 older items;
  the stored digest still describes every one of them, because labelling a memory with a period it
  only partly read would make it claim more than it knows.
- **`forecast(day, rerun_analysis=...)` re-derives the day's patterns by default.** Reading them back
  by `discovered_at` would filter on the moment a connection was written rather than on the day it
  belongs to; the deterministic `PatternId` of phase 4.3 makes the re-save an overwrite of the same
  point. A caller that has just run `analyze` passes `rerun_analysis=False`.
- **Every step is idempotent, and a repeated run is free.** `ingest` skips an item whose point
  already exists *before* extracting from it (no model call, no write); `forecast` answers from
  `get_forecast` before it does anything (no model call); `analyze` of an empty or unknown id list
  never reaches the model.
- **A model failure is retried once and then surfaced.** `steps.retrying` retries `AgentError` only —
  a `VectorStoreError` means the database is gone and an `PipelineError` is a configuration — and
  ends in `PipelineRetryError(step, ...)`. Nothing is stored for a failed forecast: an empty list
  must stay distinguishable from "the model never answered" (phase 4.3).
- **A digest is stored and readable, but not injected into a prompt in phase 5.** No phase-5 task
  changes a prompt, and `docs/PROMPTS.md` plus its snapshot tests change only when one does.

## Consequences

Easier: the CLI of phase 7 and the MCP tools of phase 6 become thin — they call `Pipeline.ingest`,
`Pipeline.analyze`, `Pipeline.forecast` and `Pipeline.summarize` and serialize what comes back — and
every one of those calls is safe to repeat, which is what a one-shot interface over shared Qdrant
state needs. Each step reports its own counters and duration, so a slow run is diagnosable from the
`PipelineRun` it returned and from one `structlog` line per step.

Harder and worth remembering:

- The pipeline is the fifth layer in a document that listed four, and it is the only one allowed to
  import everything. A symptom in any layer can now be caused by the composition, so the steps keep
  their logic in small functions (`steps.py`, `context.py`) rather than in the class.
- `asyncio.to_thread` per vector call is cheap but not free, and it is a decision to revisit only
  together with ADR 0003.
- A news item's `numerology_value` is now load-bearing for a forecast: a text without letters yields
  `None` and votes for nothing, so the dominant number rests on the items that could be read. The
  fallback to `reduce_date` keeps that from producing an empty reading.
- `digests` is a sixth collection to keep documented, provisioned and asserted; the roadmap's target
  state says "5 collections" and `docs/ARCHITECTURE.md`'s state table now says six. The public
  roadmap is updated in the same phase, with the reason recorded there.
- The digest is written but never read by an agent yet, so its value is not visible in a forecast
  today. That is deliberate — phase 8.3 owns the 30-day history injection — and it means the
  collection's usefulness is proven by its tests rather than by a demo path.

## References

- `ROADMAP.md` phases 5.1–5.7 and 8.3
- [ADR 0002](0002-numerology-scope.md) — numerology is pure logic; the pipeline never computes a
  number inline
- [ADR 0003](0003-local-embeddings.md) — the synchronous vector layer and the `asyncio.to_thread`
  bridge it predicted
- [ADR 0004](0004-pydantic-ai-choice.md) — the draft boundary and the deterministic `PatternId`
- [`docs/RAG_PIPELINE.md`](../RAG_PIPELINE.md), [`docs/CONTEXT_MANAGEMENT.md`](../CONTEXT_MANAGEMENT.md),
  [`docs/QDRANT_COLLECTIONS.md`](../QDRANT_COLLECTIONS.md)
