"""News items and the numbers extracted from them."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from numenews.models.ids import NewsId


class NewsItem(BaseModel):
    """One news article as it crosses the module boundaries.

    ``url`` is an opaque source URL: the five feeds of phase 2 spell URLs inconsistently, so the
    model does not insist on :class:`~pydantic.AnyHttpUrl` and never rejects an item over it.

    ``numbers`` and ``numerology_value`` are filled in by the extraction step (phase 4); before that
    they are ``()`` and ``None``. ``None`` is the explicit "not computed yet" — the reduced values
    never contain ``0``, so there is no magic number for it.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: NewsId
    title: str
    text: str
    source: str
    date: date
    url: str
    numbers: tuple[int, ...] = ()
    numerology_value: int | None = None


class ExtractedNumbers(BaseModel):
    """Numbers, symbols and provenance produced from one text.

    ``sources`` names the extraction strategies that contributed — ``("regex",)`` for the fallback
    of :func:`numenews.numerology.extract_numbers_regex`, ``("llm", "regex")`` when the agent ran
    first — deduplicated in first-seen order. It is **not** parallel to ``numbers``: labels describe
    the extraction, not individual values.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    numbers: tuple[int, ...] = ()
    sources: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
