"""Tests for the master-number checks (ROADMAP 1.3)."""

from __future__ import annotations

import pytest

from numenews.models import MasterCheckResult
from numenews.numerology.constants import MASTER_NUMBERS
from numenews.numerology.master import check_master_numbers, is_master


def test_master_numbers_are_11_22_and_33() -> None:
    """The set is exactly the three two-digit master numbers."""
    assert frozenset({11, 22, 33}) == MASTER_NUMBERS


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (11, True),
        (22, True),
        (33, True),
        (0, False),
        (1, False),
        (10, False),
        (12, False),
        (44, False),
        (-11, False),
    ],
)
def test_is_master(number: int, expected: bool) -> None:
    """Boundaries around the master numbers are not master numbers themselves."""
    assert is_master(number) is expected


def test_check_master_numbers_on_an_empty_sequence() -> None:
    """An empty reading is valid and reports nothing."""
    assert check_master_numbers([]) == MasterCheckResult(
        has_master=False, master_numbers=(), count=0
    )


def test_check_master_numbers_without_a_master() -> None:
    """Ordinary numbers are reported as absent, not as an error."""
    assert check_master_numbers([1, 2, 9]) == MasterCheckResult(
        has_master=False, master_numbers=(), count=0
    )


def test_check_master_numbers_counts_duplicates_once_and_per_occurrence() -> None:
    """`11, 11` is one distinct master number and two occurrences."""
    assert check_master_numbers([11, 11]) == MasterCheckResult(
        has_master=True, master_numbers=(11,), count=2
    )


def test_check_master_numbers_sorts_the_distinct_values() -> None:
    """The distinct values are ascending regardless of input order, and non-masters are ignored."""
    assert check_master_numbers([33, 7, 11, 22, 11]) == MasterCheckResult(
        has_master=True, master_numbers=(11, 22, 33), count=4
    )


def test_check_master_numbers_accepts_any_sequence() -> None:
    """The input is a `Sequence`, so a tuple works as well as a list."""
    assert check_master_numbers((11,)) == MasterCheckResult(
        has_master=True, master_numbers=(11,), count=1
    )
