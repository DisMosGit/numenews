# 12. Long-term memory: the exact log, its two windows, and the per-day frequency

## Status

Accepted (phase 8)

## Date

2026-09-21

## Context

Phase 8 is the memory phase, but most of the memory was pulled forward by earlier phases:
`number_history` was created in 3.7 with its `(number, date)` indexes, `Pipeline.ingest` has written
an activation per `(article, number)` pair since 5.2, the forecast step has read activations since
5.4, the MCP `get_history` tool shipped in 6.10 and the CLI `history` command in 7.5. Closing the
phase therefore meant answering the questions those one-line tasks left open.

**Why keep two collections of activations at all?** `numbers` (384d, `bge-small-en-v1.5`) and
`number_history` (payload only) store the same five fields. Phase 3.7 chose that deliberately, and
phase 8 has to either keep the duplication or collapse it.

**What does a row carry?** Roadmap 8.1 lists `number, date, news_id, context, numerology_value`. The
first four were already there; the item's reduced value is not part of what an activation *is*, and
the `news` collection already stores it under the same `news_id`, so storing it again is a
denormalization that needs a reason.

**How far back does a reading look?** The news window is seven days (`window_days`, phase 5.5).
Roadmap 8.3 asks the forecast to receive "the history of the last 30 days", which is a different
question from "what the day is about" — and ADR 0011 and `docs/CONTEXT_MANAGEMENT.md` explicitly
deferred that read to phase 8 rather than widening the news window.

**Where does "frequency per day" live, and what reads it?** Roadmap 8.2 asks for an aggregation but
not for a surface. The constraints are real: `agents` may not import `vector` (layer table of
`docs/ARCHITECTURE.md`), `models` is a boundary for types rather than a home for logic, and the MCP
tool's return annotation `list[NumberActivation]` is a published contract (phase 6.10,
`docs/MCP_TOOLS.md`) that the server derives the output schema from.

## Decision

We will close phase 8 with the memory log as the project's long-term state, under the decisions
below.

- **`number_history` stays the exact log and `numbers` stays the semantic index.** The log has no
  vector because a question about dates must never depend on a similarity score; the semantic
  collection embeds the snippet because "which activations read like this" is a different question.
  Both keep sharing `NumberActivation` and `activation_payload`, so the two can never drift apart in
  shape.
- **A row carries the item's reduced value.** `NumberActivation.numerology_value` is optional; it is
  written when the item was read and absent otherwise (`exclude_none`, the payload rule of phase
  3.3), and `activate()` copies it from the item. The reason is the read path: a history query
  answers "what was that day read under" without a second lookup in `news`. The field is not indexed
  — nothing filters on it yet, and an unused index is a schema promise the layer cannot keep.
- **Idempotency stays point-id based.** The point id remains `uuid5(NAMESPACE_URL,
  "numenews:activation:<news_id>:<number>")`, so re-ingesting an article overwrites its rows instead
  of appending a second copy of the same event.
- **The memory window is its own parameter.** `Pipeline.history_days` defaults to 30
  (`DEFAULT_HISTORY_DAYS`) and is independent of `window_days` (7): the news window says what the
  reading is *about*, the memory window says what it may *cite*. `forecast` reads
  `get_activations(days=history_days, today=...)` and keeps only the activations whose number occurs
  in the day's own news, so the prompt carries evidence for this reading rather than an unrelated 7
  from last week.
- **The per-day frequency is a pure read-side function.** `vector/history.py::activation_frequency`
  folds the rows a read returned into `DayActivationCount` buckets (newest day first, counting rows).
  It lives in `vector` because that is the layer that owns history, returns a `models` type because
  that is where boundary types live, and is surfaced by the CLI's `HistoryResult.by_day`. The MCP
  `get_history` tool keeps returning the rows themselves, and the forecast prompt format does not
  change: phase 8.3 asks for the window, not for a new rendering, and `docs/PROMPTS.md` and its
  snapshots change only when a prompt does.
- **The phase is documented where the memory is read.** `docs/CONTEXT_MANAGEMENT.md` states the two
  windows, `docs/QDRANT_COLLECTIONS.md` records the payload and the read functions,
  `docs/MCP_TOOLS.md` documents the returned field, and `docs/USER_FLOW.md` shows the CLI report.

## Consequences

Easier: a reading can draw on a month of activation history without touching the news window; a
caller that wants the shape of a period gets `by_day` without counting; and the memory is readable
on its own, because the item's value rides in the row.

Harder and worth remembering:

- The two windows are now two numbers in `Pipeline`, and a caller who widens the news window should
  consider the memory window too; they are independent by design, not by accident.
- `numerology_value` duplicates a value that also lives in `news`. The rows are written at ingest and
  a re-ingest overwrites them, so the copy is as fresh as the last run; nothing recomputes a stored
  article's value without re-writing its points.
- "Frequency" counts activation rows, not distinct numbers: an article that states 11 and 22 gives
  one `(article, number)` row per number, so a day's bucket is a count of mentions. The docstring,
  the model and the tests say so.
- The CLI reports `by_day` while the MCP tool does not. That asymmetry is deliberate — the tool's
  return type is a published contract — and adding the aggregation to the MCP surface would mean a
  new tool, which phase 8 does not ask for.
- `NumberActivation` gaining an optional field is an additive change to the MCP output schema. It is
  optional and absent when uncomputed, so an existing client keeps working untouched.

## References

- `ROADMAP.md` phases 3.7, 5.2, 5.4, 6.10, 7.5 and 8.1–8.4
- [ADR 0003](0003-local-embeddings.md) — the vector layer, its collections and the synchronous
  interface
- [ADR 0011](0011-rag-pipeline-orchestration.md) — the pipeline's window and the deferred 30-day
  history injection
- [`docs/CONTEXT_MANAGEMENT.md`](../CONTEXT_MANAGEMENT.md),
  [`docs/QDRANT_COLLECTIONS.md`](../QDRANT_COLLECTIONS.md),
  [`docs/PROMPTS.md`](../PROMPTS.md)
