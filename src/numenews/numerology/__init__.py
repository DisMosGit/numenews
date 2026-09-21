"""Pure numerology: reduction, master numbers, gematria, date resonance, dominant number, regex.

The package is pure. It imports only the shared :mod:`numenews.models` vocabulary — never ``news``,
``vector``, ``agents``, ``pipeline`` or ``mcp`` — and performs no I/O, so its invariants hold
without any infrastructure and are checked with property-based tests. The only ambient value it
reads is the current year, and even that is injectable (``extract_dates_regex(..., today=...)``).

:func:`compute_numerology` is the entry point for reading one text and :func:`dominant_number` for
reading a set of reduced values; the rest of the surface is the pieces they are built from,
re-exported here so a caller does not have to know the module layout. ``reduction``, ``master``,
``gematria``, ``resonance``, ``dominant``, ``extraction`` and ``api`` stay importable for a caller
that wants one piece on its own.
"""

from __future__ import annotations

from numenews.numerology.api import compute_numerology
from numenews.numerology.constants import MASTER_NUMBERS, REDUCED_NUMBERS
from numenews.numerology.dominant import dominant_number
from numenews.numerology.extraction import (
    extract_dates_regex,
    extract_numbers_regex,
    extract_symbols,
)
from numenews.numerology.gematria import gematria_reduce, gematria_simple, normalize_text
from numenews.numerology.master import check_master_numbers, is_master
from numenews.numerology.reduction import reduce_date, reduce_number, reduction_steps
from numenews.numerology.resonance import date_resonance, find_date_resonances

__all__ = [
    "MASTER_NUMBERS",
    "REDUCED_NUMBERS",
    "check_master_numbers",
    "compute_numerology",
    "date_resonance",
    "dominant_number",
    "extract_dates_regex",
    "extract_numbers_regex",
    "extract_symbols",
    "find_date_resonances",
    "gematria_reduce",
    "gematria_simple",
    "is_master",
    "normalize_text",
    "reduce_date",
    "reduce_number",
    "reduction_steps",
]
