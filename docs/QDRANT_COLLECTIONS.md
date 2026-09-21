# Qdrant collections

> Phases 3 and 5. `ROADMAP.md` is the authoritative status; this document records what the vector
> layer actually stores and why. The decisions behind it are in
> [ADR 0003](adr/0003-local-embeddings.md) and [ADR 0011](adr/0011-rag-pipeline-orchestration.md).

Six collections live in Qdrant, all created by `VectorStore.ensure_collections()` (or by the first
write of a collection, which creates its own schema first — the payload indexes must exist **before**
the first point, or Qdrant falls back to filtering after the HNSW walk):

| Collection | Vector | Payload indexes |
|---|---|---|
| `news` | 768d COSINE | `date` datetime, `source` keyword, `numerology_value` integer, `master_number` bool |
| `numbers` | 384d COSINE | `number` integer, `context` keyword |
| `patterns` | 768d COSINE | `type` keyword, `strength` float, `discovered_at` datetime |
| `forecasts` | 768d COSINE | `date` datetime, `dominant_number` integer |
| `number_history` | — (payload only) | `number` integer, `date` datetime |
| `digests` | 768d COSINE | `period_start` datetime, `period_end` datetime |

## The payloads

### `news`

One point per article, written by `upsert_news`. The payload is `NewsItem` with two additions:

```json
{
  "id": "b371bc46-7b4b-5b38-92db-cdf94a550f33",
  "title": "Markets close higher on the seventh",
  "text": "The seventh consecutive session ended in the green.",
  "source": "example.com",
  "date": "2026-09-21T00:00:00Z",
  "url": "https://example.com/markets",
  "numbers": [7, 2026],
  "numerology_value": 7,
  "master_number": false
}
```

- `master_number` is derived (`numerology_value` is 11, 22 or 33) so that a filter can ask for the
  master days without fetching a single vector.
- A field whose value is `None` — `numerology_value` before extraction — is **absent** from the
  payload rather than stored as null: "not computed" must not be an indexed value.
- `date` is the UTC start of the publication day. Qdrant's `datetime` index accepts the full
  timestamp, not `YYYY-MM-DD`, so the day is written as `2026-09-21T00:00:00Z` and read back as a
  `date` by `vector/payloads.py`.

### `numbers` and `number_history`

Both store the same payload — one `NumberActivation`:

```json
{
  "number": 11,
  "date": "2026-09-21T00:00:00Z",
  "news_id": "b371bc46-7b4b-5b38-92db-cdf94a550f33",
  "context": "eleven ministers resigned"
}
```

They answer different questions, which is why both exist:

- `numbers` (384d) is the **semantic** index: an activation is embedded from its `context`, so a
  query like *"финансы и долги"* finds the snippets that read that way. `context` is also a keyword
  index for exact lookups.
- `number_history` has **no vector**: it is the exact log, read with `get_history(number, days)`.
  A question about dates should never depend on a similarity score.

### `patterns`

One point per pattern, written by `save_pattern`:

```json
{
  "id": "8bb3a3e4-53cd-5333-92ab-5309c63d3b78",
  "type": "resonance",
  "numbers": [7],
  "news_ids": ["b371bc46-7b4b-5b38-92db-cdf94a550f33"],
  "strength": 0.75,
  "interpretation": "7 returns across the week's finance coverage",
  "discovered_at": "2026-09-21T12:00:00Z"
}
```

The vector is built from `interpretation` (or, when that is blank, from `type` and the numbers), so
`find_similar_patterns("master numbers around money")` finds the connections that read like that.
`discovered_at` is stamped by `save_pattern` and never rewritten: when a pattern was read back from
storage and saved again, its original timestamp survives.

### `forecasts`

One point per day — a day has exactly one reading, so the point id is derived from the date and a
re-save replaces the previous reading instead of adding a second:

```json
{
  "date": "2026-09-21T00:00:00Z",
  "dominant_number": 11,
  "master_active": true,
  "patterns": [],
  "forecast": "A day of visible endings.",
  "advice": "Say the thing you have been postponing.",
  "warnings": ["decisions taken today will be repeated"]
}
```

