"""Numeric constants shared by the numerology rules.

They live apart from the functions so that reduction (:mod:`numenews.numerology.reduction`) and the
master-number checks (:mod:`numenews.numerology.master`) agree on one definition instead of each
spelling out ``11``/``22``/``33``.
"""

from __future__ import annotations

MASTER_NUMBERS: frozenset[int] = frozenset({11, 22, 33})
# The master numbers: reduced no further, they keep their two-digit form.
REDUCED_NUMBERS: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9}) | MASTER_NUMBERS
# Every value reduction can produce; the invariant the property tests check against.
