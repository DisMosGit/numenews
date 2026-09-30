"""The HTTP layer: one cached client, the retry policy, and status → error mapping.

`respx` answers the requests, so the tests exercise the real `hishel` cache against a sqlite file in
the test's temporary directory. Where a test only needs the retry to happen, the backoff is
patched to zero through the `instant_retries` fixture; the fallback wait itself is covered by the
503 test, which uses the real policy.

What the cache leaves on disk is asserted by reading the database itself rather than through
`hishel`, because "the credential is not in the file" is a claim about the file.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import closing
from pathlib import Path

import hishel
import httpx
import pytest
import respx
from hishel import AsyncSqliteStorage
from hishel.httpx import AsyncCacheClient
from pydantic import BaseModel, ConfigDict

from numenews.config import Settings
from numenews.logging import configure_logging
from numenews.news import (
    NewsSourceAuthError,
    NewsSourceError,
    NewsSourceHTTPError,
    NewsSourceParseError,
    NewsSourceRateLimitError,
    NewsSourceTransportError,
)
from numenews.news.http import NEWS_CACHE_TTL_SECONDS, build_news_client, get_response, parse_json

URL = "https://news.test/v1/search"

# Stands in for Mediastack's `access_key`: the one credential of the five that travels in the query
# string, and so the one that could reach the cache database.
SECRET = "mediastack-secret"


class _Payload(BaseModel):
    """Stand-in for an adapter's private response model."""

    model_config = ConfigDict(extra="ignore", strict=True)

    title: str


async def _fetch(client: httpx.AsyncClient, **params: str) -> httpx.Response:
    """Call `get_response` the way an adapter does."""
    return await get_response(client, source="test", url=URL, params=params)


def _cache_database(settings: Settings) -> Path:
    """Return the cache database the client was configured with."""
    return settings.cache_dir / "news.db"


def _cache_bytes(settings: Settings) -> bytes:
    """Return the bytes of the cache database, or nothing when it was never created.

    A run whose every request was refused by the filter never reaches the storage, so the file
    may not exist at all — which is itself part of what these tests assert.
    """
    database = _cache_database(settings)
    return database.read_bytes() if database.exists() else b""


def _stored_entries(settings: Settings) -> list[bytes]:
    """Return the serialized entries in the cache database, read directly.

    Read through `sqlite3` rather than the file's bytes so that the write-ahead log is merged
    into the result: an entry still in the log is stored as surely as one already checkpointed.
    """
    database = _cache_database(settings)
    if not database.exists():
        return []
    with closing(sqlite3.connect(database)) as connection:
        return [row[0] for row in connection.execute("SELECT data FROM entries")]


async def _an_empty_body() -> AsyncIterator[bytes]:
    """Yield no chunks: an entry needs a response stream, and this one keeps no body."""
    chunks: tuple[bytes, ...] = ()
    for chunk in chunks:
        yield chunk


async def _store_an_entry(settings: Settings, url: str) -> None:
    """Write one entry through hishel's own storage, as a version without the filter did.

    Going through the storage rather than hand-written SQL keeps the row in the format hishel
    really writes, so the check meets the bytes a cache written before the rule would hold.
    """
    storage = AsyncSqliteStorage(
        database_path=_cache_database(settings), default_ttl=NEWS_CACHE_TTL_SECONDS
    )
    try:
        await storage.create_entry(
            hishel.Request(method="GET", url=url),
            hishel.Response(status_code=200, stream=_an_empty_body()),
            key="written-before-the-rule",
        )
    finally:
        await storage.close()


@pytest.mark.integration
async def test_the_second_identical_request_comes_from_the_cache(
    news_client: AsyncCacheClient,
) -> None:
    """docs/NEWS_SOURCES.md: a repeat within the TTL must not touch the network."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(return_value=httpx.Response(200, json={"title": "sun"}))

        first = await _fetch(news_client, q="sun")
        second = await _fetch(news_client, q="sun")

        assert route.call_count == 1

    assert first.extensions.get("hishel_from_cache") is False
    assert second.extensions.get("hishel_from_cache") is True
    assert second.json() == {"title": "sun"}


@pytest.mark.integration
async def test_different_query_parameters_are_cached_separately(
    news_client: AsyncCacheClient,
) -> None:
    """The cache key is the full URL, so a different query is a different entry, not a stale hit."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(return_value=httpx.Response(200, json={"title": "sun"}))

        await _fetch(news_client, q="sun")
        await _fetch(news_client, q="moon")

        assert route.call_count == 2


