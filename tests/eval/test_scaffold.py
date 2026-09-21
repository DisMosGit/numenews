"""Placeholder for the ragas evaluation suite (phase 9).

It exists so that ``make test-eval`` is a valid target from the first Makefile commit. Without
``--run-eval`` the conftest skips it, so ``make test`` stays fast.
"""

from __future__ import annotations

import pytest


@pytest.mark.eval
def test_eval_suite_is_wired_up(request: pytest.FixtureRequest) -> None:
    """The eval marker is reachable once ``--run-eval`` is passed."""
    assert request.node.get_closest_marker("eval") is not None
