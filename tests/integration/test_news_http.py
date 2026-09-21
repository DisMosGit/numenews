"""The HTTP layer: one cached client, the retry policy, and status → error mapping.

`respx` answers the requests, so the tests exercise the real `hishel` cache against a sqlite file in
the test's temporary directory. Where a test only needs the retry to happen, the backoff is
patched to zero through the `instant_retries` fixture; the fallback wait itself is covered by the
503 test, which uses the real policy.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from hishel import AsyncSqliteStorage
from hishel.httpx import AsyncCacheClient
from pydantic import BaseModel, ConfigDict

from numenews.config import Settings
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


class _Payload(BaseModel):
    """Stand-in for an adapter's private response model."""

    model_config = ConfigDict(extra="ignore", strict=True)

    title: str


async def _fetch(client: httpx.AsyncClient, **params: str) -> httpx.Response:
    """Call `get_response` the way an adapter does."""
    return await get_response(client, source="test", url=URL, params=params)


@pytest.mark.integration
async def test_the_second_identical_request_comes_from_the_cache(
    news_client: AsyncCacheClient,
) -> None:
    """Roadmap 2.2: a repeat within the TTL must not touch the network."""
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
async def test_the_cache_lives_in_the_configured_directory_with_the_fifteen_minute_ttl(
    news_client: AsyncCacheClient,
    settings: Settings,
) -> None:
    """The client reads `Settings.cache_dir`, and the TTL is the roadmap's fifteen minutes."""
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
async def test_build_news_client_reads_the_process_settings(settings: Settings) -> None:
    """`build_news_client()` needs no argument: it reads the process-wide settings."""
    client = build_news_client()
    try:
        storage = client.storage

        assert isinstance(storage, AsyncSqliteStorage)
        assert storage.database_path == settings.cache_dir / "news.db"
    finally:
        await client.aclose()
