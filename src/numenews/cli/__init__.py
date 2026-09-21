"""One-shot Typer commands.

stdout carries JSON and nothing else; logs and progress go to stderr. The Typer application lives in
:mod:`numenews.cli.main`, the command bodies in :mod:`numenews.cli.commands`, the single JSON writer
in :mod:`numenews.cli.output`, and the output models in :mod:`numenews.cli.schemas`.
``python -m numenews.cli`` and the installed ``numenews`` script both run the app.
"""
