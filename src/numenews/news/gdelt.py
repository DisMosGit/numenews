"""GDELT DOC 2.0: the one source that needs no key.

GDELT's ``artlist`` mode returns links with headlines and no body, so ``text`` is the headline — the
pipeline reads numbers out of the title rather than out of an article it does not have. GDELT is
also the only source that answers failures with plain text (``Invalid mode.`` at HTTP 200, a
throttle message at 429), which is why the HTTP layer reports a raw body snippet.

Three documented limits shape the request: ``maxrecords`` defaults to 75 and is capped at 250,
``STARTDATETIME``/``ENDDATETIME`` are UTC ``YYYYMMDDHHMMSS`` inside the last three months, and the
endpoint throttles a client to roughly one request every five seconds — which is why this adapter is
queried once per run and why a throttle is retried with the shared backoff rather than with a burst.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import httpx
from pydantic import BaseModel, ConfigDict

from numenews.models import DateRange, NewsItem, Topic
from numenews.news.http import get_response, parse_json
from numenews.news.items import item_text, news_id, publisher_name, utc_date

NAME = "gdelt"
_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_MAX_RECORDS = 75
# GDELT wants `YYYYMMDDHHMMSS` in the request and answers with `YYYYMMDDTHHMMSSZ`.
_STAMP_FORMAT = "%Y%m%d%H%M%S"
_SEENDATE_FORMAT = "%Y%m%dT%H%M%SZ"


class _GDELTArticle(BaseModel):
    """One entry of the ``articles`` array, as far as this adapter reads it."""

    model_config = ConfigDict(extra="ignore")

    url: str | None = None
    title: str | None = None
    seendate: str | None = None
    domain: str | None = None


class _GDELTResponse(BaseModel):
    """The ``mode=artlist`` envelope; a query with no matches carries no ``articles`` key."""

    model_config = ConfigDict(extra="ignore")

    articles: tuple[_GDELTArticle, ...] = ()


class GDELTSource:
    """GDELT DOC 2.0 behind the :class:`~numenews.news.protocol.NewsSource` protocol."""

    name = NAME

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return GDELT's headlines for ``topic`` within ``date_range``.

        Raises:
            NewsSourceError: on a transport failure, a non-2xx status or an unparsable body.
        """
        response = await get_response(
            self._client,
            source=self.name,
            url=_ENDPOINT,
            params={
                "query": topic.query,
                "mode": "artlist",
                "format": "json",
                "sort": "datedesc",
                "maxrecords": _MAX_RECORDS,
                "startdatetime": _start_stamp(date_range),
                "enddatetime": _end_stamp(date_range),
            },
        )
        parsed = parse_json(response, _GDELTResponse, source=self.name)
        if parsed is None:
            return []
        return [item for article in parsed.articles if (item := _to_item(article)) is not None]


def _start_stamp(date_range: DateRange) -> str:
    """Return the range start as GDELT's UTC ``YYYYMMDDHHMMSS``."""
    start = datetime.combine(date_range.start, time.min, tzinfo=UTC)
    return start.strftime(_STAMP_FORMAT)


def _end_stamp(date_range: DateRange) -> str:
    """Return the range end at 23:59:59 so the whole last day is included."""
    end = datetime.combine(date_range.end, time(23, 59, 59), tzinfo=UTC)
    return end.strftime(_STAMP_FORMAT)


def _to_item(article: _GDELTArticle) -> NewsItem | None:
    """Map one article, or ``None`` when it lacks what a :class:`NewsItem` needs."""
    url = article.url.strip() if article.url else ""
    title = article.title.strip() if article.title else ""
    published = _parse_seendate(article.seendate)
    if not url or not title or published is None:
        return None
    return NewsItem(
        id=news_id(url),
        title=title,
        # The artlist response has no description or content field at all.
        text=item_text(article.title),
        source=publisher_name(article.domain, url=url, fallback=NAME),
        date=published,
        url=url,
    )


def _parse_seendate(value: str | None) -> date | None:
    """Parse GDELT's ``20260920T190000Z`` into the UTC calendar day, or ``None`` when unusable."""
    if not value:
        return None
    try:
        moment = datetime.strptime(value, _SEENDATE_FORMAT)
    except ValueError:
        return None
    return utc_date(moment)
