"""The one place in the pipeline that reads a clock.

Both ambient readings the pipeline needs go through this Protocol: the wall clock, which decides
which day a forecast is for and how an old-news period is labelled, and the monotonic clock, which
measures how long a step took. Tests hand in a clock whose readings they control, so a timing
assertion is exact and a window does not depend on the machine's date — the same reason
``extract_dates_regex(..., today=)`` and ``get_history(..., today=)`` take theirs (phases 1.6, 3.7).

``monotonic`` is deliberately separate from ``now``: a step's duration must not be disturbed by a
wall-clock adjustment, so the timing path never calls :meth:`Clock.now`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """The two readings the pipeline takes: the current instant and the elapsed time."""

    def now(self) -> datetime:
        """Return the current instant, in UTC."""
        ...

    def monotonic(self) -> float:
        """Return a monotonically increasing seconds value, for measuring a duration."""
        ...


class SystemClock:
    """The real clock: UTC wall time and :func:`time.monotonic`."""

    def now(self) -> datetime:
        """Return the current UTC instant."""
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """Return the process's monotonic seconds value."""
        return time.monotonic()
