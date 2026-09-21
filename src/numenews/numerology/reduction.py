"""Digit reduction: the arithmetic core of the numerology layer.

``reduce_number`` repeatedly sums the decimal digits of a positive integer until a single digit
remains, except that the master numbers 11, 22 and 33 stop the chain. ``reduce_date`` applies the
same rule to the digits of an ISO date. Nothing here reads a clock, a file or the network, so the
invariants hold for every input and are checked with property-based tests:

1. ``reduce_number(n)`` is in :data:`~numenews.numerology.constants.REDUCED_NUMBERS` for every
   ``n >= 1``;
2. reducing an already reduced value changes nothing (idempotence);
3. ``reduce_date(d)`` is in the same set for every :class:`~datetime.date`.

``n < 1`` is outside the domain and raises :class:`ValueError`. ``0`` is not a reduced value, and a
date always contributes at least one non-zero digit, so the rule never has to invent one.
"""

from __future__ import annotations

from datetime import date
from itertools import pairwise

from numenews.numerology.constants import MASTER_NUMBERS


def _digit_sum(n: int) -> int:
    """Return the sum of the decimal digits of ``n``."""
    return sum(int(digit) for digit in str(n))


def _digit_sum_chain(n: int) -> tuple[int, tuple[int, ...]]:
    """Return the reduced value of ``n`` and every value visited on the way.

    The chain starts at ``n`` and ends at the returned value, so ``_digit_sum_chain(124)`` is
    ``(7, (124, 7))`` and ``_digit_sum_chain(9)`` is ``(9, (9,))``. Both public functions render
    from this one chain, which keeps the stopping rule in a single place.

    Args:
        n: A positive integer.
    """
    visited = [n]
    while visited[-1] > 9 and visited[-1] not in MASTER_NUMBERS:
        visited.append(_digit_sum(visited[-1]))
    return visited[-1], tuple(visited)


def reduce_number(n: int) -> int:
    """Reduce a positive integer to ``1-9``, stopping at a master number.

    Args:
        n: The number to reduce; must be positive.

    Returns:
        The reduced value, always a member of
        :data:`~numenews.numerology.constants.REDUCED_NUMBERS`.

    Raises:
        ValueError: If ``n`` is zero or negative.
    """
    if n < 1:
        raise ValueError(f"reduce_number expects a positive integer, got {n}")
    return _digit_sum_chain(n)[0]


def reduction_steps(n: int) -> tuple[str, ...]:
    """Render the reduction of ``n`` as human-readable steps.

    Used for the ``breakdown`` of a
    :class:`~numenews.models.results.NumerologyResult`, so the caller does not have to
    re-implement the loop:

    * ``reduction_steps(7)`` is ``()`` — a single digit is already reduced;
    * ``reduction_steps(124)`` is ``("124 -> 1+2+4 = 7",)``;
    * ``reduction_steps(29)`` is
      ``("29 -> 2+9 = 11", "11 is a master number and is not reduced further")``.

    Args:
        n: The number to render; must be positive.

    Returns:
        The steps in order, one string per reduction plus, when the chain ends on a master number,
        a final note that it is not reduced further.

    Raises:
        ValueError: If ``n`` is zero or negative.
    """
    if n < 1:
        raise ValueError(f"reduction_steps expects a positive integer, got {n}")
    final, visited = _digit_sum_chain(n)
    steps = [
        f"{current} -> {'+'.join(str(digit) for digit in str(current))} = {following}"
        for current, following in pairwise(visited)
    ]
    if final in MASTER_NUMBERS:
        steps.append(f"{final} is a master number and is not reduced further")
    return tuple(steps)


def reduce_date(d: date) -> int:
    """Reduce the digits of an ISO date.

    The digits of ``d.isoformat()`` (``YYYY-MM-DD``) are summed and reduced, so ``2026-09-21`` is
    ``2+0+2+6+0+9+2+1 = 22`` — a master number. Zero padding never changes a digit sum, so the
    result does not depend on how the date is spelled.

    Args:
        d: The date to reduce.

    Returns:
        The reduced value, always a member of
        :data:`~numenews.numerology.constants.REDUCED_NUMBERS`.
    """
    digits = (int(character) for character in d.isoformat() if character.isdigit())
    return reduce_number(sum(digits))
