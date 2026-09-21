"""``python -m numenews.cli`` runs the Typer application.

Kept separate from :mod:`numenews.cli.main` so the installed script (``numenews``) and the module
runner take the same path: both end in the ``app`` object of :mod:`numenews.cli.main`. It mirrors
``numenews.mcp.__main__``.
"""

from __future__ import annotations

from numenews.cli.main import app

if __name__ == "__main__":  # pragma: no cover - exercised through `python -m`, not by pytest
    app()
