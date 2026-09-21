"""Tests for date resonance (ROADMAP 1.5).

`2026-09-21`, `2026-09-12` and `2026-09-03` all have the digit sum 22, which makes them a convenient
resonant trio; `2026-09-22` reduces to 23 -> 5 and stays outside it.
"""

from __future__ import annotations

from datetime import date

from numenews.numerology.constants import REDUCED_NUMBERS
from numenews.numerology.resonance import date_resonance, find_date_resonances

RESONANT_22 = date(2026, 9, 21)
ALSO_22 = date(2026, 9, 12)
THIRD_22 = date(2026, 9, 3)
DIFFERENT = date(2026, 9, 22)


def test_date_resonance_returns_the_shared_value() -> None:
    """A match reports the reduced value itself, masters included."""
    assert date_resonance(RESONANT_22, ALSO_22) == 22
    assert date_resonance(ALSO_22, RESONANT_22) == 22


def test_date_resonance_is_zero_without_a_match() -> None:
    """`0` is the sentinel, because no reduced date value is ever zero."""
    assert date_resonance(RESONANT_22, DIFFERENT) == 0
    assert date_resonance(DIFFERENT, RESONANT_22) == 0


def test_a_date_resonates_with_itself() -> None:
    """Identity is resonance by definition."""
    assert date_resonance(RESONANT_22, RESONANT_22) == 22


def test_date_resonance_is_symmetric_across_a_month() -> None:
    """Over a whole month the answer never depends on the argument order."""
    days = [date(2026, 9, day) for day in range(1, 29)]

    for first in days:
        for second in days:
            forward = date_resonance(first, second)

            assert forward == date_resonance(second, first)
            assert forward == 0 or forward in REDUCED_NUMBERS


def test_find_date_resonances_returns_every_match_in_input_order() -> None:
    """Non-resonant dates are left out; the surviving pair keeps the input order."""
    assert find_date_resonances([RESONANT_22, DIFFERENT, ALSO_22]) == [(RESONANT_22, ALSO_22, 22)]


def test_three_mutually_resonant_dates_produce_three_pairs() -> None:
    """Every unordered pair is reported exactly once."""
    assert find_date_resonances([RESONANT_22, ALSO_22, THIRD_22]) == [
        (RESONANT_22, ALSO_22, 22),
        (RESONANT_22, THIRD_22, 22),
        (ALSO_22, THIRD_22, 22),
    ]


def test_identical_dates_form_a_pair() -> None:
    """A repeated date resonates with its own earlier occurrence."""
    assert find_date_resonances([RESONANT_22, RESONANT_22]) == [(RESONANT_22, RESONANT_22, 22)]


def test_find_date_resonances_handles_short_and_empty_input() -> None:
    """Fewer than two dates cannot form a pair."""
    assert find_date_resonances([]) == []
    assert find_date_resonances([RESONANT_22]) == []
    assert find_date_resonances([RESONANT_22, DIFFERENT]) == []
