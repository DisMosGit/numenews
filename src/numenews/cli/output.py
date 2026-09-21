"""The CLI's one writer: a Pydantic model and nothing else on stdout.

Every command answers with a model — ``Forecast``, ``CollectionQueryResult``, an ``ErrorReport`` —
and this module turns it into exactly one JSON document. The separation exists so the contract of
roadmap 7.2 ("stdout is JSON only") has a single place to live: no command builds a dict, calls
``print()`` or reaches for a Rich renderer, and a test can assert the shape without running a
command.

``sys.stdout.write`` rather than :func:`print`: the project bans ``print`` (``CONTRIBUTING.md``) so
that nothing accidental reaches stdout, and the two writes here are the sanctioned exception.
"""

from __future__ import annotations

import sys

from pydantic import BaseModel


def print_json(model: BaseModel, *, pretty: bool = True) -> None:
    """Write ``model`` to stdout as one JSON document, followed by a newline.

    Args:
        model: The command's answer. Any Pydantic model is accepted; the commands never pass a dict.
        pretty: Indent the document (``model_dump_json(indent=2)``) when true, which is the default
            of roadmap 7.2. ``--no-pretty`` writes the compact single-line form for ``jq -c`` and
            logs.
    """
    sys.stdout.write(model.model_dump_json(indent=2 if pretty else None))
    sys.stdout.write("\n")
