"""The Mediastack adapter: `access_key` in the query, a `data` array, offset timestamps.

The fixture covers the fields the mapper reads and the ones it must survive: a null `source` (falls
back to the URL host), a null `description` (falls back to the headline), a null title and an
unparsable `published_at`.
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
from numenews.news import NewsSourceAuthError, NewsSourceRateLimitError
from numenews.news.mediastack import MediastackSource

from .conftest import news_fixture

ENDPOINT = "https://api.mediastack.com/v1/news"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
API_KEY = "test-mediastack-key"


def _source(client: httpx.AsyncClient, key: str = API_KEY) -> MediastackSource:
    """Return the adapter with a throwaway key."""
    return MediastackSource(client, api_key=SecretStr(key))


def _ok() -> httpx.Response:
    """Return the recorded successful response."""
    return httpx.Response(200, content=news_fixture("mediastack_news.json"))


@pytest.mark.integration
async def test_fetch_maps_the_data_array(news_client: AsyncCacheClient) -> None:
    """Two of the five entries are usable; the missing title and the bad dates are skipped."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=_ok())

        items = await _source(news_client).fetch(TOPIC, RANGE)

    assert [item.title for item in items] == [
        "The eleventh hour budget",
        "A headline with no description",
    ]

    first = items[0]
    assert first.text == "Talks ran to the 11th hour."
    assert first.source == "Example News"
    assert first.date == date(2026, 9, 21)
    assert first.url == "https://www.example.com/budget"
    assert first.id == NewsId(uuid5(NAMESPACE_URL, first.url))

    # A null publisher falls back to the host, and a null description to the headline.
    assert items[1].source == "news.example.net"
    assert items[1].text == "A headline with no description"
    assert items[1].date == date(2026, 9, 20)


@pytest.mark.integration
async def test_fetch_sends_the_key_in_the_query_and_the_documented_range(
    news_client: AsyncCacheClient,
) -> None:
    """`access_key` is the only auth form Mediastack documents, and the range is comma-separated."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=_ok())

        await _source(news_client).fetch(TOPIC, RANGE)

        params = route.calls[-1].request.url.params

    assert params["access_key"] == API_KEY
    assert params["keywords"] == "politics"
    assert params["date"] == "2026-09-15,2026-09-21"
    assert params["limit"] == "100"
    assert params["sort"] == "published_desc"


@pytest.mark.integration
def test_from_settings_needs_a_key(settings: Settings, news_client: AsyncCacheClient) -> None:
    """Without its key the source is not constructed at all."""
    assert MediastackSource.from_settings(settings, news_client) is None

    configured = settings.model_copy(update={"mediastack_key": SecretStr(API_KEY)})
    source = MediastackSource.from_settings(configured, news_client)

    assert source is not None
    assert source.name == "mediastack"


@pytest.mark.integration
async def test_fetch_returns_nothing_for_an_empty_body(news_client: AsyncCacheClient) -> None:
    """An empty body is a result rather than an error."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=b""))

        assert await _source(news_client).fetch(TOPIC, RANGE) == []


@pytest.mark.integration
async def test_a_rejected_key_is_not_retried(news_client: AsyncCacheClient) -> None:
    """A missing or invalid key is final."""
    body = b'{"error":{"code":"missing_access_key","message":"No access key supplied."}}'

    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=httpx.Response(401, content=body))

        with pytest.raises(NewsSourceAuthError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 1

    assert "missing_access_key" in str(caught.value)


@pytest.mark.integration
async def test_a_monthly_quota_is_reported_as_a_rate_limit(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """The free plan's call count is tiny, and a spent one surfaces as a 429."""
    body = b'{"error":{"code":"usage_limit_reached","message":"Usage limit reached."}}'

    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(429, content=body))

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

    assert "usage_limit_reached" in str(caught.value)
