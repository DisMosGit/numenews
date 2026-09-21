"""Tests for the dominant-number rule (ROADMAP 5.4).

The rule decides which number a day is read under, so its behaviour has to be predictable and
total: the most frequent value wins, a tie goes to the larger value, and an empty set says so with
the `0` sentinel instead of inventing a number. The property test states the invariants that must
hold for any input at all.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from numenews.models import DominantResult
from numenews.numerology import REDUCED_NUMBERS, dominant_number


def test_the_most_frequent_value_wins() -> None:
    """A day where seven articles say 11 is read under 11."""
    result = dominant_number([11, 11, 11, 7, 3])

    assert result == DominantResult(dominant_number=11, is_master=True, votes=3, considered=5)


def test_a_tie_goes_to_the_larger_value() -> None:
    """The rule is stated, not accidental: [7, 7, 11, 11] is a master day."""
    result = dominant_number([7, 7, 11, 11])

    assert result.dominant_number == 11
    assert result.is_master is True
    assert result.votes == 2
    assert result.considered == 4


def test_a_tie_between_plain_numbers_prefers_the_larger_one() -> None:
    """Two 3s and two 9s are a 9, whichever order the items arrived in."""
    assert dominant_number([3, 9, 3, 9]).dominant_number == 9
    assert dominant_number([9, 3, 9, 3]).dominant_number == 9


def test_a_single_value_is_its_own_dominant_number() -> None:
    """One article is enough to read the day; the vote count says how thin the evidence is."""
    result = dominant_number([7])

    assert result == DominantResult(dominant_number=7, is_master=False, votes=1, considered=1)


def test_an_empty_set_answers_the_sentinel_not_a_guess() -> None:
    """No news at all is `0`; the caller falls back to the date, because a reading needs one."""
    assert dominant_number([]) == DominantResult(
        dominant_number=0, is_master=False, votes=0, considered=0
    )


def test_a_master_number_is_reported_as_one() -> None:
    """`is_master` is what the forecast's `master_active` rests on."""
    assert dominant_number([22]).is_master is True
    assert dominant_number([4]).is_master is False


def test_a_not_computed_value_is_refused() -> None:
    """`0` means "no letters to sum"; letting it vote would make the sentinel an answer."""
    with pytest.raises(ValueError, match="reduced values"):
        dominant_number([7, 0])


@given(st.lists(st.sampled_from(sorted(REDUCED_NUMBERS)), min_size=1, max_size=50))
def test_the_dominant_number_is_always_a_reduced_value(values: list[int]) -> None:
    """The result is always something reduction could have produced."""
    assert dominant_number(values).dominant_number in REDUCED_NUMBERS


@given(st.lists(st.sampled_from(sorted(REDUCED_NUMBERS)), min_size=1, max_size=50))
def test_the_dominant_number_has_at_least_one_vote(values: list[int]) -> None:
    """The winner is the winner because it really occurred, and not more often than the input."""
    result = dominant_number(values)

    assert 1 <= result.votes <= result.considered
    assert result.considered == len(values)


@given(st.lists(st.sampled_from(sorted(REDUCED_NUMBERS)), min_size=2, max_size=50))
def test_shuffling_the_values_never_changes_the_answer(values: list[int]) -> None:
    """The dominant number is a property of the set, not of the order the feed returned it."""
    shuffled = list(reversed(values))

    assert dominant_number(values) == dominant_number(shuffled)
