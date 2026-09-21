# News Sources

> **Implemented** in `src/numenews/news/` (phase 2). Five APIs behind one
> [`NewsSource`](../src/numenews/news/protocol.py) Protocol, one cached HTTP client, and an
> aggregator that degrades gracefully. `ROADMAP.md` is the authoritative status.

## The layer in one picture

```python
from numenews.models import DateRange, Topic
from numenews.news import fetch_news

items = await fetch_news(Topic(query="politics"), DateRange(start=..., end=...))
```

```
Topic + DateRange
      │
      ├─ GDELT ────┐
      ├─ NewsAPI ──┤   asyncio.gather
      ├─ GNews ────┤   (one failure never fails the run)
      ├─ Mediastack┤
      └─ Currents ─┘
                   ▼
      get_response: httpx + hishel cache (15 min) + tenacity retry
                   ▼
      parse_json → private response model → NewsItem
                   ▼
      range filter → de-duplication on (title, source, date) → list[NewsItem]
```

Every adapter implements the same two members:

```python
class NewsSource(Protocol):
    @property
    def name(self) -> str: ...
    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]: ...
```

Only GDELT works without a key, so the default demo path needs no configuration at all
(`AGENTS.md`); the other four are constructed only when their key is present.

## The five sources

| Adapter | Key | Endpoint | Auth | Free tier | Per request | Date parameters | `published` format | `source` from |
|---|---|---|---|---|---|---|---|---|
| `gdelt` | — | `https://api.gdeltproject.org/api/v2/doc/doc` | none | no quota, ~1 req/5 s | 75 (250 max) | `startdatetime`/`enddatetime` = `YYYYMMDDHHMMSS` UTC, last 3 months | `seendate` = `20260920T190000Z` | `domain` |
| `newsapi` | `NEWSAPI_KEY` | `https://newsapi.org/v2/everything` | `X-Api-Key` header | 100 req/day, 24 h delay, 1 month history | 100 | `from`/`to` = `YYYY-MM-DD` | `publishedAt` = `2026-09-21T14:30:00Z` | `source.name` |
| `gnews` | `GNEWS_KEY` | `https://gnews.io/api/v4/search` | `X-Api-Key` header | 100 req/day, 12 h delay, 30 days | 10 (100 paid) | `from`/`to` = RFC 3339 | `publishedAt` = `2026-09-21T09:15:00Z` | `source.name` |
| `mediastack` | `MEDIASTACK_KEY` | `https://api.mediastack.com/v1/news` | `access_key` **query param** | 100 calls/month, 30 min delay | 100 | `date=YYYY-MM-DD,YYYY-MM-DD` | `published_at` = `2026-09-21T14:30:00+00:00` | `source` (name) |
| `currents` | `CURRENTS_KEY` | `https://api.currentsapi.services/v1/search` | `Authorization: Bearer` header | 250 req/day, 30 days | 20 (300 max) | `start_date`/`end_date` = RFC 3339 **only** | `published` = `2026-09-21 12:05:00 +0000` | URL host |

Free-tier numbers are the documented plan limits; the per-request caps are what the adapters send.
Nothing in the layer depends on a paid plan, but a paid plan widens the numbers in the table.

## Per-source notes

### GDELT DOC 2.0

- **No API key**, and the only source that answers failures with *plain text*: a bad mode is
  `Invalid mode.` with HTTP 200, and a throttle is a 429 with a text body. The HTTP layer therefore
  reports a truncated body snippet and never tries to parse an error envelope — an HTML body at 200
  becomes `NewsSourceParseError`.
- `mode=artlist` returns links with headlines only: there is **no description and no author**, so
  `NewsItem.text` is the headline. `NewsItem.text` is never empty because a title is required for an
  item to exist at all.
- A query with no matches comes back as an **empty body**, which the layer treats as "no results"
  rather than as an error.
- The endpoint throttles a client to roughly one request every five seconds and only covers the last
  three months; a range outside that window returns nothing rather than an error.
- Free-form query syntax lives in the `query` value (`"quoted phrase"`, `(a OR b)`, `-exclude`,
  `sourcelang:english`, `domain:cnn.com`), because GDELT has no separate filter parameters.

### NewsAPI.org v2

- The key travels in the `X-Api-Key` header rather than the `apiKey` query parameter, so it never
  appears in a URL, a log record or the hashed cache key.
- The API can answer **`{"status":"error", …}` with HTTP 200**; that is raised as a
  `NewsSourceError` rather than returned as an empty page.
- `content` is truncated with a `[+1234 chars]` marker; `description` is preferred and the marker is
  stripped when the truncated content is all there is.
- A rate-limited 429 on the free plan usually means the **daily quota** is spent, so the retry gives
  up after three attempts rather than hammering the endpoint.

### GNews v4

- The key travels in the `X-Api-Key` header.
- `403` is GNews' **spent daily quota** rather than a permission problem; the adapter translates it
  into `NewsSourceRateLimitError` so callers are not misled (a 401 stays an auth failure).
- `from`/`to` are RFC 3339 timestamps; the free plan caps a response at ten articles.

### Mediastack

- `access_key` is the only documented auth form, so the key necessarily travels in the query string.
  It is never logged (`get_response` logs the endpoint without parameters), but it does end up inside
  the *hashed* cache key.
