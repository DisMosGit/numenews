"""The ``--date`` grammar of the CLI (ROADMAP 7.4).

``parse_day`` is pure: it resolves names and offsets against a day the caller passes, and refuses
anything else with a Typer usage error. These tests pin the accepted forms and the refusal.
"""

from __future__ import annotations

from datetime import date

import pytest
import typer

from numenews.cli.dates import parse_day

TODAY = date(2026, 9, 21)


def test_an_iso_date_is_taken_literally() -> None:
    """``--date 2026-09-22`` is the day it says, whatever today is."""
    assert parse_day("2026-09-22", today=TODAY) == date(2026, 9, 22)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("today", date(2026, 9, 21)),
        ("tomorrow", date(2026, 9, 22)),
        ("yesterday", date(2026, 9, 20)),
    ],
)
def test_named_days_are_offsets_from_today(value: str, expected: date) -> None:
    """ROADMAP 7.4: the three named days are relative to the injected today."""
    assert parse_day(value, today=TODAY) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("+3d", date(2026, 9, 24)),
        ("-2d", date(2026, 9, 19)),
        ("+0d", date(2026, 9, 21)),
        ("+10d", date(2026, 10, 1)),
    ],
)
def test_offsets_are_whole_days(value: str, expected: date) -> None:
    """ROADMAP 7.4: ``+3d`` and the other offset forms move whole days across month boundaries."""
    assert parse_day(value, today=TODAY) == expected


def test_the_basic_iso_form_works_too() -> None:
    """``date.fromisoformat`` accepts ``20260922``; the grammar does not fight it."""
    assert parse_day("20260922", today=TODAY) == date(2026, 9, 22)


def test_surrounding_space_and_case_is_ignored() -> None:
    """A shell-quoted argument often carries whitespace; ``Tomorrow`` is still tomorrow."""
    assert parse_day("  Tomorrow  ", today=TODAY) == date(2026, 9, 22)


@pytest.mark.parametrize("value", ["banana", "22-09-2026", "+3", "3d", "", "2026-13-40", "+1w"])
def test_an_unknown_form_is_a_usage_error(value: str) -> None:
    """Anything else is refused with a message that lists the grammar, not a stack trace."""
    with pytest.raises(typer.BadParameter, match="is not a date"):
        parse_day(value, today=TODAY)
