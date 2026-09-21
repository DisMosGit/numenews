"""Tests for the public numerology API (ROADMAP 1.7).

Besides the readings themselves, these tests guard the two structural promises of the layer: the
package re-exports one coherent surface, and it does not drag the rest of `numenews` in with it.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import numenews.numerology as numerology
from numenews.models import NumerologyResult
from numenews.numerology import compute_numerology


def test_compute_numerology_reads_a_latin_text() -> None:
    """The roadmap example: `Sun rises` sums to 124 and reduces to 7."""
    assert compute_numerology("Sun rises") == NumerologyResult(
        text="Sun rises",
        gematria=124,
        value=7,
        is_master=False,
        breakdown=("gematria_simple = 124", "124 -> 1+2+4 = 7"),
    )


def test_compute_numerology_flags_a_master_number() -> None:
    """`k` is 11, so the value stays the master number and the breakdown says why."""
    result = compute_numerology("k")

    assert result.gematria == 11
    assert result.value == 11
    assert result.is_master is True
    assert result.breakdown == (
        "gematria_simple = 11",
        "11 is a master number and is not reduced further",
    )


def test_compute_numerology_reads_a_cyrillic_text() -> None:
    """`солнце` sums to 93 and reduces in two steps to 3."""
    result = compute_numerology("солнце")

    assert (result.gematria, result.value, result.is_master) == (93, 3, False)
    assert result.breakdown == ("gematria_simple = 93", "93 -> 9+3 = 12", "12 -> 1+2 = 3")


def test_compute_numerology_of_a_single_digit_sum_has_no_reduction_step() -> None:
    """The breakdown always starts with the sum, even when nothing needed reducing."""
    result = compute_numerology("g")

    assert result.gematria == 7
    assert result.breakdown == ("gematria_simple = 7",)


def test_compute_numerology_of_a_letterless_text_is_not_an_error() -> None:
    """A title of digits or emoji yields the documented zero reading."""
    expected = NumerologyResult(
        text="123 !!!",
        gematria=0,
        value=0,
        is_master=False,
        breakdown=("no letters to sum",),
    )

    assert compute_numerology("123 !!!") == expected
    assert compute_numerology("") == expected.model_copy(update={"text": ""})


def test_the_package_reexports_the_documented_surface() -> None:
    """Every name of `__all__` resolves through the package, sorted and unique."""
    assert list(numerology.__all__) == sorted(numerology.__all__)
    assert len(set(numerology.__all__)) == len(numerology.__all__)

    for name in numerology.__all__:
        assert hasattr(numerology, name), name


def test_the_package_reexports_the_constants_and_functions_of_the_layer() -> None:
    """The re-export is the same object as the module's, not a copy."""
    assert numerology.compute_numerology is compute_numerology
    assert numerology.reduce_number(29) in numerology.REDUCED_NUMBERS
    assert frozenset({11, 22, 33}) == numerology.MASTER_NUMBERS


def _imported_numenews_modules(statement: str) -> set[str]:
    """Return the `numenews` modules loaded after running `statement` in a fresh interpreter.

    A subprocess is needed because the rest of the suite imports ``numenews.mcp`` and
    ``numenews.cli``, which would otherwise pollute an in-process check.
    """
    program = (
        "import sys\n"
        f"{statement}\n"
        "print(' '.join(sorted(name for name in sys.modules if name.startswith('numenews'))))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    return set(completed.stdout.split())


@pytest.mark.parametrize(
    "banned",
    ["numenews.news", "numenews.vector", "numenews.agents", "numenews.mcp", "numenews.cli"],
)
def test_numerology_does_not_import_the_layers_above_it(banned: str) -> None:
    """AGENTS.md: the pure layer never imports news, vector, agents or mcp."""
    assert banned not in _imported_numenews_modules("import numenews.numerology")


def test_models_depend_on_nothing_beyond_the_package_root() -> None:
    """The shared vocabulary is a leaf, so `numerology` can safely depend on it."""
    imported = _imported_numenews_modules("import numenews.models")

    assert imported, "the subprocess reported no numenews module at all"
    assert all(name == "numenews" or name.startswith("numenews.models") for name in imported)
