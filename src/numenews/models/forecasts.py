"""The daily numerological forecast."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from numenews.models.patterns import Pattern


class Forecast(BaseModel):
    """One day's reading.

    ``dominant_number`` is the reduced value the day is read under, ``master_active`` says whether
    a master number (11, 22 or 33) participates, and ``patterns`` carries the connections the
    reading was built from. The field is named ``master_active`` after ``ROADMAP.md`` 1.1; the JSON
    sketch in the private design brief (``master_number_active``) is stale.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    date: date
    dominant_number: int
    master_active: bool
    patterns: tuple[Pattern, ...] = ()
    forecast: str
    advice: str
    warnings: tuple[str, ...] = ()
