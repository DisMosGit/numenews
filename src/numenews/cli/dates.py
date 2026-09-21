"""The ``--date`` grammar of the CLI: an absolute day or one relative to today.

``numenews forecast`` is the command a user reaches for on a day that is not today — the roadmap
asks for ``--date 2026-09-22``, ``--date tomorrow`` and ``--date +3d`` — so the grammar lives in one
place instead of in the command. The offset forms exist because a shell script should not have to
compute a date to ask about one.

Relative forms are resolved against a day the caller passes in, never against ``date.today()`` here:
the day comes from the pipeline's clock, which is the one clock the project reads (phases 1.6, 3.7
and 5.4 inject theirs for the same reason), so a test or a replayed run is independent of the wall
clock.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import typer

#: The accepted relative offsets, spelled with a lowercase ``d`` as the roadmap writes them.
_OFFSET = re.compile(r"^(?P<sign>[+-])(?P<days>\d+)d$")

#: Named days, resolved as an offset from the day the caller passes.
_NAMED: dict[str, int] = {"today": 0, "tomorrow": 1, "yesterday": -1}


def parse_day(value: str, *, today: date) -> date:
    """Return the calendar day ``value`` names, resolved against ``today``.

    Accepted forms:

    * ``YYYY-MM-DD`` — an absolute UTC day (``2026-09-22``);
    * ``today``, ``tomorrow``, ``yesterday``;
    * ``+Nd`` / ``-Nd`` — a whole-day offset (``+3d``, ``-2d``, ``+0d``).

    Surrounding whitespace and letter case are ignored.

    Args:
        value: The raw ``--date`` argument.
        today: The day relative forms are resolved against — the pipeline clock's today.

    Raises:
        typer.BadParameter: when ``value`` is none of the accepted forms. Click reports it as a
            usage error (exit code 2) with the message on stderr, which keeps stdout free of a
            partial document.
    """
    text = value.strip().lower()
    if text in _NAMED:
        return today + timedelta(days=_NAMED[text])
    offset = _OFFSET.match(text)
    if offset is not None:
        days = int(offset.group("days"))
        return today + timedelta(days=days if offset.group("sign") == "+" else -days)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        message = f"{value!r} is not a date: use YYYY-MM-DD, today, tomorrow, yesterday, +Nd or -Nd"
        raise typer.BadParameter(message, param_hint="--date") from error


__all__ = ["parse_day"]
