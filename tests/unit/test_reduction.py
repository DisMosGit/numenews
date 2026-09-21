"""Tests for digit reduction (ROADMAP 1.2).

The table cases pin the behaviour; the property tests check the invariants that no table can cover
completely — every positive integer reduces into the allowed set and reduction is idempotent.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numenews.numerology.constants import REDUCED_NUMBERS
from numenews.numerology.reduction import reduce_date, reduce_number, reduction_steps

POSITIVE_INTS = st.integers(min_value=1, max_value=10**12)


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, 1),
        (9, 9),
        (10, 1),
        (19, 1),
        (29, 11),
        (38, 11),
        (49, 4),
        (99, 9),
        (100, 1),
        (1998, 9),
        (99999, 9),
        (999999, 9),
        (11, 11),
        (22, 22),
        (33, 33),
    ],
)
def test_reduce_number_returns_the_expected_value(number: int, expected: int) -> None:
    """The worked examples from `docs/NUMEROLOGY.md` and the master-number identities."""
    assert reduce_number(number) == expected


@given(POSITIVE_INTS)
@settings(max_examples=1000)
def test_reduce_number_stays_in_the_reduced_set(number: int) -> None:
    """Invariant 1: a reduced value is always `1-9` or a master number."""
    assert reduce_number(number) in REDUCED_NUMBERS


@given(POSITIVE_INTS)
@settings(max_examples=1000)
def test_reduce_number_is_idempotent(number: int) -> None:
    """Invariant 2: reducing an already reduced value changes nothing."""
    once = reduce_number(number)

    assert reduce_number(once) == once


@pytest.mark.parametrize("number", [0, -1, -33])
def test_reduce_number_rejects_non_positive_input(number: int) -> None:
    """`0` and negatives are outside the domain, so they raise instead of returning `0`."""
    with pytest.raises(ValueError, match="positive integer"):
        reduce_number(number)


@given(st.dates())
def test_reduce_date_stays_in_the_reduced_set(day: date) -> None:
    """Invariant 3: every ISO date reduces into the same allowed set."""
    assert reduce_date(day) in REDUCED_NUMBERS


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 21), 22),
        (date(1998, 12, 31), 7),
        (date(2030, 1, 1), 7),
        (date(1, 1, 1), 3),
    ],
)
def test_reduce_date_sums_the_iso_digits(day: date, expected: int) -> None:
    """The date is read as its ISO digits, zero padding included."""
    assert reduce_date(day) == expected


def test_reduce_date_can_stop_on_a_master_number() -> None:
    """A date whose digit sum is a master number is not reduced further."""
    assert reduce_date(date(2026, 9, 21)) == 22


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (7, ()),
        (11, ("11 is a master number and is not reduced further",)),
        (124, ("124 -> 1+2+4 = 7",)),
        (29, ("29 -> 2+9 = 11", "11 is a master number and is not reduced further")),
        (999999, ("999999 -> 9+9+9+9+9+9 = 54", "54 -> 5+4 = 9")),
    ],
)
def test_reduction_steps_render_the_chain(number: int, expected: tuple[str, ...]) -> None:
    """The rendered steps match the reduction that `reduce_number` performs."""
    assert reduction_steps(number) == expected


def test_reduction_steps_reject_non_positive_input() -> None:
    """The steps share the domain rule of `reduce_number`."""
    with pytest.raises(ValueError, match="positive integer"):
        reduction_steps(0)
