# Tasks

## 1. Keep credentials out of the cache database

- [x] 1.1 Add a request filter in `src/numenews/news/http.py` that refuses a request whose query string carries a credential, so hishel neither looks it up nor writes it, and pass it to `FilterPolicy` in `build_news_client`. Verify with `uv run ruff check . && uv run mypy .`
- [x] 1.2 Extract the "does this URL carry a credential" test into a pure helper and cover it in `tests/unit/test_news_http.py`: a URL carrying `access_key` is refused, a URL without one is not, and a repeated parameter and the other documented credential names are all recognised. Verify with `uv run pytest tests/unit/test_news_http.py -v`
- [x] 1.3 Add the integration tests to `tests/integration/test_news_http.py` that perform a fetch with a credential through a real client and then read `.cache/hishel/news.db` directly: no entry was stored, the secret appears nowhere in the file, the request that reached the mocked upstream still carried the real key, and a request without a credential is still served from the cache on the second call. Verify with `uv run pytest tests/integration/test_news_http.py -v`
- [x] 1.4 Log a warning when building the client if the cache database already holds a request with a credential parameter, so a cache written before this change announces itself. Verify with `uv run pytest tests/integration/test_news_http.py -v -k warning`
- [x] 1.5 Document credential handling and the disposable cache in `docs/NEWS_SOURCES.md`: that a request carrying a credential query parameter is not cached at all, why redacting it instead would not have worked, and that removing `.cache/hishel/news.db` clears rows written before this change. Verify by reading the section against `src/numenews/news/http.py`

## 2. Refuse to store what the origin forbade storing

- [x] 2.1 Widen the response filter in `src/numenews/news/http.py` so a response whose `Cache-Control` carries `no-store`, `no-cache` or `private` is not stored, alongside the existing 2xx rule, and rename it and its docstring to describe the storage decision it now makes. Verify with `uv run mypy .`
- [x] 2.2 Add the directive-parsing unit tests to `tests/unit/test_news_http.py`: each refused directive is detected in its plain, upper-case and `=value` forms, and a response with an ordinary cache header is still stored. Verify with `uv run pytest tests/unit/test_news_http.py -v`
- [x] 2.3 Add the integration tests to `tests/integration/test_news_http.py` showing a `no-store` response is fetched from upstream on the next call while a cacheable response is not, using `respx` to count requests. Verify with `uv run pytest tests/integration/test_news_http.py -v`
- [x] 2.4 Record the narrowed policy in `docs/NEWS_SOURCES.md`: the TTL remains the freshness mechanism for responses that permit storing, and the three refused directives are the deliberate exception to it. Verify by reading the section against the filter in `src/numenews/news/http.py`

## 3. Write activation history in one batch

- [ ] 3.1 Add a batched history write to `src/numenews/vector/history.py` that ensures the collection once and upserts every point in one call, and make `record_activation` a single-element delegation to it so the public surface is unchanged. Verify with `uv run mypy .`
- [ ] 3.2 Replace the per-activation loop in the ingest write phase (`src/numenews/pipeline/steps.py`) with one call to the batched write. Verify with `uv run ruff check .`
- [ ] 3.3 Add the unit tests to `tests/unit/test_vector_history.py` for the empty batch writing nothing without touching the collection, and for the single-activation path storing the same point id as before. Verify with `uv run pytest tests/unit/test_vector_history.py -v`
- [ ] 3.4 Add the integration test to `tests/integration/test_vector_history.py` asserting a batch of activations stores exactly one point per `(article, number)` pair and that `get_history` returns them all. Verify with `uv run pytest tests/integration/test_vector_history.py -v`
- [ ] 3.5 Confirm the existing ingest tests still pass unchanged, since the stored result must be identical: `uv run pytest tests/integration/test_pipeline_ingest.py tests/integration/test_pipeline_e2e.py -v`

## 4. Integration verification

- [ ] 4.1 Run the full suite and the strict validator: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest tests/unit tests/integration -v` and `openspec validate "harden-news-cache-and-source-robustness" --strict`
- [ ] 4.2 Confirm the two changes compose: whichever is applied second, the phase must still end with the `news` upsert as its last write (3.2 changes the statement immediately before it in `fix-ingest-and-forecast-integrity`), and the ingest tests from both changes must pass with both applied
