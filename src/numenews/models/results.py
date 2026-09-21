"""Results returned by the pure numerology layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
