"""GNews v4: the tightest free plan of the five.

The free plan allows 100 requests a day, caps a response at ten articles (``max`` defaults to ten,
and the paid plans allow up to 100), delays articles by twelve hours and answers a spent daily quota
with **403**. That last one is non-standard — HTTP 403 usually means "authenticated but forbidden",
which is how :func:`~numenews.news.http.get_response` classifies it — so this adapter translates a
403 into :class:`~numenews.news.errors.NewsSourceRateLimitError`, the failure it actually is.

The key travels in the ``X-Api-Key`` header (the ``apikey`` query parameter is the alternative), and
``from``/``to`` are RFC 3339 timestamps rather than bare dates.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.errors import NewsSourceAuthError, NewsSourceRateLimitError
from numenews.news.http import get_response, parse_json
from numenews.news.items import item_text, news_id, publisher_name, utc_date

NAME = "gnews"
_ENDPOINT = "https://gnews.io/api/v4/search"
# The free plan's ceiling; a paid plan would raise it to 100.
_MAX_ARTICLES = 10


class _GNewsArticleSource(BaseModel):
    """The nested ``source`` object of an article."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None


class _GNewsArticle(BaseModel):
    """One entry of the ``articles`` array, as far as this adapter reads it."""

    model_config = ConfigDict(extra="ignore")

    source: _GNewsArticleSource | None = None
    title: str | None = None
    description: str | None = None
    content: str | None = None
    url: str | None = None
    published_at: str | None = Field(default=None, alias="publishedAt")


class _GNewsResponse(BaseModel):
    """The ``/v4/search`` envelope; ``totalArticles`` and ``errors`` are not read."""

    model_config = ConfigDict(extra="ignore")

    articles: tuple[_GNewsArticle, ...] = ()


class GNewsSource:
    """GNews v4 behind the :class:`~numenews.news.protocol.NewsSource` protocol."""

    name = NAME

    def __init__(self, client: httpx.AsyncClient, *, api_key: SecretStr) -> None:
        self._client = client
        self._api_key = api_key

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.AsyncClient) -> GNewsSource | None:
        """Return the adapter, or ``None`` when no key is configured for it."""
        if settings.gnews_key is None:
            return None
        return cls(client, api_key=settings.gnews_key)

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return GNews' articles for ``topic`` within ``date_range``.

        Raises:
            NewsSourceError: on a transport failure, a non-2xx status or an unparsable body.
        """
        try:
            response = await get_response(
                self._client,
                source=self.name,
                url=_ENDPOINT,
                params={
                    "q": topic.query,
                    "from": _start_stamp(date_range),
                    "to": _end_stamp(date_range),
                    "max": _MAX_ARTICLES,
                    "sortby": "publishedAt",
                },
                headers={"X-Api-Key": self._api_key.get_secret_value()},
            )
        except NewsSourceAuthError as error:
            # 403 is GNews' spent daily quota; 401 is the rejected key.
            if error.status_code == 403:
                raise NewsSourceRateLimitError(str(error), status_code=403) from error
            raise
        parsed = parse_json(response, _GNewsResponse, source=self.name)
        if parsed is None:
            return []
        return [item for article in parsed.articles if (item := _to_item(article)) is not None]


def _start_stamp(date_range: DateRange) -> str:
    """Return the range start as an RFC 3339 UTC timestamp."""
    start = datetime.combine(date_range.start, time.min, tzinfo=UTC)
    return start.isoformat().replace("+00:00", "Z")


def _end_stamp(date_range: DateRange) -> str:
    """Return the range end at 23:59:59 so the whole last day is included."""
    end = datetime.combine(date_range.end, time(23, 59, 59), tzinfo=UTC)
    return end.isoformat().replace("+00:00", "Z")


def _to_item(article: _GNewsArticle) -> NewsItem | None:
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
        text=item_text(article.description, article.content, title),
        source=publisher_name(publisher, url=url, fallback=NAME),
        date=published,
        url=url,
    )


def _parse_published(value: str | None) -> date | None:
    """Parse the ISO 8601 UTC ``publishedAt`` into its calendar day, or ``None`` when unusable."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return utc_date(moment)
