"""Date resonance: which dates reduce to the same value.

Two dates resonate when their reduced values coincide, so ``date_resonance`` answers one pair and
``find_date_resonances`` reports the whole set. ``0`` is the "no resonance" answer: a reduced date
value is always at least 1, so it can never be a legitimate match.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from itertools import combinations

from numenews.numerology.reduction import reduce_date


def date_resonance(d1: date, d2: date) -> int:
    """Return the reduced value two dates share, or ``0`` when they do not resonate.

    Args:
        d1: The first date.
        d2: The second date.

    Returns:
        The shared reduced value, or ``0``. The comparison is symmetric, and a date always
        resonates with itself.
    """
    first = reduce_date(d1)

    return first if first == reduce_date(d2) else 0


def find_date_resonances(dates: Sequence[date]) -> list[tuple[date, date, int]]:
    """Return every resonant pair among ``dates``.

    Pairs are unordered and reported in input order (first the earlier element, then the later), so
    a date that appears twice forms as many pairs as it has partners and two identical dates always
    form one. The result is empty for fewer than two dates and for a set with no coinciding values.

    Args:
        dates: The dates to compare, in the order the caller wants the pairs reported.

    Returns:
        ``(earlier, later, shared_value)`` triples, ordered by the first date's position and then
        the second's.
    """
    reduced = [(day, reduce_date(day)) for day in dates]

    return [
        (first_day, second_day, first_value)
        for (first_day, first_value), (second_day, second_value) in combinations(reduced, 2)
        if first_value == second_value
    ]
