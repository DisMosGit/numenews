"""The GNews adapter: RFC 3339 ranges, header auth, and 403 as a spent daily quota.

The fixture keeps the cases the mapper has to survive: a null publisher (falls back to the URL
host), a null description and content (falls back to the headline), a missing timestamp and a
missing URL.
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
from numenews.news.gnews import GNewsSource

from .conftest import news_fixture

ENDPOINT = "https://gnews.io/api/v4/search"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
API_KEY = "test-gnews-key"


def _source(client: httpx.AsyncClient, key: str = API_KEY) -> GNewsSource:
    """Return the adapter with a throwaway key."""
    return GNewsSource(client, api_key=SecretStr(key))


def _ok() -> httpx.Response:
    """Return the recorded successful response."""
    return httpx.Response(200, content=news_fixture("gnews_search.json"))


@pytest.mark.integration
async def test_fetch_maps_the_articles(news_client: AsyncCacheClient) -> None:
    """Two of the five fixture articles are usable; the bad dates and missing URL are skipped."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=_ok())

        items = await _source(news_client).fetch(TOPIC, RANGE)

    assert [item.title for item in items] == [
        "Twenty-two nations sign the accord",
        "A lonely headline",
    ]

    first = items[0]
    assert first.text == "The accord was signed by 22 nations."  # `description` wins
    assert first.source == "Example News"
    assert first.date == date(2026, 9, 21)
    assert first.url == "https://www.example.com/world/accord"
    assert first.id == NewsId(uuid5(NAMESPACE_URL, first.url))

    # A null publisher falls back to the host, and a null description to the headline.
    assert items[1].source == "news.example.org"
    assert items[1].text == "A lonely headline"
    assert items[1].date == date(2026, 9, 20)


@pytest.mark.integration
async def test_fetch_sends_the_key_in_a_header_and_rfc_3339_dates(
    news_client: AsyncCacheClient,
) -> None:
    """GNews wants timestamps, not bare dates, and the free plan caps the page at ten articles."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(return_value=_ok())

        await _source(news_client).fetch(TOPIC, RANGE)

        request = route.calls[-1].request

    assert request.headers["x-api-key"] == API_KEY
    assert API_KEY not in str(request.url)

    params = request.url.params
    assert params["q"] == "politics"
    assert params["from"] == "2026-09-15T00:00:00Z"
    assert params["to"] == "2026-09-21T23:59:59Z"
    assert params["max"] == "10"
    assert params["sortby"] == "publishedAt"


@pytest.mark.integration
def test_from_settings_needs_a_key(settings: Settings, news_client: AsyncCacheClient) -> None:
    """Without its key the source is not constructed at all."""
    assert GNewsSource.from_settings(settings, news_client) is None

    configured = settings.model_copy(update={"gnews_key": SecretStr(API_KEY)})
    source = GNewsSource.from_settings(configured, news_client)

    assert source is not None
    assert source.name == "gnews"


@pytest.mark.integration
async def test_a_spent_daily_quota_is_reported_as_a_rate_limit(
    news_client: AsyncCacheClient,
) -> None:
    """GNews answers a spent daily quota with 403, which the central mapping reads as forbidden."""
    body = b'{"errors":["You have reached your daily quota."]}'

    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(403, content=body))

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await _source(news_client).fetch(TOPIC, RANGE)

    assert caught.value.status_code == 403
    assert "daily quota" in str(caught.value)


@pytest.mark.integration
async def test_a_rejected_key_stays_an_auth_error(news_client: AsyncCacheClient) -> None:
    """Only 403 means quota; a 401 is the key, and retrying it wastes the quota."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(
            return_value=httpx.Response(401, content=b'{"errors":["Invalid API Key provided."]}')
        )

        with pytest.raises(NewsSourceAuthError):
            await _source(news_client).fetch(TOPIC, RANGE)

        assert route.call_count == 1


@pytest.mark.integration
async def test_fetch_returns_nothing_for_an_empty_body(news_client: AsyncCacheClient) -> None:
    """An empty body is a result rather than an error."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=b""))

        assert await _source(news_client).fetch(TOPIC, RANGE) == []