`get_forecast(day)` is a point lookup by that id: `None` means the day has not been read yet, while a
missing collection means the store was never initialised. `vector/forecasts.py` keeps the two apart.

### `digests`

One point per summarised period, written by `save_digest` (roadmap 5.5):

```json
{
  "period_start": "2026-09-01T00:00:00Z",
  "period_end": "2026-09-07T00:00:00Z",
  "summary": "Период прошёл под числом 11: ...",
  "numbers": [11, 7]
}
```

`Digest` has no id of its own: the period is the identity, so the point id is `uuid5` over
`(period_start, period_end)` and re-summarising a range replaces its point. Both ends are RFC 3339
days and are indexed as `DATETIME`, because "what did the first week of September look like" is a
range query. The vector is built from `summary` (or, when it is blank, from the numbers), so a later
semantic question about an earlier stretch can find the digest that answers it. Phase 5 stores and
reads the digest; no prompt contains one yet (`docs/CONTEXT_MANAGEMENT.md`).

## Point ids

Ids are derived, never random, so every write is an upsert and a repeated run is idempotent:

| Collection | Id |
|---|---|
| `news` | `NewsId` — `uuid5(NAMESPACE_URL, url)` from `news/items.py` |
| `numbers`, `number_history` | `uuid5(NAMESPACE_URL, "numenews:activation:<news_id>:<number>")` |
| `patterns` | `PatternId` |
| `forecasts` | `uuid5(NAMESPACE_URL, "numenews:forecast:<YYYY-MM-DD>")` |
| `digests` | `uuid5(NAMESPACE_URL, "numenews:digest:<start>:<end>")` |

## Reading the collections

The pipeline's steps read three of them, and each has a read function rather than a raw query:

| Function | Question |
|---|---|
| `get_news_items(store, ids)` | "show me the items these search results name" — the pattern step |
| `read_news_range(store, date_from, date_to)` | "what was published in my window" — inclusive at both ends |
| `get_activations(store, days, today=)` | "what was active recently" — the forecast step's memory |
| `get_history(store, number, days, today=)` | "when was 11 active" — the exact question about one number |
| `get_forecast(store, day)` / `get_digest(store, start, end)` | "have I already read this day / summarised this period" |

## Searching

```python
from numenews.models import NewsFilter
from numenews.vector import VectorStore, hybrid_search_news, search_news, upsert_news

store = VectorStore.from_settings(settings)  # health-checks Qdrant
store.ensure_collections()

upsert_news(store, items)  # embeds with the 768d model, idempotent by NewsId

search_news(store, "число 7 и деньги", NewsFilter(numerology_value=7), limit=10)
hybrid_search_news(store, "число 7 и деньги", NewsFilter(numerology_value=7), limit=10)
```

`NewsFilter` (`models/query.py`) is the typed front end: `date_from`, `date_to`, `source`,
`numerology_value`, `master_number`. `vector/filters.py` turns it into a Qdrant filter; the layers
above never import `qdrant_client`. Date windows are inclusive of `date_to`'s own day, which is why
the generated upper bound is the *start of the next day*.

`search_news` passes the filter as `query_filter`; `hybrid_search_news` uses the multi-stage Query
API — `Prefetch(query=vector, filter=..., limit=...)` followed by `FusionQuery(Fusion.RRF)` — so every
retriever pre-filters its own candidate set. Phase 3 has one dense retriever, so the fusion merges a
single ranking and the returned order is **RRF** (`1 / (60 + rank)`), not cosine; a sparse/BM25
prefetch joins as a second entry in the same list.

## Local mode

`VectorStore.in_memory()` and `QdrantClient(":memory:")` run a real Qdrant engine in-process, but it
**ignores payload indexes** and warns that it does. The tests therefore verify two different things:

- `tests/integration/test_vector_*.py` (in memory) verify behaviour: upserts, idempotency, filters,
  similarity ordering, windows.
- `tests/integration/test_vector_docker.py` (against the container from `make dev`) verifies the
  schema: that each collection's `payload_schema` really holds the indexes in the table above.

Running the Docker file provisions those collections in the developer's Qdrant; it never deletes
anything. `make test` skips it when the container is not running, so a machine without Docker still
gets a green suite.
