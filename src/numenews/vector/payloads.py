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
from datetime import UTC, date, datetime, time
from uuid import NAMESPACE_URL, uuid5

from numenews.models import Digest, Forecast, NewsItem, NumberActivation, Pattern
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
    return NewsItem.model_validate_json(json.dumps(_restore_day(dict(payload))))


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


def activation_payload(activation: NumberActivation) -> dict[str, object]:
    """Return the payload of one number activation.

    The same shape serves ``numbers`` (vector-backed, the semantic index over contexts) and
    ``number_history`` (payload only, the exact log); the collections differ in what they can be
    asked, not in what they store. ``numerology_value`` is dropped when it is ``None`` — the rule of
    this module, so "not computed" stays unindexed rather than becoming an indexed null.
    """
    payload: dict[str, object] = dict(activation.model_dump(mode="json", exclude_none=True))
    payload["date"] = iso_day(activation.date)
    return payload


def activation_from_payload(payload: Mapping[str, object]) -> NumberActivation:
    """Rebuild a :class:`~numenews.models.NumberActivation` from a stored payload."""
    return NumberActivation.model_validate_json(json.dumps(_restore_day(dict(payload))))


def activation_embedding_text(activation: NumberActivation) -> str:
    """Return the text embedded for one activation: the snippet, or the number itself.

    The context is what makes an activation findable by meaning ("финансы", "выборы"); when the
    extractor had no snippet, the number is the only text there is, and it must not be empty.
    """
    return activation.context.strip() or str(activation.number)


def activation_point_id(activation: NumberActivation) -> str:
    """Return one point id per ``(news item, number)`` pair.

    A news item contributes a number once — ``ExtractedNumbers.numbers`` is already de-duplicated —
    so re-ingesting the same article overwrites its activations instead of piling them up.
    """
    key = f"numenews:activation:{activation.news_id.root}:{activation.number}"
    return str(uuid5(NAMESPACE_URL, key))


def iso_day(day: date) -> str:
    """Return the RFC 3339 UTC start of ``day``, the only shape a ``DATETIME`` index accepts."""
    return f"{day.isoformat()}T00:00:00Z"


def day_start(day: date) -> datetime:
    """Return the UTC midnight that opens ``day``, which is what a filter compares a date against.

    The same instant :func:`iso_day` writes: payloads carry the string form, filters carry the
    ``datetime`` Qdrant's own model stores, and both come from here so they cannot drift.
    """
    return datetime.combine(day, time.min, tzinfo=UTC)


def pattern_payload(pattern: Pattern) -> dict[str, object]:
    """Return the payload of one pattern.

    No date normalization is needed here: ``discovered_at`` is a ``datetime``, so its own JSON form
    is already the RFC 3339 timestamp the ``discovered_at`` index expects.
    """
    return dict(pattern.model_dump(mode="json", exclude_none=True))


def pattern_from_payload(payload: Mapping[str, object]) -> Pattern:
    """Rebuild a :class:`~numenews.models.Pattern` from a stored payload."""
    return Pattern.model_validate_json(json.dumps(dict(payload)))


def pattern_embedding_text(pattern: Pattern) -> str:
    """Return the text embedded for one pattern: its interpretation.

    An interpretation is the pattern's meaning in words, which is what a later query ("master
    numbers around money") should match. When it is blank, the type and the numbers are the only
    content left and are used instead of an empty string.
    """
    interpretation = pattern.interpretation.strip()
    if interpretation:
        return interpretation
    numbers = " ".join(str(number) for number in pattern.numbers)
    return f"{pattern.type} {numbers}".strip()


def pattern_point_id(pattern: Pattern) -> str:
    """Return the point id of one pattern: its own ``PatternId``."""
    return str(pattern.id.root)


def forecast_payload(forecast: Forecast) -> dict[str, object]:
    """Return the payload of one forecast.

    The nested patterns keep their own timestamps, which are already RFC 3339; only the outer
    ``date`` is a calendar day and needs the same normalization as a news item's.
    """
    payload: dict[str, object] = dict(forecast.model_dump(mode="json", exclude_none=True))
    payload["date"] = iso_day(forecast.date)
    return payload


def forecast_from_payload(payload: Mapping[str, object]) -> Forecast:
    """Rebuild a :class:`~numenews.models.Forecast` from a stored payload."""
    return Forecast.model_validate_json(json.dumps(_restore_day(dict(payload))))


def forecast_embedding_text(forecast: Forecast) -> str:
    """Return the text embedded for one forecast: its reading and its advice.

    Similarity between forecasts is what would let a later run ask "was there a day like this",
    so the text is the interpretive part, not the numbers that are filtered on instead.
    """
    return f"{forecast.forecast}\n\n{forecast.advice}".strip() or str(forecast.dominant_number)


def forecast_point_id(day: date) -> str:
    """Return the point id of one day's forecast.

    ``Forecast`` carries no id of its own — a day has exactly one reading — so the date is the key,
    and saving a forecast twice for the same day overwrites instead of duplicating.
    """
    return str(uuid5(NAMESPACE_URL, f"numenews:forecast:{day.isoformat()}"))


def digest_payload(digest: Digest) -> dict[str, object]:
    """Return the payload of one digest.

    Both ends of the period are stored in the same RFC 3339 shape as every other day in the store,
    because the two fields are indexed as ``DATETIME``.
    """
    payload: dict[str, object] = dict(digest.model_dump(mode="json", exclude_none=True))
    payload["period_start"] = iso_day(digest.period_start)
    payload["period_end"] = iso_day(digest.period_end)
    return payload


def digest_from_payload(payload: Mapping[str, object]) -> Digest:
    """Rebuild a :class:`~numenews.models.Digest` from a stored payload."""
    restored = dict(payload)
    for key in ("period_start", "period_end"):
        value = restored.get(key)
        if isinstance(value, str):
            restored[key] = value[:10]
    return Digest.model_validate_json(json.dumps(restored))


def digest_embedding_text(digest: Digest) -> str:
    """Return the text embedded for one digest: its summary.

    A digest is only worth storing if a later question can find it, and the question is about what
    the period was like — so the summary is what is embedded. A blank summary cannot be written
    (``DigestDraft.summary`` has ``min_length=1``), and the numbers are the only text left if one
    ever is, because an empty string would map every digest to the same point.
    """
    return digest.summary.strip() or " ".join(str(number) for number in digest.numbers)


def digest_point_id(start: date, end: date) -> str:
    """Return the point id of one digest: the period it covers.

    A period has one summary, so re-summarising the same range replaces the point instead of adding
    a second copy of it.
    """
    return str(uuid5(NAMESPACE_URL, f"numenews:digest:{start.isoformat()}:{end.isoformat()}"))


def _restore_day(payload: dict[str, object]) -> dict[str, object]:
    """Turn a stored RFC 3339 day back into the ``YYYY-MM-DD`` the strict models expect."""
    date_value = payload.get("date")
    if isinstance(date_value, str):
        payload["date"] = date_value[:10]
    return payload