@pytest.mark.integration
async def test_a_request_carrying_a_credential_is_never_cached(settings: Settings) -> None:
    """The credential costs that request its cache entry: nothing is written for it at all."""
    upstream: list[str] = []
    client = build_news_client(settings)
    try:
        with respx.mock(assert_all_called=False) as router:

            def answer(request: httpx.Request) -> httpx.Response:
                upstream.append(str(request.url))
                return httpx.Response(200, json={"title": "sun"})

            route = router.get(URL).mock(side_effect=answer)

            first = await _fetch(client, q="sun", access_key=SECRET)
            second = await _fetch(client, q="sun", access_key=SECRET)

            # Nothing was stored, so the second call has nothing to be served from.
            assert route.call_count == 2
    finally:
        await client.aclose()

    # The request itself is untouched: refusing it the cache must not refuse it the key.
    assert SECRET in upstream[0]
    assert first.json() == second.json() == {"title": "sun"}
    assert _stored_entries(settings) == []
    assert SECRET.encode() not in _cache_bytes(settings)


@pytest.mark.integration
async def test_a_refused_request_leaves_the_cache_working_for_the_next_one(
    settings: Settings,
) -> None:
    """The filter refuses one request, not the client: an ordinary fetch is cached as before."""
    client = build_news_client(settings)
    try:
        with respx.mock(assert_all_called=False) as router:
            route = router.get(URL).mock(return_value=httpx.Response(200, json={"title": "sun"}))

            await _fetch(client, q="sun", access_key=SECRET)
            await _fetch(client, q="sun")
            cached = await _fetch(client, q="sun")

            # One call for the credentialed request, one for the first ordinary one, none for the
            # second: the plain URL is cached even though it shares an endpoint with a refused one.
            assert route.call_count == 2
    finally:
        await client.aclose()

    assert cached.extensions.get("hishel_from_cache") is True


@pytest.mark.integration
async def test_the_cache_lives_in_the_configured_directory_with_the_fifteen_minute_ttl(
    news_client: AsyncCacheClient,
    settings: Settings,
) -> None:
    """The client reads `Settings.cache_dir`, and the TTL is the documented fifteen minutes."""
    storage = news_client.storage

    assert isinstance(storage, AsyncSqliteStorage)
    assert storage.default_ttl == NEWS_CACHE_TTL_SECONDS
    assert NEWS_CACHE_TTL_SECONDS == 900.0
    assert storage.database_path == settings.cache_dir / "news.db"


@pytest.mark.integration
async def test_a_transient_failure_is_retried_and_the_success_is_cached(
    news_client: AsyncCacheClient,
) -> None:
    """A 503 is retried; the successful answer is what the cache remembers."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json={"title": "sun"})]
        )

        response = await _fetch(news_client, q="sun")

        assert route.call_count == 2

    assert parse_json(response, _Payload, source="test") == _Payload(title="sun")


@pytest.mark.integration
async def test_an_error_response_is_never_cached(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """A cached 503 would be replayed for the whole TTL instead of being retried."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json={"title": "sun"}),
            ]
        )

        with pytest.raises(NewsSourceHTTPError):
            await _fetch(news_client, q="sun")
        healthy = await _fetch(news_client, q="sun")
        from_cache = await _fetch(news_client, q="sun")

        # Three attempts for the failed call, one for the successful one — and the third read
        # never reaches the network at all, so none of the 503s were stored.
        assert route.call_count == 4

    assert parse_json(healthy, _Payload, source="test") == _Payload(title="sun")
    assert from_cache.extensions.get("hishel_from_cache") is True


