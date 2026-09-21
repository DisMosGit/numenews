"""Master numbers: 11, 22 and 33.

A master number is read as itself and not as its digit sum — the "11" of heightened intuition, not
the "2" of partnership. :func:`is_master` answers the single-value question;
:func:`check_master_numbers` reports on a whole sequence the way a reading needs it: whether one is
present, which distinct ones, and how often.
"""

from __future__ import annotations

from collections.abc import Sequence

from numenews.models.results import MasterCheckResult
from numenews.numerology.constants import MASTER_NUMBERS


def is_master(n: int) -> bool:
    """Return whether ``n`` is a master number (11, 22 or 33).

    Args:
        n: Any integer; values outside the set are simply ``False``.
    """
    return n in MASTER_NUMBERS


def check_master_numbers(numbers: Sequence[int]) -> MasterCheckResult:
    """Report the master numbers found in a sequence.

    Duplicates count once as a distinct value and once per occurrence, so ``[11, 11]`` yields
    ``MasterCheckResult(has_master=True, master_numbers=(11,), count=2)``. An empty sequence is a
    valid input — the reading simply found no activation — and never raises.

    Args:
        numbers: The numbers to inspect, in any order.

    Returns:
        Whether a master number is present, which distinct ones (ascending), and the number of
        occurrences.
    """
    present = sorted({number for number in numbers if number in MASTER_NUMBERS})
    return MasterCheckResult(
        has_master=bool(present),
        master_numbers=tuple(present),
        count=sum(1 for number in numbers if number in MASTER_NUMBERS),
    )
