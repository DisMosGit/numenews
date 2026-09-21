"""The dominant number of a set: which value a day is read under.

A day's reading needs one number to stand for it, and the source of that number is the day's news:
whatever reduced value the articles of the day agree on. The rule is deliberately simple and
total — the most frequent value wins, and a tie goes to the larger value — so that a caller can
explain the choice to a reader instead of guessing at it. Two master numbers beat one plain 7, and
an 11 beats a 7 on an even split, which matches the weight the master numbers carry everywhere else
in the layer.

``0`` is the sentinel for "there was nothing to count": no reduced value is ever ``0``, so a caller
can tell an empty set from a real answer without a second field (the idiom of
:func:`~numenews.numerology.gematria_reduce` and :func:`~numenews.numerology.date_resonance`). A day
with no news at all falls back to ``reduce_date`` at the call site, because a reading always has a
number to rest on.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from numenews.models import DominantResult
from numenews.numerology.master import is_master


def dominant_number(values: Sequence[int]) -> DominantResult:
    """Return the value the set is read under: most frequent, ties to the larger value.

    Args:
        values: Reduced values — the ``numerology_value`` of a day's news items. An empty sequence
            is a valid input and yields the ``0`` sentinel.

    Returns:
        The dominant value with its vote count and the size of the set that was counted.

    Raises:
        ValueError: when a value is not a reduced number (``1-9``, ``11``, ``22``, ``33``). A ``0``
            from a text without letters is "not computed", and letting it vote would make the
            sentinel an answer.
    """
    for value in values:
        if value < 1:
            raise ValueError(f"dominant_number expects reduced values, got {value}")
    if not values:
        return DominantResult(dominant_number=0, is_master=False, votes=0, considered=0)

    # `Counter.most_common` orders equal counts by first appearance, which is not a rule a reader
    # could predict; sorting by (count, value) descending makes the tie-break explicit.
    counts = Counter(values)
    winner, votes = max(counts.items(), key=lambda item: (item[1], item[0]))
    return DominantResult(
        dominant_number=winner,
        is_master=is_master(winner),
        votes=votes,
        considered=len(values),
    )
