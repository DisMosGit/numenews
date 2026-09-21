"""Tests for gematria (ROADMAP 1.4)."""

from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from numenews.numerology.constants import REDUCED_NUMBERS
from numenews.numerology.gematria import (
    CYRILLIC_VALUES,
    LATIN_VALUES,
    gematria_reduce,
    gematria_simple,
    normalize_text,
)


def test_latin_table_runs_from_a_equals_1_to_z_equals_26() -> None:
    """The Latin table is the plain alphabet position."""
    assert LATIN_VALUES["a"] == 1
    assert LATIN_VALUES["m"] == 13
    assert LATIN_VALUES["z"] == 26
    assert len(LATIN_VALUES) == 26


def test_cyrillic_table_follows_the_russian_alphabet() -> None:
    """Cyrillic is the 33-letter alphabet by position, Ё included at 7."""
    assert CYRILLIC_VALUES["а"] == 1
    assert CYRILLIC_VALUES["е"] == 6
    assert CYRILLIC_VALUES["ё"] == 7
    assert CYRILLIC_VALUES["я"] == 33
    assert len(CYRILLIC_VALUES) == 33


def test_normalize_text_keeps_only_mapped_letters() -> None:
    """Digits, punctuation and whitespace are dropped; both scripts survive."""
    assert normalize_text("Sun rises! 42") == "sunrises"
    assert normalize_text("Солнце, 2026") == "солнце"
    assert normalize_text("!!! 123 🙂") == ""


def test_normalize_text_folds_case() -> None:
    """Upper- and lowercase spellings normalise to the same text."""
    assert normalize_text("SUN") == "sun"
    assert normalize_text("СОЛНЦЕ") == "солнце"


def test_gematria_simple_sums_latin_letters() -> None:
    """The roadmap example: `sun` is 19 + 21 + 14 = 54."""
    assert gematria_simple("sun") == 54
    assert gematria_simple("Sun") == 54
    assert gematria_simple("Sun rises") == 124


def test_gematria_simple_ignores_whitespace_and_punctuation() -> None:
    """Surrounding noise never changes the sum."""
    assert gematria_simple("  sun!!  ") == 54
    assert gematria_simple("s.u-n") == 54


def test_gematria_simple_sums_cyrillic_letters() -> None:
    """`солнце` is 19 + 16 + 13 + 15 + 24 + 6 = 93."""
    assert gematria_simple("солнце") == 93


def test_gematria_simple_keeps_the_two_scripts_apart() -> None:
    """A mixed text sums both alphabets; the scripts do not share letter values."""
    assert gematria_simple("sun солнце") == 54 + 93


def test_gematria_simple_of_letterless_text_is_zero() -> None:
    """A text with nothing to sum has the sum zero, not an error."""
    for text in ("", "12345", "!!!", "🙂", "日本語"):
        assert gematria_simple(text) == 0


def test_gematria_reduce_returns_the_reduced_sum() -> None:
    """The reduced value is the reduction of the sum, masters included."""
    assert gematria_reduce("sun") == 9
    assert gematria_reduce("k") == 11
    assert gematria_reduce("солнце") == 3


def test_gematria_reduce_of_letterless_text_is_the_zero_sentinel() -> None:
    """`reduce_number` starts at 1, so the gematria layer returns 0 itself."""
    assert gematria_reduce("") == 0
    assert gematria_reduce("007") == 0


def test_yo_is_a_letter_of_its_own() -> None:
    """Ё is not folded onto Е; the alphabet offset is positional, not transliterated."""
    assert gematria_simple("ё") == 7
    assert gematria_simple("е") == 6


def test_cyrillic_letters_outside_the_russian_alphabet_are_ignored() -> None:
    """Ukrainian Ї and Serbian Ђ are not part of the 33-letter table."""
    assert gematria_simple("Ї") == 0
    assert gematria_simple("ђ") == 0


def test_unknown_script_letters_are_ignored() -> None:
    """Greek and CJK letters have no value in this system."""
    assert gematria_simple("αβγ") == 0
    assert gematria_simple("日本") == 0


@given(st.text())
def test_gematria_simple_is_never_negative(text: str) -> None:
    """Invariant 3: a sum of letter values is non-negative for every text."""
    assert gematria_simple(text) >= 0


@given(st.text())
def test_gematria_reduce_is_always_an_allowed_value(text: str) -> None:
    """Invariant 4: a reduced gematria is 0 (no letters) or a reduced number."""
    reduced = gematria_reduce(text)

    assert reduced == 0 or reduced in REDUCED_NUMBERS


@given(st.text(alphabet=string.ascii_letters))
def test_case_does_not_change_the_sum(text: str) -> None:
    """Case folding makes the reading case-insensitive on both scripts."""
    assert gematria_simple(text) == gematria_simple(text.upper())
    assert gematria_simple(text) == gematria_simple(text.lower())


@pytest.mark.parametrize("letter", list("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"))
def test_every_cyrillic_letter_has_a_positive_value(letter: str) -> None:
    """No letter of the alphabet silently falls out of the table."""
    assert gematria_simple(letter) > 0
