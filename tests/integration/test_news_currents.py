"""The Currents adapter: Bearer auth, strict RFC 3339 ranges, and its own timestamp format.

The fixture keeps the fields the mapper reads and the shapes it must survive: a null description
(falls back to the headline), a null title, an ISO timestamp Currents never sends and a missing
`published` field.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient
from pydantic import SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsId, Topic
from numenews.news import (
    NewsSourceAuthError,
    NewsSourceError,
    NewsSourceHTTPError,
    NewsSourceRateLimitError,
)
from numenews.news.currents import CurrentsSource

from .conftest import news_fixture

ENDPOINT = "https://api.currentsapi.services/v1/search"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
API_KEY = "test-currents-key"


def _source(client: httpx.AsyncClient, key: str = API_KEY) -> CurrentsSource:
    """Return the adapter with a throwaway key."""
    return CurrentsSource(client, api_key=SecretStr(key))


def _ok() -> httpx.Response:
    """Return the recorded successful response."""
    return httpx.Response(200, content=news_fixture("currents_search.json"))


@pytest.mark.integration
async def test_fetch_maps_the_news_array(news_client: AsyncCacheClient) -> None:
    """Two of the five fixture articles are usable; the nulls and the odd timestamps are skipped."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=_ok())

        items = await _source(news_client).fetch(TOPIC, RANGE)

    assert [item.title for item in items] == [
        "The thirty-third rescue",
        "A headline with no description",
    ]

    first = items[0]
    assert first.text == "Thirty-three miners were rescued."
    assert first.source == "www.example.com"
    assert first.date == date(2026, 9, 21)
    assert first.url == "https://www.example.com/world/miners"
    assert first.id == NewsId(uuid5(NAMESPACE_URL, first.url))

    assert items[1].source == "news.example.org"
    assert items[1].text == "A headline with no description"
    assert items[1].date == date(2026, 9, 20)


@pytest.mark.integration
async def test_fetch_sends_a_bearer_token_and_rfc_3339_dates(
    news_client: AsyncCacheClient,
) -> None:
    """Currents rejects a bare date, so the range is sent as full timestamps."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=_ok())

        await _source(news_client).fetch(TOPIC, RANGE)

        request = route.calls[-1].request

    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    assert API_KEY not in str(request.url)

    params = request.url.params
    assert params["keywords"] == "politics"
    assert params["start_date"] == "2026-09-15T00:00:00Z"
    assert params["end_date"] == "2026-09-21T23:59:59Z"
    assert params["page_size"] == "20"
    assert "query" not in params  # `keywords` wins when both are sent


@pytest.mark.integration
def test_from_settings_needs_a_key(settings: Settings, news_client: AsyncCacheClient) -> None:
    """Without its key the source is not constructed at all."""
    assert CurrentsSource.from_settings(settings, news_client) is None

    configured = settings.model_copy(update={"currents_key": SecretStr(API_KEY)})
    source = CurrentsSource.from_settings(configured, news_client)

    assert source is not None
    assert source.name == "currents"


@pytest.mark.integration
async def test_fetch_raises_for_an_error_envelope_sent_with_http_200(
    news_client: AsyncCacheClient,
) -> None:
    """A non-`ok` status inside a 200 body must not look like an empty page."""
    body = b'{"status":"error","msg":"Invalid parameters"}'

    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=body))

        with pytest.raises(NewsSourceError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

    assert "Invalid parameters" in str(caught.value)


@pytest.mark.integration
async def test_an_authentication_failure_is_not_retried(news_client: AsyncCacheClient) -> None:
    """Currents answers a missing token with 401."""
    body = b'{"status":"401","msg":"Authentication required"}'

    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=httpx.Response(401, content=body))

        with pytest.raises(NewsSourceAuthError):
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 1


@pytest.mark.integration
async def test_a_rate_limit_with_retry_after_is_retried(news_client: AsyncCacheClient) -> None:
    """Currents sends `Retry-After` on a 429, and the retry's answer is what comes back."""
    limited = httpx.Response(
        429, headers={"Retry-After": "0"}, content=b'{"status":"429","msg":"Too many requests"}'
    )

    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(side_effect=[limited, _ok()])

        items = await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 2

    assert len(items) == 2


@pytest.mark.integration
async def test_a_search_backend_timeout_is_a_retryable_server_error(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """A 503 is retried and then reported as a server failure."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(
            return_value=httpx.Response(503, content=b'{"status":"503","msg":"Backend timeout"}')
        )

        with pytest.raises(NewsSourceHTTPError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 3

    assert caught.value.retryable is True


@pytest.mark.integration
async def test_fetch_returns_nothing_for_an_empty_body(news_client: AsyncCacheClient) -> None:
    """An empty body is a result rather than an error."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=b""))

        assert await _source(news_client).fetch(TOPIC, RANGE) == []


@pytest.mark.integration
async def test_an_unexpected_rate_limit_is_not_retried_forever(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """Without `Retry-After` the backoff takes over, and the budget is still three attempts."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=httpx.Response(429, text="slow down"))

        with pytest.raises(NewsSourceRateLimitError):
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 3