@pytest.mark.integration
@pytest.mark.parametrize("directive", ["no-store", "no-cache", "private"])
async def test_a_response_that_forbids_storing_is_fetched_again(
    news_client: AsyncCacheClient,
    directive: str,
) -> None:
    """The fifteen-minute TTL is not allowed to outlast the origin's own refusal."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            return_value=httpx.Response(
                200, headers={"Cache-Control": directive}, json={"title": "sun"}
            )
        )

        first = await _fetch(news_client, q="sun")
        second = await _fetch(news_client, q="sun")

        # Nothing was stored, so the second call has nothing to be served from.
        assert route.call_count == 2

    assert first.json() == second.json() == {"title": "sun"}
    # `is not True` rather than `is False`: a request the filter turns away never reaches the code
    # that marks a response, so the flag is absent rather than set — what matters is that it is not
    # claiming a cache hit.
    assert second.extensions.get("hishel_from_cache") is not True


@pytest.mark.integration
async def test_a_cacheable_response_is_still_served_from_the_cache(
    news_client: AsyncCacheClient,
) -> None:
    """An ordinary freshness header is ignored, exactly as before: the TTL remains the rule.

    This is the half that keeps the narrowed policy narrow. The five APIs send no usable freshness
    metadata, so a cache that honoured `max-age` would answer nothing; what is honoured is the three
    directives that forbid keeping a response at all.
    """
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            return_value=httpx.Response(
                200, headers={"Cache-Control": "public, max-age=300"}, json={"title": "sun"}
            )
        )

        await _fetch(news_client, q="sun")
        cached = await _fetch(news_client, q="sun")

        assert route.call_count == 1

    assert cached.extensions.get("hishel_from_cache") is True


@pytest.mark.integration
async def test_a_503_that_keeps_failing_is_reported_after_three_attempts(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """The retry budget is finite: three attempts, then the failure reaches the aggregator."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(return_value=httpx.Response(503))

        with pytest.raises(NewsSourceHTTPError) as caught:
            await _fetch(news_client, q="sun")

        assert route.call_count == 3

    assert caught.value.status_code == 503
    assert caught.value.retryable is True


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, NewsSourceHTTPError),
        (404, NewsSourceHTTPError),
        (401, NewsSourceAuthError),
        (403, NewsSourceAuthError),
    ],
)
async def test_a_client_error_maps_to_its_exception_and_is_not_retried(
    news_client: AsyncCacheClient,
    status: int,
    expected: type[NewsSourceError],
) -> None:
    """A 4xx is final: one request, one exception, no attempt spent on a hopeless retry."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(return_value=httpx.Response(status, text="nope"))

        with pytest.raises(expected) as caught:
            await _fetch(news_client, q="sun")

        assert route.call_count == 1

    assert caught.value.retryable is False
    assert "nope" in str(caught.value)


@pytest.mark.integration
async def test_a_rate_limit_with_retry_after_is_retried_after_that_delay(
    news_client: AsyncCacheClient,
) -> None:
    """`Retry-After: 0` is honoured (and keeps this test fast); the retry then succeeds."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}, text="slow down"),
                httpx.Response(200, json={"title": "sun"}),
            ]
        )

        response = await _fetch(news_client, q="sun")

        assert route.call_count == 2

    assert response.status_code == 200


