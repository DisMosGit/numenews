"""The CLI's output contract: one JSON document on stdout, nothing else (ROADMAP 7.2).

``print_json`` is the single writer, so these tests pin the shape a pipe sees: a model becomes a
JSON document, pretty by default, compact on request, and non-ASCII text survives unescaped. The
error report a failed command prints is pinned here too, because it is part of the same contract.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from numenews.cli.output import print_json
from numenews.cli.schemas import ErrorReport


class Sample(BaseModel):
    """A stand-in command answer with non-ASCII text, so the encoding is exercised."""

    model_config = ConfigDict(frozen=True)

    text: str
    value: int


def test_pretty_output_is_indented_json(capsys: pytest.CaptureFixture[str]) -> None:
    """The default form is human-readable and still one document."""
    print_json(Sample(text="Число 11", value=11))

    written = capsys.readouterr().out
    assert json.loads(written) == {"text": "Число 11", "value": 11}
    assert '\n  "text"' in written


def test_compact_output_is_a_single_line(capsys: pytest.CaptureFixture[str]) -> None:
    """``--no-pretty`` is what a log or ``jq -c`` wants: one line, one document."""
    print_json(Sample(text="Число 11", value=11), pretty=False)

    written = capsys.readouterr().out
    assert written.count("\n") == 1
    assert json.loads(written)["text"] == "Число 11"


def test_non_ascii_text_is_not_escaped(capsys: pytest.CaptureFixture[str]) -> None:
    """A Russian forecast reads as Russian in the pipe, not as ``\\u0414`` escapes."""
    print_json(Sample(text="День под знаком одиннадцати.", value=11), pretty=False)

    assert "День под знаком одиннадцати." in capsys.readouterr().out


def test_the_document_ends_with_a_newline(capsys: pytest.CaptureFixture[str]) -> None:
    """A trailing newline keeps the output line-oriented for shells and logs."""
    print_json(Sample(text="sun", value=9))

    assert capsys.readouterr().out.endswith("}\n")


def test_an_error_report_is_json_too(capsys: pytest.CaptureFixture[str]) -> None:
    """A failure is an answer: the report carries the message and the exception kind."""
    print_json(ErrorReport(kind="VectorStoreError", error="Qdrant is not reachable"))

    assert json.loads(capsys.readouterr().out) == {
        "error": "Qdrant is not reachable",
        "kind": "VectorStoreError",
    }
