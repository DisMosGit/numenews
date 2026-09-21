# 9. Cache the news feeds with `hishel` in filter mode

## Status

Accepted (phase 2)

## Date

2026-09-21

## Context

The five news APIs are queried together, several times a day, during development and from the MCP
server, and all but GDELT count requests against a daily quota on their free tiers. `ROADMAP.md`
fixes a fifteen-minute cache: within one working session the same query should hit the network once.
A cache is also what makes a repeated `numenews today` reproducible when a feed is throttled.

`httpx` has no cache of its own, so the layer needed a third-party one, and the obvious candidate —
the RFC 9111 specification policy — turned out not to work here. None of the five APIs sends
`Cache-Control` or `Expires` headers. Under the specification policy a stored response without a
freshness lifetime is treated as stale, so the cache is asked, misses, and the request goes out
anyway: measured with two identical requests, two network calls, which is exactly what the cache was
supposed to prevent. `hishel` offers a second, non-specification mode — a storage with a
`default_ttl` (a `hishel` extension) and a `FilterPolicy` — in which storing and answering are
explicit decisions rather than header arithmetic. That mode makes the roadmap's fifteen minutes
real.

Two further problems had to be solved at the same layer. `hishel` stores whatever the transport
returned, so a cached 503 would be replayed for the whole TTL instead of being retried, and a cached
429 would hide the moment a quota reset. And the cache key hashes the request, which means API key
material must not end up on the wrong side of it: four of the five adapters send their key in a
header, while Mediastack documents `access_key` in the query string only.

## Decision

We will cache every news request through one `hishel`-backed `httpx.AsyncClient`, built by
`build_news_client(settings)` in `src/numenews/news/http.py`:

1. **`FilterPolicy` plus `AsyncSqliteStorage(default_ttl=900)`, not the RFC 9111 policy.** The
   storage's TTL, not a response header, is the freshness rule: a stored response answers for
   fifteen minutes and then stops. `FilterPolicy(response_filters=[_CacheOnlySuccesses()])` is the
   policy that lets that rule apply.
2. **Only 2xx responses are stored.** `_CacheOnlySuccesses` decides from the status line alone
   (`needs_body() == False`), so a 429 or a 503 is retried by `tenacity` instead of being replayed
   from the cache, and an error can never outlive the moment it happened.
3. **The database lives in `Settings.cache_dir`** (default `.cache/hishel`) as `news.db`; `hishel`
   creates the directory and drops a `.gitignore` holding `*` into it, so the cache never appears in
   `git status`.
4. **One client per run, never a module-level singleton.** Closing the client closes its sqlite
   storage for good, so `fetch_news` builds a client and closes it, while the MCP `AppContext` keeps
   one alive for the server's lifetime. Reusing a closed one would be a bug that appears only after
   the first call.
5. **Keys stay out of URLs and logs where the API allows it.** NewsAPI, GNews and Currents send the
   key in a header, and Mediastack's `access_key` is the documented query form — it is never logged,
   but it is part of the *hashed* cache key. That asymmetry is documented rather than hidden.
6. **The cache is not a correctness dependency.** `fetch_news` degrades on a failed source whatever
   the cache holds; the cache only avoids repeating a request that already answered.

## Consequences

- **What becomes easier.** Development and repeated demos stop burning free-tier quota; a re-run
  within the TTL is fast and deterministic; and the retry policy keeps its meaning, because a cached
  error cannot shadow a retry.
- **What becomes harder.** A stale answer can be served for up to fifteen minutes after a feed
  corrects itself, and no test may depend on the on-disk cache: the `settings` fixture points
  `Settings.cache_dir` at a temporary directory, the `respx` tests install their own transport, and
  the tests that exercise the two policies directly are in
  `tests/integration/test_news_http.py` (cache hit on the second identical request, TTL and database
  path, and an error never stored).
- **What we explicitly did not do.** No `Cache-Control` parsing, no per-source TTL table, no shared
  process-wide cache, no cache in front of the LLM endpoint — the agents stay uncached, because an
  uncached model answer is part of what makes the forecast honest.
- **Follow-up work.** A cache-clearing command is not needed yet (the directory is gitignored and
  `make clean` removes the volumes). If a source starts sending freshness headers, the specification
  policy becomes viable again and this ADR is superseded rather than edited.

## References

- [ADR 0003](0003-local-embeddings.md) — the same "local by default, no keys" posture in the vector layer
- [`docs/NEWS_SOURCES.md`](../NEWS_SOURCES.md) — the five APIs, their quotas and §The cache
- [`src/numenews/news/http.py`](../../src/numenews/news/http.py) — `build_news_client`,
  `_CacheOnlySuccesses` and the retry policy
- [`ROADMAP.md`](../../ROADMAP.md) — phase 2, tasks 2.2 and 2.9
- [`hishel`](https://hishel.com/) — storage TTLs and filtering policies