@pytest.mark.integration
async def test_a_rate_limit_without_retry_after_reports_none(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """GDELT answers a throttle with plain text and no header; the message keeps the text."""
    with respx.mock(assert_all_called=False) as router:
        router.get(URL).mock(return_value=httpx.Response(429, text="Please limit requests"))

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _fetch(news_client, q="sun")

    assert caught.value.retry_after is None
    assert "Please limit requests" in str(caught.value)


@pytest.mark.integration
async def test_an_http_date_retry_after_falls_back_to_the_backoff(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """`Retry-After` may legally be an HTTP date; the numeric parse then falls back to backoff."""
    with respx.mock(assert_all_called=False) as router:
        router.get(URL).mock(
            return_value=httpx.Response(
                429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, text="slow down"
            )
        )

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _fetch(news_client, q="sun")

    assert caught.value.retry_after is None


@pytest.mark.integration
@pytest.mark.parametrize("retry_after", ["nan", "-5", "3.5", "Wed, 21 Oct 2026 07:28:00 GMT"])
async def test_a_retry_after_outside_the_delta_seconds_grammar_is_no_hint_at_all(
    news_client: AsyncCacheClient,
    instant_retries: None,
    retry_after: str,
) -> None:
    """Only a whole number of seconds is a hint; every other value falls to the backoff."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": retry_after}, text="slow down")
        )

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _fetch(news_client, q="sun")

        # Every attempt was answered and the failure that surfaces is still a source error, so the
        # value never reached tenacity's sleep as a delay it would reject with a `ValueError`.
        assert route.call_count == 3

    assert caught.value.retry_after is None


@pytest.mark.integration
async def test_a_large_retry_after_is_clamped_to_the_retry_ceiling(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """A valid hint is capped at fifteen seconds rather than slept in full."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "9999"}, text="slow down")
        )

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _fetch(news_client, q="sun")

        assert route.call_count == 3

    assert caught.value.retry_after == 15.0  # `numenews.news.http._MAX_RETRY_WAIT_SECONDS`


@pytest.mark.integration
async def test_a_transport_failure_becomes_a_retryable_source_error(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """A connection that never answered is retried like a 5xx, and never escapes as `httpx`."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(URL).mock(side_effect=httpx.ConnectError("connection refused"))

        with pytest.raises(NewsSourceTransportError) as caught:
            await _fetch(news_client, q="sun")

        assert route.call_count == 3

    assert caught.value.retryable is True


@pytest.mark.integration
def test_parse_json_validates_the_documented_body() -> None:
    """A well-formed body becomes the adapter's model, ignoring unknown fields."""
    response = httpx.Response(200, content=b'{"title": "sun", "unknown": 1}')

    assert parse_json(response, _Payload, source="test") == _Payload(title="sun")


@pytest.mark.integration
def test_parse_json_returns_none_for_an_empty_body() -> None:
    """GDELT answers "no matches" with an empty body, which is a result rather than a failure."""
    assert parse_json(httpx.Response(200, content=b""), _Payload, source="test") is None


@pytest.mark.integration
def test_parse_json_rejects_a_body_that_is_not_the_documented_json() -> None:
    """A plain-text or HTML body (GDELT sends both) must fail loudly, not parse into nonsense."""
    with pytest.raises(NewsSourceParseError) as caught:
        parse_json(
            httpx.Response(200, content=b"<html>Invalid mode.</html>"), _Payload, source="test"
        )

    assert "test" in str(caught.value)


@pytest.mark.integration
async def test_building_the_client_logs_a_warning_for_a_cache_that_holds_a_credential(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A cache written before the rule is not deleted, but it does announce itself."""
    await _store_an_entry(settings, f"{URL}?q=sun&access_key={SECRET}")
    # Configuring inside the test is what points the log at `capsys`'s stream: the autouse fixture
    # binds the handler before `capsys` replaces `sys.stderr`, so its records go to the real one.
    configure_logging(settings)

    client = build_news_client(settings)
    try:
        assert "news.http.cache_holds_credential" in capsys.readouterr().err
    finally:
        await client.aclose()


@pytest.mark.integration
async def test_building_the_client_is_quiet_for_a_cache_that_holds_no_credential(
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The warning is for a real leftover, so an ordinary cache must not produce one.

    Two rows are stored, and neither carries a credential: one ordinary query, and one whose *value*
    holds the literal text `access_key=` while its parameter names only look similar. A check that
    reported the bare bytes would flag both, and a warning that fires on every run is one nobody
    reads.
    """
    await _store_an_entry(settings, f"{URL}?q=sun")
    await _store_an_entry(settings, f"{URL}?q=access_key=notes&access_key_backup=no")
    configure_logging(settings)

    client = build_news_client(settings)
    try:
        captured = capsys.readouterr().err
    finally:
        await client.aclose()

    assert "news.http.cache_holds_credential" not in captured


@pytest.mark.integration
async def test_build_news_client_reads_the_process_settings(settings: Settings) -> None:
    """`build_news_client()` needs no argument: it reads the process-wide settings."""
    client = build_news_client()
    try:
        storage = client.storage

        assert isinstance(storage, AsyncSqliteStorage)
        assert storage.database_path == settings.cache_dir / "news.db"
    finally:
        await client.aclose()
