"""The tool functions that need no context, called directly (ROADMAP 6.4, 6.6).

Two of the nine tools are pure wrappers over :mod:`numenews.numerology`: they take no
``Context[AppContext]``, so they can be imported and called like the layer function they wrap. The
:mod:`numenews.mcp.server` test proves they are registered as tools; these tests prove they answer
what the roadmap says they answer.
"""

from __future__ import annotations

from numenews.mcp.tools import compute_numerology
from numenews.models import NumerologyResult


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
