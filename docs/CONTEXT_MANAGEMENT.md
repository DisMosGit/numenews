# Context management

> Phase 5.5. `ROADMAP.md` is the authoritative status; this document records how much of the past the
> agents see, what is compressed instead, and what is deliberately not wired into a prompt yet.

An installation that runs every day accumulates more news than any prompt can hold. numenews answers
that with three mechanisms of different granularity:

| Mechanism | Horizon | Where it lives | Who reads it |
|---|---|---|---|
| The sliding window | the day and the six before it | Qdrant `news` | the pattern and forecast steps |
| The activation history | the same window, by number | Qdrant `number_history` | the forecast step |
| The digest | everything older | Qdrant `digests` | a caller, and a later phase's prompt |

## The sliding window

`Pipeline.window_days` is seven by default, and the window ends on the day being handled: the day
itself and the six before it. The rule has exactly one definition —
`numenews.pipeline.context.window_start` — and both readers use it:

- `Pipeline.forecast(day)` reads the news of the window with `read_news_range(store, start, end)`;
- `Pipeline.summarize(...)` partitions the same window into `recent` and `older`
  (`numenews.pipeline.context.partition`).

`partition` is inclusive of the window's last day and leaves *future* items out of both halves: a
replay of an old day must not summarise what had not happened yet. Ties aside, both halves come back
oldest first, because a prompt and a digest both read better in chronological order.

The window's end is injectable (`today=`) exactly like `extract_dates_regex` and `get_history`
before it, so a replayed batch is deterministic and no test depends on the wall clock. The window is
the only place those readings happen: every step takes its dates from the pipeline's injected
`Clock`.

## The activation history

`number_history` is the exact log of which number occurred in which article on which day (phase 3.7,
roadmap phase 8). The forecast step reads the window back with `get_activations(store, days,
today=)` — the read *without* a number, because a day's reading is interested in whatever was active
— and then keeps only the activations whose number appears in the day's own news. The prompt
therefore carries evidence for *this* reading: a 7 from last week does not appear in a reading about
an 11.

The window is deliberately short (seven days) for the forecast. Roadmap 8.3 extends the read to the
30-day window the `ForecastAgent` was built for; the agent already accepts the history as an
argument, so that change is a parameter, not a refactor.

## The digest

`Pipeline.summarize(topic, date_range)` is the opt-in compression: it ingests the range, partitions
it, and summarises everything older than the window into one `Digest`:

```python
Digest(
    period_start=date(2026, 9, 1),
    period_end=date(2026, 9, 14),
    summary="Период прошёл под числом 11: ...",
    numbers=(11, 7),
)
```

- **The period is the identity.** There is no id of its own; the point id is `uuid5` over
  `(period_start, period_end)`, so re-summarising a range replaces its point instead of adding a
  second memory (phase 3.6's idiom for forecasts).
- **Two items are the minimum.** One article is not a digest, so `build_digest` returns `None` and
  writes nothing. A daily run whose range falls entirely inside the window produces `None`, which is
  the normal case, not an error.
- **The limit bounds the prompt, not the period.** `Pipeline.summary_limit` (50) caps how many older
  items the model is shown — a busy month is one summarisation call, not many — while the stored
  period and its numbers still describe every older item. Labelling a digest with a period it only
  partly read would make the memory claim more than it knows.
- **The numbers are ours.** The model writes the prose; the period and the reduced values come from
  the items, because a model asked to list the numbers it saw can list one that was not there.
- **A digest is never injected.** Phase 5 stores it and reads it back through `get_digest`; no
  prompt contains one yet. The prompt snapshots in `docs/PROMPTS.md` change when the roadmap asks
  for a prompt change, and no phase-5 task does. Wiring it into the pattern or forecast prompt is
  additive when a later task calls for it.

## Cost

| Step | Model calls | Notes |
|---|---|---|
| `ingest`, first run | one extraction per article | zero on a repeated run: the item is known |
| `ingest`, repeated run | 0 | idempotency by `news_id` |
| `analyze` | one per non-empty set of ids | zero for no items, unknown ids, or a repeated set |
| `forecast`, cached day | 0 | the date-derived point id answers first |
| `forecast`, first time | pattern agent + forecast agent | `rerun_analysis=False` drops the first |
| `summarize` | one, plus the ingest's extractions | only when two or more items fall outside the window |
