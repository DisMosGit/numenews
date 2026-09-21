"""The NewsAPI.org adapter: header auth, ISO dates, and the HTTP-200 error envelope.

The fixture is a hand-written response in the documented shape, including the fields this adapter
has to survive: a null publisher, a null description, a truncated `content`, a missing title and an
unparsable timestamp.
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
    NewsSourceRateLimitError,
)
from numenews.news.newsapi import NewsAPISource

from .conftest import news_fixture

ENDPOINT = "https://newsapi.org/v2/everything"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
API_KEY = "test-newsapi-key"


def _source(client: httpx.AsyncClient, key: str = API_KEY) -> NewsAPISource:
    """Return the adapter with a throwaway key."""
    return NewsAPISource(client, api_key=SecretStr(key))


def _ok() -> httpx.Response:
    """Return the recorded successful response."""
    return httpx.Response(200, content=news_fixture("newsapi_everything.json"))


@pytest.mark.integration
async def test_fetch_maps_the_articles(news_client: AsyncCacheClient) -> None:
    """Three of the six fixture articles are usable; the nulls and the bad dates are skipped."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=_ok())

        items = await _source(news_client).fetch(TOPIC, RANGE)

    assert [item.title for item in items] == [
        "The 11th hour deal",
        "Resonance in the markets",
        "A headline with neither description nor content",
    ]

    first = items[0]
    assert first.text == "A budget deal arrived in the 11th hour."  # `description` wins
    assert first.source == "The Verge"
    assert first.date == date(2026, 9, 21)
    assert first.url == "https://www.theverge.com/2026/9/21/deal"
    assert first.id == NewsId(uuid5(NAMESPACE_URL, first.url))

    # A null publisher falls back to the URL host, and the truncation marker is stripped.
    assert items[1].source == "news.example.net"
    assert items[1].text == "Markets closed at 7777 points."
    assert items[1].date == date(2026, 9, 20)

    # With neither description nor content, the headline is the only text there is.
    assert items[2].text == items[2].title
    assert items[2].source == "Textless"


@pytest.mark.integration
async def test_fetch_returns_nothing_for_an_empty_body(news_client: AsyncCacheClient) -> None:
    """NewsAPI always answers with JSON, but an empty body is a result rather than an error."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=b""))

        assert await _source(news_client).fetch(TOPIC, RANGE) == []


@pytest.mark.integration
async def test_fetch_sends_the_key_in_a_header_and_the_range_in_the_query(
    news_client: AsyncCacheClient,
) -> None:
    """The key never appears in the URL, so it never reaches the log or the cache key."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=_ok())

        await _source(news_client).fetch(TOPIC, RANGE)

        request = route.calls[-1].request

    assert request.headers["x-api-key"] == API_KEY
    assert API_KEY not in str(request.url)

    params = request.url.params
    assert params["q"] == "politics"
    assert params["from"] == "2026-09-15"
    assert params["to"] == "2026-09-21"
    assert params["pageSize"] == "100"
    assert params["sortBy"] == "publishedAt"
    assert "apiKey" not in params


@pytest.mark.integration
def test_from_settings_needs_a_key(settings: Settings, news_client: AsyncCacheClient) -> None:
    """Without its key the source is not constructed at all, so the fetch path stays absent."""
    assert NewsAPISource.from_settings(settings, news_client) is None

    configured = settings.model_copy(update={"newsapi_key": SecretStr(API_KEY)})
    source = NewsAPISource.from_settings(configured, news_client)

    assert source is not None
    assert source.name == "newsapi"


@pytest.mark.integration
async def test_fetch_raises_for_an_error_envelope_sent_with_http_200(
    news_client: AsyncCacheClient,
) -> None:
    """NewsAPI can report `status: error` in a 200 body; that must not look like an empty page."""
    body = b'{"status":"error","code":"apiKeyInvalid","message":"Your API key is invalid."}'

    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=body))

        with pytest.raises(NewsSourceError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

    assert "apiKeyInvalid" in str(caught.value)


@pytest.mark.integration
async def test_a_daily_rate_limit_is_retried_and_then_succeeds(
    news_client: AsyncCacheClient,
) -> None:
    """Roadmap 2.4: tenacity retries the 429, and the retry's answer is what comes back."""
    limited = httpx.Response(
        429,
        headers={"Retry-After": "0"},
        content=b'{"status":"error","code":"rateLimited","message":"Too many requests."}',
    )

    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(side_effect=[limited, _ok()])

        items = await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 2

    assert len(items) == 3


@pytest.mark.integration
async def test_a_persistent_rate_limit_reports_the_remaining_quota(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """A daily quota is exhausted after three attempts, not hammered until midnight."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(429, text="Too many requests."))

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

    assert "Too many requests." in str(caught.value)


@pytest.mark.integration
async def test_a_rejected_key_is_not_retried(news_client: AsyncCacheClient) -> None:
    """The free plan's most common failure is a wrong key; retrying it wastes the quota."""
    body = b'{"status":"error","code":"apiKeyMissing","message":"Your API key is missing."}'

    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=httpx.Response(401, content=body))

        with pytest.raises(NewsSourceAuthError):
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 1
