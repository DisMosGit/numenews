"""Results returned by the pure numerology layer.

`NumerologyResult` is what reading one text produces, `MasterCheckResult` the answer to the
master-number question, and `DominantResult` which value a *set* of values is read under — the rule
that decides a day's number from the numbers of that day's news.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class NumerologyResult(BaseModel):
    """The reading of one text.

    ``gematria`` is the raw letter sum, ``value`` the reduced number, ``is_master`` whether
    ``value`` is 11, 22 or 33, and ``breakdown`` the rendered calculation steps. A text without a
    single mapped letter has ``gematria == value == 0`` and ``is_master is False``.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    text: str
    gematria: int
    value: int
    is_master: bool
    breakdown: tuple[str, ...]


class MasterCheckResult(BaseModel):
    """Outcome of :func:`numenews.numerology.check_master_numbers`.

    ``master_numbers`` holds the distinct master numbers present, ascending; ``count`` counts every
    occurrence. Duplicates therefore appear once in the first field and once per occurrence in the
    second: ``check_master_numbers([11, 11])`` is ``(True, (11,), 2)``.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    has_master: bool
    master_numbers: tuple[int, ...]
    count: int


class DominantResult(BaseModel):
    """Which value a set of reduced values is read under.

    ``dominant_number`` is the value that occurs most often, ties going to the larger value;
    ``votes`` is how often it occurred and ``considered`` how many values were counted, so a caller
    can tell "eleven items agree" from "one item was all there was". ``dominant_number == 0`` is the
    sentinel for an empty set — the same idiom as :func:`~numenews.numerology.gematria_reduce` and
    :func:`~numenews.numerology.date_resonance`, because ``0`` is not a reduced value.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    dominant_number: int
    is_master: bool
    votes: int
    considered: int


class Digest(BaseModel):
    """A compressed reading of the news outside the pipeline's sliding window.

    Roadmap 5.5 keeps the recent window raw and summarises the older items into one numerological
    digest per period, so the memory of an earlier stretch survives in a sentence instead of a page
    of articles. ``period_start`` and ``period_end`` are the publication days the summary covers and
    are what identify the digest (there is no id of its own), ``summary`` is the prose, and
    ``numbers`` are the reduced values the period was read under, so a later query can find the
    digest of a master week without embedding a question about it.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    period_start: date
    period_end: date
    summary: str
    numbers: tuple[int, ...] = ()

    @model_validator(mode="after")
    def _reject_a_reversed_period(self) -> Self:
        """Refuse a period whose start lies after its end, as :class:`DateRange` does."""
        if self.period_start > self.period_end:
            raise ValueError("digest period_start must not be after period_end")
        return self
