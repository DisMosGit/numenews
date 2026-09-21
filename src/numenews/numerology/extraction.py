"""Regex extraction: the LLM-free fallback.

Phase 4 has an agent read a news item, but the pipeline must keep working when the model is down or
returns nonsense, so these functions find numbers, dates and symbols with regular expressions alone.
They are deliberately plain and predictable: matches come back in text order with duplicates kept,
and nothing is inferred beyond what the pattern says.

Two consequences of "nothing is inferred" are worth stating, because a caller can be surprised by
them. Numbers and dates overlap — the digits of a date are also numbers — so a caller that wants
dates uses :func:`extract_dates_regex` and ignores the values from :func:`extract_numbers_regex`.
And a thousands separator is not understood: ``"1,000"`` is the numbers ``1`` and ``0``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from types import MappingProxyType

_NUMBER_PATTERN = re.compile(r"\d+")

# `\b` on both sides keeps a longer digit run from being read as a date: `12026-09-21` is not one.
_ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DOTTED_DATE_PATTERN = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")

# The genitive form is the usual one in a sentence ("15 марта"); the nominative is accepted because
# a headline often writes it that way. Keys are casefolded, matching the `re.IGNORECASE` search.
_MONTHS: Mapping[str, int] = MappingProxyType(
    {
        "января": 1,
        "январь": 1,
        "февраля": 2,
        "февраль": 2,
        "марта": 3,
        "март": 3,
        "апреля": 4,
        "апрель": 4,
        "мая": 5,
        "май": 5,
        "июня": 6,
        "июнь": 6,
        "июля": 7,
        "июль": 7,
        "августа": 8,
        "август": 8,
        "сентября": 9,
        "сентябрь": 9,
        "октября": 10,
        "октябрь": 10,
        "ноября": 11,
        "ноябрь": 11,
        "декабря": 12,
        "декабрь": 12,
    }
)
# Longest name first, so "марта" is tried before "март".
_MONTH_DATE_PATTERN = re.compile(
    rf"\b(\d{{1,2}})\s+({'|'.join(sorted(_MONTHS, key=len, reverse=True))})(?:\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)


def _build_date(year: int, month: int, day: int) -> date | None:
    """Return the date, or ``None`` when the numbers do not describe a real calendar day."""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_numbers_regex(text: str) -> list[int]:
    """Return every run of ASCII digits as an integer, in text order.

    Leading zeros are normalised (``"007"`` is ``7``) and duplicates are kept. Digits that belong to
    a date are returned as well: this function is format-agnostic by design.

    Args:
        text: The text to scan.

    Returns:
        The numbers found, in order, duplicates included.
    """
    return [int(match.group()) for match in _NUMBER_PATTERN.finditer(text)]


def extract_dates_regex(text: str, *, today: date | None = None) -> list[date]:
    """Return the dates written in one of the supported formats, in text order.

    The formats are ISO (``2026-09-21``), dotted (``21.09.2026``) and a Russian month name
    (``15 марта``, optionally followed by a year). A date that does not exist — ``31.02.2026`` — is
    skipped rather than raising, because news text contains such typos and one bad date must not
    lose the others.

    A month-name date without a year is completed with ``today``'s year: the text does not say which
    year is meant, and the reading is about the news of the day. ``today`` is injectable so that a
    test (or a caller replaying an old batch) does not depend on the wall clock.

    Args:
        text: The text to scan.
        today: The date whose year completes a year-less match. Defaults to :func:`date.today`.

    Returns:
        The dates found, in order of their position in the text, duplicates included.
    """
    default_year = (today if today is not None else date.today()).year
    found: list[tuple[int, date]] = []

    for match in _ISO_DATE_PATTERN.finditer(text):
        parsed = _build_date(int(match[1]), int(match[2]), int(match[3]))
        if parsed is not None:
            found.append((match.start(), parsed))

    for match in _DOTTED_DATE_PATTERN.finditer(text):
        parsed = _build_date(int(match[3]), int(match[2]), int(match[1]))
        if parsed is not None:
            found.append((match.start(), parsed))

    for match in _MONTH_DATE_PATTERN.finditer(text):
        year = int(match[3]) if match[3] else default_year
        parsed = _build_date(year, _MONTHS[match[2].casefold()], int(match[1]))
        if parsed is not None:
            found.append((match.start(), parsed))

    found.sort(key=lambda item: item[0])

    return [parsed for _, parsed in found]


def extract_symbols(text: str, symbols: Sequence[str]) -> list[str]:
    """Return the requested symbols that occur in ``text``.

    Matching is case-insensitive and substring-based, so a multi-character symbol (``"AI"``) and an
    emoji work alike. The result keeps the order of ``symbols``, lists each one once, and never
    includes an empty symbol. Presence — not frequency — is the primitive: counting occurrences is
    the pattern layer's job, where symbols are compared across news items.

    Args:
        text: The text to search.
        symbols: The symbols to look for, in the order they should be reported.

    Returns:
        The symbols present in the text, deduplicated, ordered as in ``symbols``.
    """
    haystack = text.casefold()
    seen: set[str] = set()
    found: list[str] = []

    for symbol in symbols:
        folded = symbol.casefold()
        if not folded or folded in seen or folded not in haystack:
            continue
        seen.add(folded)
        found.append(symbol)

    return found
