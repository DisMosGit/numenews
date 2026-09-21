"""Currents: Bearer auth, RFC 3339 ranges, and a timestamp format of its own.

Two of its parameters are stricter than the neighbours'. ``start_date``/``end_date`` must be full
RFC 3339 timestamps — a bare ``2026-09-01`` is a 400 rather than a default — and the response's
``published`` field is ``2026-03-24 12:05:00 +0000``, which no ISO parser accepts, so it is parsed
with an explicit format. ``keywords`` wins over ``query`` when both are sent, so only ``keywords``
is sent.

The key travels in the ``Authorization: Bearer`` header (the legacy ``apiKey`` query parameter is
documented but not used). The free plan allows 250 requests a day and 20 results per request.

Currents has no publisher field — only ``author``, which names a person — so ``source`` is the URL
host: the aggregator de-duplicates on ``(title, source, date)``, and a byline is not a publisher.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.errors import NewsSourceError
from numenews.news.http import get_response, parse_json
from numenews.news.items import item_text, news_id, publisher_name, utc_date

NAME = "currents"
_ENDPOINT = "https://api.currentsapi.services/v1/search"
# The free plan's per-request ceiling; the endpoint itself allows up to 300.
_PAGE_SIZE = 20
_PUBLISHED_FORMAT = "%Y-%m-%d %H:%M:%S %z"


class _CurrentsArticle(BaseModel):
    """One entry of the ``news`` array, as far as this adapter reads it."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    description: str | None = None
    url: str | None = None
    published: str | None = None


class _CurrentsResponse(BaseModel):
    """The ``/v1/search`` envelope, including the error status it can send with HTTP 200."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    msg: str | None = None
    news: tuple[_CurrentsArticle, ...] = ()


class CurrentsSource:
    """Currents behind the :class:`~numenews.news.protocol.NewsSource` protocol."""

    name = NAME

    def __init__(self, client: httpx.AsyncClient, *, api_key: SecretStr) -> None:
        self._client = client
        self._api_key = api_key

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.AsyncClient) -> CurrentsSource | None:
        """Return the adapter, or ``None`` when no key is configured for it."""
        if settings.currents_key is None:
            return None
        return cls(client, api_key=settings.currents_key)

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return Currents' articles for ``topic`` within ``date_range``.

        Raises:
            NewsSourceError: on a transport failure, a non-2xx status, an error envelope, or an
                unparsable body.
        """
        response = await get_response(
            self._client,
            source=self.name,
            url=_ENDPOINT,
            params={
                "keywords": topic.query,
                "start_date": _start_stamp(date_range),
                "end_date": _end_stamp(date_range),
                "page_size": _PAGE_SIZE,
            },
            headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
        )
        parsed = parse_json(response, _CurrentsResponse, source=self.name)
        if parsed is None:
            return []
        if parsed.status != "ok":
            raise NewsSourceError(f"{NAME} reported {parsed.status}: {parsed.msg}")
        return [item for article in parsed.news if (item := _to_item(article)) is not None]


def _start_stamp(date_range: DateRange) -> str:
    """Return the range start as the strict RFC 3339 timestamp Currents requires."""
    start = datetime.combine(date_range.start, time.min, tzinfo=UTC)
    return start.isoformat().replace("+00:00", "Z")


def _end_stamp(date_range: DateRange) -> str:
    """Return the range end at 23:59:59 so the whole last day is included."""
    end = datetime.combine(date_range.end, time(23, 59, 59), tzinfo=UTC)
    return end.isoformat().replace("+00:00", "Z")


def _to_item(article: _CurrentsArticle) -> NewsItem | None:
    """Map one article, or ``None`` when it lacks what a :class:`NewsItem` needs."""
    url = article.url.strip() if article.url else ""
    title = article.title.strip() if article.title else ""
    published = _parse_published(article.published)
    if not url or not title or published is None:
        return None
    return NewsItem(
        id=news_id(url),
        title=title,
        # Currents has no `content`; `description` is the whole body it offers.
        text=item_text(article.description, title),
        source=publisher_name(None, url=url, fallback=NAME),
        date=published,
        url=url,
    )


def _parse_published(value: str | None) -> date | None:
    """Parse Currents' ``2026-03-24 12:05:00 +0000`` into its UTC calendar day."""
    if not value:
        return None
    try:
        moment = datetime.strptime(value, _PUBLISHED_FORMAT)
    except ValueError:
        return None
    return utc_date(moment)
