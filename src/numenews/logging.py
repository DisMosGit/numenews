"""structlog configuration.

stdout belongs to the CLI's JSON payload, so every log record goes to stderr: one JSON object
per line when ``environment == "prod"``, a compact console rendering in dev. Standard-library
records (``httpx``, ``qdrant-client``, uvicorn) pass through the same formatter, so the stream
has a single shape regardless of who logged.

Correlation identifiers travel in ``contextvars``, which makes them async-safe: binding a
request id once makes it appear on every record logged below it, without threading it through
call signatures.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import cast

import structlog
from structlog.stdlib import BoundLogger
from structlog.typing import Processor

from numenews.config import Settings, get_settings

# Processors shared by structlog-native and standard-library records, so a foreign record
# carries the same level, logger name, timestamp and exception rendering.
_LOG_PROCESSORS: list[Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging(settings: Settings | None = None) -> None:
    """Configure structlog and the standard-library root logger.

    Idempotent: the root handlers are replaced rather than stacked, so calling it again with
    different settings (as the tests do) fully switches the rendering.

    Args:
        settings: Configuration to read the level and the renderer from. Defaults to
            :func:`numenews.config.get_settings`.
    """
    resolved = settings if settings is not None else get_settings()
    level = logging.getLevelNamesMapping()[resolved.log_level]
    renderer: Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if resolved.environment == "prod"
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # What a record that came in through `logging` looks like before rendering.
        foreign_pre_chain=list(_LOG_PROCESSORS),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    structlog.configure(
        processors=[
            # Drop records below the configured level before they reach the formatter.
            structlog.stdlib.filter_by_level,
            *_LOG_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Loggers are re-assembled after a reconfiguration: the tests switch renderers, and a
        # cached processor chain would pin the first configuration into every logger already
        # used. Rendering one record is not a hot path worth a stale cache.
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> BoundLogger:
    """Return a bound logger.

    Logs are written to stderr; stdout stays reserved for CLI and MCP payloads.

    Args:
        name: Logger name, usually ``__name__``.
    """
    return cast("BoundLogger", structlog.get_logger(name))


def bind_request_context(*, request_id: str, news_id: str | None = None) -> None:
    """Bind correlation identifiers for every record logged in this context.

    Args:
        request_id: Correlation id for one command or tool call; see :func:`new_request_id`.
        news_id: Optional id of the news item the work is about.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id)
    if news_id is not None:
        structlog.contextvars.bind_contextvars(news_id=news_id)


def clear_request_context() -> None:
    """Drop every context variable bound by :func:`bind_request_context`."""
    structlog.contextvars.clear_contextvars()


def new_request_id() -> str:
    """Return a fresh correlation id for a CLI invocation or an MCP tool call."""
    return uuid.uuid4().hex
