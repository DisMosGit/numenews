"""Tests for the regex extraction fallback (ROADMAP 1.6).

The fallback must never raise on news text: an impossible date is skipped, a text without matches
returns an empty list, and the order of the input is preserved throughout.
"""

from __future__ import annotations

from datetime import date

from numenews.numerology.extraction import (
    extract_dates_regex,
    extract_numbers_regex,
    extract_symbols,
)


def test_extract_numbers_returns_them_in_order_with_duplicates() -> None:
    """Every digit run is a number, and the same number can appear twice."""
    assert extract_numbers_regex("The 7 and 7 again, plus 11") == [7, 7, 11]


def test_extract_numbers_normalises_leading_zeros() -> None:
    """`007` is the number 7, as `int` reads it."""
    assert extract_numbers_regex("007 agents, 0 cases") == [7, 0]


def test_extract_numbers_of_text_without_digits_is_empty() -> None:
    """No digits, no numbers — not an error."""
    assert extract_numbers_regex("no digits here") == []


def test_extract_numbers_splits_on_a_thousands_separator() -> None:
    """A separator is not understood: `1,000` is the numbers 1 and 0."""
    assert extract_numbers_regex("about 1,000 people") == [1, 0]


def test_extract_numbers_includes_the_digits_of_a_date() -> None:
    """The formats overlap by design; a caller that wants dates uses `extract_dates_regex`."""
    assert extract_numbers_regex("published 2026-09-21") == [2026, 9, 21]


def test_extract_dates_reads_iso_dates() -> None:
    """The ISO form is the canonical one."""
    assert extract_dates_regex("Published 2026-09-21 by GDELT.") == [date(2026, 9, 21)]


def test_extract_dates_reads_dotted_dates() -> None:
    """`DD.MM.YYYY` is the common European spelling."""
    assert extract_dates_regex("On 21.09.2026 the summit opened.") == [date(2026, 9, 21)]


def test_extract_dates_reads_month_name_dates_with_a_year() -> None:
    """`15 марта 2026` carries its own year."""
    assert extract_dates_regex("Подписано 15 марта 2026 года.") == [date(2026, 3, 15)]


def test_extract_dates_reads_month_name_dates_without_a_year() -> None:
    """A year-less date is completed from the injected `today`."""
    assert extract_dates_regex("Подписано 15 марта.", today=date(2026, 1, 1)) == [date(2026, 3, 15)]


def test_extract_dates_accepts_the_nominative_month() -> None:
    """A headline may write `5 Май 2027` instead of `5 мая 2027`."""
    assert extract_dates_regex("5 Май 2027") == [date(2027, 5, 5)]


def test_extract_dates_uses_the_current_year_by_default() -> None:
    """Without `today`, a year-less date resolves against the wall clock."""
    today = date.today()

    assert extract_dates_regex("15 марта") == [date(today.year, 3, 15)]


def test_extract_dates_skips_impossible_days() -> None:
    """Typos do not raise and do not hide the dates around them."""
    assert extract_dates_regex("31.02.2026 and 45.13.2026") == []
    assert extract_dates_regex("2026-13-45") == []
    assert extract_dates_regex("31.02.2026, but 01.03.2026 is real") == [date(2026, 3, 1)]


def test_extract_dates_checks_the_leap_year() -> None:
    """29 February exists in a leap year and is skipped otherwise."""
    assert extract_dates_regex("29 февраля", today=date(2024, 1, 1)) == [date(2024, 2, 29)]
    assert extract_dates_regex("29 февраля", today=date(2026, 1, 1)) == []


def test_extract_dates_keeps_text_order_across_formats() -> None:
    """All three patterns are merged by position in the text."""
    text = "2026-09-21, then 22.09.2026, then 23 сентября 2026"
    expected = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23)]

    assert extract_dates_regex(text) == expected


def test_extract_dates_does_not_read_a_longer_digit_run_as_a_date() -> None:
    """The word boundaries keep `12026-09-21` out of the result."""
    assert extract_dates_regex("12026-09-21") == []


def test_extract_dates_of_text_without_dates_is_empty() -> None:
    """No matches, no error."""
    assert extract_dates_regex("nothing to see") == []


def test_extract_symbols_returns_the_present_ones() -> None:
    """A symbol that does not occur is left out."""
    assert extract_symbols("Peace and love", ["love", "war"]) == ["love"]


def test_extract_symbols_matches_case_insensitively_but_returns_as_given() -> None:
    """The lookup folds case; the returned symbol is the caller's spelling."""
    assert extract_symbols("PEACE", ["peace"]) == ["peace"]
    assert extract_symbols("peace", ["Peace"]) == ["Peace"]


def test_extract_symbols_supports_multi_character_symbols_and_emoji() -> None:
    """A symbol is a substring, not necessarily a single character."""
    assert extract_symbols("AI is here", ["AI", "AGI"]) == ["AI"]
    assert extract_symbols("we want 🕊️ now", ["🕊️", "🔥"]) == ["🕊️"]


def test_extract_symbols_keeps_the_argument_order() -> None:
    """The caller decides the order, not the text."""
    assert extract_symbols("war and peace", ["peace", "war"]) == ["peace", "war"]


def test_extract_symbols_deduplicates_and_ignores_empty_entries() -> None:
    """Repeats in the argument list collapse, and an empty symbol matches nothing."""
    assert extract_symbols("war and peace", ["war", "war"]) == ["war"]
    assert extract_symbols("anything at all", [""]) == []


def test_extract_symbols_of_empty_input_is_empty() -> None:
    """An empty text or an empty symbol list yields nothing."""
    assert extract_symbols("", ["war"]) == []
    assert extract_symbols("war", []) == []
