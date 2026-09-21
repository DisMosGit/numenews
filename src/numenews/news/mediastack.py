"""Mediastack: the only source that takes its key as a query parameter.

``access_key`` is the sole authentication form the API documents, so the key necessarily travels in
the query string. Nothing logs it — :func:`~numenews.news.http.get_response` records the endpoint
without its parameters — but it does end up inside the hashed cache key, which is why this module
never builds a full URL for a log record or an error message.

The free plan allows 100 requests a month and serves live news delayed by half an hour; the
``date=YYYY-MM-DD,YYYY-MM-DD`` range and historical queries are documented as Standard-plan
functions, so a free account may answer this adapter's range request with
``function_access_restricted``. The range is still sent, because implementing the documented
contract is right and the aggregator degrades on the error; ``docs/NEWS_SOURCES.md`` documents the
caveat.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.http import get_response, parse_json
from numenews.news.items import item_text, news_id, publisher_name, utc_date

NAME = "mediastack"
_ENDPOINT = "https://api.mediastack.com/v1/news"
# The documented ceiling; the free plan is limited by its monthly call count.
_LIMIT = 100


class _MediastackArticle(BaseModel):
    """One entry of the ``data`` array, as far as this adapter reads it."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    url: str | None = None
    source: str | None = None
    published_at: str | None = None


class _MediastackResponse(BaseModel):
    """The ``/v1/news`` envelope; ``pagination`` is not read."""

    model_config = ConfigDict(extra="ignore")

    data: tuple[_MediastackArticle, ...] = ()


class MediastackSource:
    """Mediastack behind the :class:`~numenews.news.protocol.NewsSource` protocol."""

    name = NAME

    def __init__(self, client: httpx.AsyncClient, *, api_key: SecretStr) -> None:
        self._client = client
        self._api_key = api_key

    @classmethod
    def from_settings(
        cls, settings: Settings, client: httpx.AsyncClient
    ) -> MediastackSource | None:
        """Return the adapter, or ``None`` when no key is configured for it."""
        if settings.mediastack_key is None:
            return None
        return cls(client, api_key=settings.mediastack_key)

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return Mediastack's articles for ``topic`` within ``date_range``.

        Raises:
            NewsSourceError: on a transport failure, a non-2xx status or an unparsable body.
        """
        response = await get_response(
            self._client,
            source=self.name,
            url=_ENDPOINT,
            params={
                "access_key": self._api_key.get_secret_value(),
                "keywords": topic.query,
                "date": f"{date_range.start.isoformat()},{date_range.end.isoformat()}",
                "limit": _LIMIT,
                "sort": "published_desc",
            },
        )
        parsed = parse_json(response, _MediastackResponse, source=self.name)
        if parsed is None:
            return []
        return [item for article in parsed.data if (item := _to_item(article)) is not None]


def _to_item(article: _MediastackArticle) -> NewsItem | None:
    """Map one article, or ``None`` when it lacks what a :class:`NewsItem` needs."""
    url = article.url.strip() if article.url else ""
    title = article.title.strip() if article.title else ""
    published = _parse_published(article.published_at)
    if not url or not title or published is None:
        return None
    return NewsItem(
        id=news_id(url),
        title=title,
        # Mediastack has no `content`; `description` is the whole body it offers.
        text=item_text(article.description, title),
        source=publisher_name(article.source, url=url, fallback=NAME),
        date=published,
        url=url,
    )


def _parse_published(value: str | None) -> date | None:
    """Parse the ISO 8601 ``published_at`` into its UTC calendar day, or ``None`` when unusable."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return utc_date(moment)
