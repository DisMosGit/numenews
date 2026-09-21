"""The mapping rules every adapter shares.

The five APIs disagree about almost everything except the shape they must produce — a
:class:`~numenews.models.NewsItem` — so the parts of that mapping that do not depend on a response
format live here, once, instead of five times with five chances to drift.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from numenews.models import NewsId


def news_id(url: str) -> NewsId:
    """Return the deterministic id of the article at ``url``.

    Derived from the URL with ``uuid5``, so the same article keeps the same id across runs: phase 5
    gets idempotent ingest without a lookup table, and two feeds reporting the same link collapse to
    one item.
    """
    return NewsId(uuid5(NAMESPACE_URL, url))


def publisher_name(*candidates: str | None, url: str, fallback: str) -> str:
    """Return the publisher, taking the first usable candidate and falling back to the URL host.

    ``NewsItem.source`` means the publisher, not the feed: the aggregator de-duplicates on
    ``(title, source, date)``, so two sources reporting the same article from the same publisher
    must agree on this value. ``fallback`` (the adapter's name) is the last resort for a URL without
    a host, which keeps ``source`` a non-empty string as the model requires.
    """
    for candidate in candidates:
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return urlsplit(url).hostname or fallback


def item_text(*candidates: str | None) -> str:
    """Return the first non-blank candidate, or an empty string.

    The APIs disagree about which field is usable — one has only a headline, another truncates
    ``content`` — so each adapter passes its preference in order and this function only implements
    it.
    """
    for candidate in candidates:
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return ""


def utc_date(moment: datetime) -> date:
    """Return the UTC calendar day of ``moment``.

    A naive timestamp is read as UTC: the feeds that send an offset say the value is UTC, and
    GDELT's ``Z`` suffix parses into a naive datetime.
    """
    if moment.tzinfo is None:
        return moment.date()
    return moment.astimezone(UTC).date()
