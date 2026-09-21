"""Tests for the structlog setup: rendering, destination, level and correlation."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from numenews.config import Settings
from numenews.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
    new_request_id,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Leave the global logging configuration as the tests found it."""
    yield
    clear_request_context()
    configure_logging(Settings(environment="dev", log_level="INFO"))


def _lines(text: str) -> list[str]:
    """Return the non-empty lines of a captured stream."""
    return [line for line in text.splitlines() if line.strip()]


def test_prod_writes_one_json_object_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """`environment=prod` renders JSON on stderr and nothing on stdout."""
    configure_logging(Settings(environment="prod", log_level="INFO"))

    get_logger("numenews.test").info("smoke.event", number=11)

    captured = capsys.readouterr()
    assert captured.out == ""
    lines = _lines(captured.err)
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "smoke.event"
    assert record["number"] == 11
    assert record["level"] == "info"
    assert record["logger"] == "numenews.test"
    assert "timestamp" in record


def test_dev_writes_readable_text(capsys: pytest.CaptureFixture[str]) -> None:
    """`environment=dev` renders a console line instead of JSON."""
    configure_logging(Settings(environment="dev", log_level="INFO"))

    get_logger("numenews.test").info("smoke.event", number=11)

    lines = _lines(capsys.readouterr().err)
    assert len(lines) == 1
    assert "smoke.event" in lines[0]
    with pytest.raises(json.JSONDecodeError):
        json.loads(lines[0])


def test_level_filters_lower_records(capsys: pytest.CaptureFixture[str]) -> None:
    """Records below `log_level` never reach the stream."""
    configure_logging(Settings(environment="prod", log_level="WARNING"))
    logger = get_logger("numenews.test")

    logger.info("hidden.event")
    logger.warning("shown.event")

    lines = _lines(capsys.readouterr().err)
    assert [json.loads(line)["event"] for line in lines] == ["shown.event"]


def test_context_variables_are_merged(capsys: pytest.CaptureFixture[str]) -> None:
    """Bound correlation ids appear on every record in the context."""
    configure_logging(Settings(environment="prod", log_level="INFO"))
    bind_request_context(request_id="req-1", news_id="news-7")

    get_logger("numenews.test").info("smoke.event")

    clear_request_context()
    record = json.loads(_lines(capsys.readouterr().err)[0])
    assert record["request_id"] == "req-1"
    assert record["news_id"] == "news-7"


def test_context_variables_are_optional(capsys: pytest.CaptureFixture[str]) -> None:
    """A request id without a news id is still correlated."""
    configure_logging(Settings(environment="prod", log_level="INFO"))
    bind_request_context(request_id="req-2")

    get_logger("numenews.test").info("smoke.event")

    clear_request_context()
    record = json.loads(_lines(capsys.readouterr().err)[0])
    assert record["request_id"] == "req-2"
    assert "news_id" not in record


def test_standard_library_records_use_the_same_renderer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Foreign records (httpx, qdrant-client) are rendered exactly like structlog's."""
    configure_logging(Settings(environment="prod", log_level="INFO"))

    logging.getLogger("numenews.foreign").warning("from stdlib")

    lines = _lines(capsys.readouterr().err)
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "from stdlib"
    assert record["logger"] == "numenews.foreign"
    assert record["level"] == "warning"


def test_reconfiguration_replaces_handlers(capsys: pytest.CaptureFixture[str]) -> None:
    """Configuring twice switches the renderer without duplicating the handler."""
    configure_logging(Settings(environment="dev", log_level="INFO"))
    configure_logging(Settings(environment="prod", log_level="INFO"))

    get_logger("numenews.test").info("smoke.event")

    lines = _lines(capsys.readouterr().err)
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "smoke.event"


def test_new_request_id_is_unique_hex() -> None:
    """Request ids are unique and URL/JSON safe."""
    first = new_request_id()
    second = new_request_id()

    assert first != second
    assert len(first) == 32
    int(first, 16)  # hexadecimal or this raises
