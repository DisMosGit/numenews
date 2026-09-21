"""The tool functions that need no context, called directly (ROADMAP 6.4, 6.6).

Two of the nine tools are pure wrappers over :mod:`numenews.numerology`: they take no
``Context[AppContext]``, so they can be imported and called like the layer function they wrap. The
:mod:`numenews.mcp.server` test proves they are registered as tools; these tests prove they answer
what the roadmap says they answer.
"""

from __future__ import annotations

from numenews.mcp.tools import check_master_numbers, compute_numerology
from numenews.models import MasterCheckResult, NumerologyResult


def test_compute_numerology_returns_the_pure_reading() -> None:
    """The wrapper does not reimplement anything: gematria and value come from the layer."""
    result = compute_numerology("sun")

    assert isinstance(result, NumerologyResult)
    assert result.gematria == 54
    assert result.value == 9
    assert result.is_master is False
    assert result.breakdown[0] == "gematria_simple = 54"


def test_compute_numerology_keeps_a_master_number() -> None:
    """11, 22 and 33 are not reduced, which is the one rule worth an end-to-end assertion."""
    result = compute_numerology("k")

    assert result.value == 11
    assert result.is_master is True


def test_compute_numerology_reads_cyrillic_too() -> None:
    """The layer is bilingual; the tool exposes that unchanged."""
    assert compute_numerology("солнце").value == 3


def test_check_master_numbers_counts_every_occurrence() -> None:
    """ROADMAP 6.6: distinct master numbers live in one field, occurrences in the other."""
    result = check_master_numbers([11, 11, 7, 22])

    assert isinstance(result, MasterCheckResult)
    assert result.has_master is True
    assert result.master_numbers == (11, 22)
    assert result.count == 3


def test_check_master_numbers_finds_nothing_in_ordinary_numbers() -> None:
    """A list without 11, 22 or 33 reports the negative case, not an error."""
    result = check_master_numbers([1, 2, 3, 9])

    assert result.has_master is False
    assert result.master_numbers == ()
    assert result.count == 0


def test_check_master_numbers_accepts_an_empty_list() -> None:
    """An empty list is valid input; the call answers rather than failing."""
    assert check_master_numbers([]) == MasterCheckResult(
        has_master=False, master_numbers=(), count=0
    )
