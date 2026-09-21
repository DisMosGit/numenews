"""Model ⇄ Qdrant payload conversion, embedding texts and point ids.

Qdrant stores payloads as dicts, so this module turns a domain model into one and back. The dict
never crosses a module boundary: every function that returns one returns it to the client library,
and everything a caller sees is a model again.

Three rules are visible in every function here:

* **Dates are RFC 3339.** ``2026-09-21T00:00:00Z``, not ``2026-09-21``: a `DATETIME` payload index
  only indexes the full timestamp, and the domain models' ``date`` is turned back by slicing the
  string. A day is stored as its UTC start.
* **``None`` values are dropped.** An item whose numerology has not been computed has no
  ``numerology_value`` key at all rather than a null one; a null would still be indexed and would
  make "not computed" indistinguishable from "computed to null".
* **Point ids are derived, never random.** A repeated ingest overwrites the same point, which is
  what makes phase 5 idempotent without a lookup table.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date

from numenews.models import NewsItem
from numenews.numerology import is_master


def news_payload(item: NewsItem) -> dict[str, object]:
    """Return the payload of one news item, indexed fields included.

    ``master_number`` is derived rather than stored on the model: it is a question about
    ``numerology_value`` (is it 11, 22 or 33?), and the answer must be a field a filter can use.
    """
    payload: dict[str, object] = dict(item.model_dump(mode="json", exclude_none=True))
    payload["date"] = iso_day(item.date)
    if item.numerology_value is not None:
        payload["master_number"] = is_master(item.numerology_value)
    return payload


def news_from_payload(payload: Mapping[str, object]) -> NewsItem:
    """Rebuild a :class:`~numenews.models.NewsItem` from a stored payload.

    The date is normalized back to ``YYYY-MM-DD`` first because the model is strict and accepts no
    timestamp, and JSON validation is the path ``NewsId`` documents for reading stored payloads.
    Unknown keys (``master_number``) are ignored by Pydantic.
    """
    restored = dict(payload)
    date_value = restored.get("date")
    if isinstance(date_value, str):
        restored["date"] = date_value[:10]
    return NewsItem.model_validate_json(json.dumps(restored))


def news_embedding_text(item: NewsItem) -> str:
    """Return the text embedded for one item: headline and body, or the URL when both are blank.

    Two feeds of the five ship items with an empty description, and the URL is the only text left
    that still says what the item is about; embedding an empty string would map every such item to
    the same point.
    """
    return f"{item.title}\n\n{item.text}".strip() or item.url


def news_point_id(item: NewsItem) -> str:
    """Return the point id of one item: its deterministic URL-derived ``NewsId``."""
    return str(item.id.root)


def iso_day(day: date) -> str:
    """Return the RFC 3339 UTC start of ``day``, the only shape a ``DATETIME`` index accepts."""
    return f"{day.isoformat()}T00:00:00Z"
