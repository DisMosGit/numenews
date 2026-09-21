"""NewsAPI.org v2: the widest reach, the most caveats.

Three documented details shape this adapter. The key travels in the ``X-Api-Key`` header rather than
the ``apiKey`` query parameter, so it never reaches a URL, the request log or the cache key. The
free Developer plan answers with articles delayed by 24 hours and allows 100 requests a day, so a
429 here is a daily quota rather than a burst. And ``content`` is truncated with a
``[+1234 chars]`` marker, which is why ``description`` is preferred and the marker is stripped when
the truncated content is all there is.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.errors import NewsSourceError
from numenews.news.http import get_response, parse_json
from numenews.news.items import item_text, news_id, publisher_name, utc_date

NAME = "newsapi"
_ENDPOINT = "https://newsapi.org/v2/everything"
# The documented maximum on every plan; the free plan is limited by its request count, not by this.
_PAGE_SIZE = 100
_TRUNCATION_MARKER = re.compile(r"\s*\[\+\d+ chars\]$")


class _NewsAPIArticleSource(BaseModel):
    """The nested ``source`` object of an article."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None


class _NewsAPIArticle(BaseModel):
    """One entry of the ``articles`` array, as far as this adapter reads it."""

    model_config = ConfigDict(extra="ignore")

    source: _NewsAPIArticleSource | None = None
    title: str | None = None
    description: str | None = None
    url: str | None = None
    content: str | None = None
    # Aliases keep the API's camelCase out of the code while pydantic still reads the wire format.
    published_at: str | None = Field(default=None, alias="publishedAt")


class _NewsAPIResponse(BaseModel):
    """The ``/v2/everything`` envelope.

    ``totalResults`` and the rest of the envelope are ignored: the adapter needs the articles and
    the error status, and the fields it does not read are covered by ``extra="ignore"``.
    """

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    code: str | None = None
    message: str | None = None
    articles: tuple[_NewsAPIArticle, ...] = ()


class NewsAPISource:
    """NewsAPI.org v2 behind the :class:`~numenews.news.protocol.NewsSource` protocol."""

    name = NAME

    def __init__(self, client: httpx.AsyncClient, *, api_key: SecretStr) -> None:
        self._client = client
        self._api_key = api_key

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.AsyncClient) -> NewsAPISource | None:
        """Return the adapter, or ``None`` when no key is configured for it."""
        if settings.newsapi_key is None:
            return None
        return cls(client, api_key=settings.newsapi_key)

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return NewsAPI's articles for ``topic`` within ``date_range``.

        Raises:
            NewsSourceError: on a transport failure, a non-2xx status, an error envelope, or an
                unparsable body.
        """
        response = await get_response(
            self._client,
            source=self.name,
            url=_ENDPOINT,
            params={
                "q": topic.query,
                "from": date_range.start.isoformat(),
                "to": date_range.end.isoformat(),
                "pageSize": _PAGE_SIZE,
                "sortBy": "publishedAt",
            },
            headers={"X-Api-Key": self._api_key.get_secret_value()},
        )
        parsed = parse_json(response, _NewsAPIResponse, source=self.name)
        if parsed is None:
            return []
        if parsed.status == "error":
            raise NewsSourceError(f"{NAME} reported {parsed.code}: {parsed.message}")
        return [item for article in parsed.articles if (item := _to_item(article)) is not None]


def _to_item(article: _NewsAPIArticle) -> NewsItem | None:
    """Map one article, or ``None`` when it lacks what a :class:`NewsItem` needs."""
    url = article.url.strip() if article.url else ""
    title = article.title.strip() if article.title else ""
    published = _parse_published(article.published_at)
    if not url or not title or published is None:
        return None
    publisher = article.source.name if article.source is not None else None
    return NewsItem(
        id=news_id(url),
        title=title,
        # `description` is a clean sentence; `content` is truncated and only a fallback.
        text=item_text(article.description, _strip_truncation(article.content), title),
        source=publisher_name(publisher, url=url, fallback=NAME),
        date=published,
        url=url,
    )


def _strip_truncation(value: str | None) -> str | None:
    """Drop NewsAPI's ``[+1234 chars]`` marker so it never reaches the pipeline."""
    if value is None:
        return None
    return _TRUNCATION_MARKER.sub("", value).strip() or None


def _parse_published(value: str | None) -> date | None:
    """Parse the ISO 8601 UTC ``publishedAt`` into its calendar day, or ``None`` when unusable."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return utc_date(moment)