- The free plan is live-only; `date=YYYY-MM-DD,YYYY-MM-DD` and historical queries are documented as
  Standard-plan functions, so a free account may answer with `function_access_restricted`. The range
  is still sent — the documented contract comes first, and the aggregator degrades on the error.
- There is no `content` field; `description` is the whole body the API offers.

### Currents

- The key travels in `Authorization: Bearer` (the legacy `apiKey` query parameter is not used).
- `start_date`/`end_date` must be **strict RFC 3339**: a bare `2026-09-01` is a 400, so the adapter
  always sends full timestamps.
- `published` is `2026-03-24 12:05:00 +0000`, which no ISO parser accepts; it is parsed with an
  explicit format.
- `keywords` is used instead of `query` (when both are sent, `keywords` wins), and the endpoint's
  default language filter is English.
- Currents has no publisher field — only `author`, which names a person — so `NewsItem.source` is the
  URL host.

## Dates, ranges and de-duplication

- **All dates are UTC calendar days.** A timestamp with an offset is converted; a naive one is read
  as UTC (GDELT's `Z` suffix parses into a naive datetime).
- **The aggregator owns the range.** Each API filters with its own precision — GDELT takes whole
  seconds, NewsAPI whole days, Currents forces full timestamps — so the final
  `start <= item.date <= end` check happens once, after every source has answered. Keeping it in one
  place is what makes the boundary exact and identical for all five.
- **De-duplication is literal**: `(title, source, date)`, first occurrence wins, in source order.
  Nothing is normalised beyond the adapters' own trimming, so two feeds reporting the same story
  collapse only when they agree on all three values.
- **`NewsItem.source` is the publisher, not the feed.** That is what makes the de-duplication key
  meaningful across feeds: a null publisher falls back to the URL hostname, and the adapter's name is
  the last resort.
- **`NewsItem.id` is `uuid5(NAMESPACE_URL, url)`**, so the same article keeps the same id across
  runs and the ingest step of phase 5 is idempotent by `news_id` with no lookup table.

## The cache

The client is one `hishel`-backed `httpx.AsyncClient`, configured in
[`news/http.py`](../src/numenews/news/http.py):

```python
AsyncSqliteStorage(database_path=settings.cache_dir / "news.db", default_ttl=900.0)
FilterPolicy(response_filters=[_CacheOnlySuccesses()])
```

Two decisions are worth knowing about:

- **`FilterPolicy`, not the RFC 9111 specification policy.** None of the five APIs sends a freshness
  header (`Cache-Control`/`Expires`) that the specification policy could use, so it treats every
  stored response as stale and the cache never answers a request — measured: two identical requests,
  two network calls. `FilterPolicy` plus the storage's `default_ttl` is what makes the roadmap's
  fifteen minutes real. (ADR 0009, in phase 10.3, is where this becomes a recorded decision.)
- **Only 2xx responses are stored.** `hishel` stores whatever the transport returned, so without
  `_CacheOnlySuccesses` a cached 503 would be replayed for the whole TTL instead of being retried,
  and a 429 would hide the moment the quota reset.

The database lives in `Settings.cache_dir` (default `.cache/hishel`); `hishel` creates the directory
and drops a `.gitignore` holding `*` into it. The client is **not** a module-level singleton: closing
it closes the sqlite storage for good, so `fetch_news` creates one per call, and phase 6 may keep a
long-lived one in its application context.

## The retry policy

`get_response` retries inside `tenacity`, at most three attempts, and the exception decides:

| Failure | Exception | Retried |
|---|---|---|
| timeout, DNS, connection reset | `NewsSourceTransportError` | yes |
| 5xx | `NewsSourceHTTPError` | yes |
| 429 | `NewsSourceRateLimitError` | yes, waiting for `Retry-After` when present |
| 401, 403 | `NewsSourceAuthError` | no |
| other 4xx | `NewsSourceHTTPError` | no |
| body that is not the documented JSON | `NewsSourceParseError` | no |

The backoff is exponential with jitter, capped at fifteen seconds; a numeric `Retry-After` wins when
the source sends one. `tenacity` 9 no longer ships `wait_retry_after`, so the wait is ours.

## What this layer deliberately does not do

- **No language filter.** None is sent, so each API uses its own default (Currents defaults to
  English; GDELT is language-agnostic). Add it in a later phase with one mapping table per API — half
  a mapping is worse than none.
- **No pagination.** One page per source per run, capped by the free tier; the caps are constants in
  each adapter.
- **No de-duplication beyond the literal key** — no fuzzy titles, no canonical URLs.
- **No key handling in the CLI layer yet** (phase 7): the adapters read `Settings`
  through `from_settings`, and `build_sources` decides which of them exist. The MCP server of phase 6
  does the same — it hands `Settings` to `build_sources` and has no key handling of its own.

## Configuration

```bash
NEWSAPI_KEY=      # newsapi.org — 100 req/day on the free Developer plan
GNEWS_KEY=        # gnews.io — 100 req/day, 10 articles per request
MEDIASTACK_KEY=   # mediastack.com — 100 calls/month
CURRENTS_KEY=     # currentsapi.services — 250 req/day, 20 results per request
CACHE_DIR=.cache/hishel
```

Every key is optional and blank values are ignored (`.env.example` ships them commented out). A
source whose key is missing is simply not queried, so a half-configured machine still produces a
result from the feeds that are available; with no keys at all, GDELT alone answers.
