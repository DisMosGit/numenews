"""Placeholder for the one-shot CLI.

The Typer application lands with phase 7 (``ROADMAP.md`` 7.1). Until then this module keeps
``make run`` honest: it writes a JSON object to stdout and exits successfully, so the
"stdout is JSON only" contract is checkable from the first commit. The progress note goes to
stderr through structlog.
"""

from __future__ import annotations

import json
import sys

from numenews.logging import configure_logging, get_logger, new_request_id


def main() -> int:
    """Write the placeholder payload to stdout and return the exit code."""
    configure_logging()
    get_logger("numenews.cli").info(
        "cli.placeholder",
        request_id=new_request_id(),
        detail="the one-shot commands land in ROADMAP.md phase 7",
    )
    payload = {
        "command": "numenews",
        "status": "not_implemented",
        "phase": 7,
        "message": "The one-shot CLI lands in ROADMAP.md phase 7.",
    }
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
