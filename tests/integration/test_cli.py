"""The one-shot commands, driven through ``CliRunner`` (ROADMAP 7.3-7.9).

The commands are exercised the way a shell runs them — the real Typer application, real argument
parsing, real ``run_command`` — while the services behind them are the test's doubles: an in-memory
Qdrant with fake embedders, real agents driven by ``FunctionModel`` scripts, and a fake news
fetcher. ``build_context`` is replaced, which is the one seam the CLI grew for this; everything else
is the production path.

A run closes its context, so the in-memory store is closed when the command returns; assertions
about what a command did therefore read the JSON it printed (and, where useful, the counters of its
scripted agents) rather than the store afterwards.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from numenews.cli import main as cli_main
from numenews.cli.main import app
from numenews.config import Settings
from numenews.mcp.context import AppContext
from numenews.models import DateRange, Forecast, NewsId, NewsItem, Topic
from numenews.news.errors import NewsSourceError
from numenews.numerology import compute_numerology
from numenews.pipeline import NewsFetcher, Pipeline, reading_text
from numenews.vector import VectorStore, save_forecast, upsert_news

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)

pytestmark = pytest.mark.integration

runner = CliRunner()

TODAY = date(2026, 9, 21)


def _item(title: str, *, day: date = TODAY) -> NewsItem:
    """Return a news item with a deterministic id and just enough variety."""
    return NewsItem(
        id=NewsId(uuid4()),
        title=title,
        text=f"{title} body",
        source="example.com",
        date=day,
        url=f"https://example.test/{title.replace(' ', '-').lower()}",
    )


def _pipeline(
    store: VectorStore,
    *,
    fetcher: NewsFetcher | None = None,
) -> tuple[Pipeline, ModelCounter, ModelCounter]:
    """Return a pipeline over ``store`` plus the extract and forecast agent counters."""
    extract, extract_counter = extract_agent([11])
    pattern_reader, _ = pattern_agent([])
    forecaster, forecast_counter = forecast_agent()
    summarizer, _ = summarize_agent()
    pipeline = Pipeline(
        store=store,
        extract=extract,
        patterns=pattern_reader,
        forecast_agent=forecaster,
        summarizer=summarizer,
        fetcher=fetcher if fetcher is not None else fetcher_returning([]),
        clock=FrozenClock(),
    )
    return pipeline, extract_counter, forecast_counter


def _install(monkeypatch: pytest.MonkeyPatch, context: AppContext) -> None:
    """Make every command of the app use ``context`` instead of building one from settings."""
    monkeypatch.setattr(cli_main, "build_context", lambda settings: context)


def test_today_ingests_the_window_and_prints_the_reading(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.3: ``numenews today`` runs ingest + forecast and prints the ``Forecast``."""
    item = _item("eleven ministers resigned")
    pipeline, extract_counter, forecast_counter = _pipeline(
        vector_store, fetcher=fetcher_returning([item])
    )
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0, result.stderr
    reading = json.loads(result.stdout)
    assert reading["date"] == TODAY.isoformat()
    assert reading["dominant_number"] == compute_numerology(reading_text(item)).value
    assert reading["forecast"] == "День под знаком одиннадцати."
    assert extract_counter.calls == 1
    assert forecast_counter.calls == 1


def test_today_honours_the_topic_option(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--topic`` reaches the fetcher; the default is ``politics``."""
    seen: list[tuple[Any, Any]] = []
    pipeline, _, _ = _pipeline(vector_store, fetcher=fetcher_returning([], seen=seen))
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today", "--topic", "technology"])

    assert result.exit_code == 0, result.stderr
    assert seen[0][0].query == "technology"
    assert seen[0][1].start < seen[0][1].end


def test_today_defaults_to_politics(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bare DoD form ``numenews today`` works because the topic has a default."""
    seen: list[tuple[Any, Any]] = []
    pipeline, _, _ = _pipeline(vector_store, fetcher=fetcher_returning([], seen=seen))
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0, result.stderr
    assert seen[0][0].query == "politics"
    assert seen[0][1].end == TODAY
    assert seen[0][1].start == date(2026, 9, 15)


def test_today_answers_from_the_store_without_running_the_agent(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A day that was already read costs no model run: the command answers from Qdrant."""
    stored = _item("11th hour deal").model_copy(update={"numbers": (11,), "numerology_value": 11})
    upsert_news(vector_store, [stored])
    save_forecast(
        vector_store,
        Forecast(
            date=TODAY,
            dominant_number=11,
            master_active=True,
            forecast="День под знаком одиннадцати.",
            advice="Слушайте интуицию.",
        ),
    )
    pipeline, _, forecast_counter = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["dominant_number"] == 11
    assert forecast_counter.calls == 0


def test_no_pretty_writes_a_single_line(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.2: the compact form is one JSON document on one line."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["--no-pretty", "today"])

    assert result.exit_code == 0, result.stderr
    assert result.stdout.count("\n") == 1


def test_logs_go_to_stderr_and_stdout_stays_json(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.2: the payload parses as JSON while the progress lines land on stderr."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["date"] == TODAY.isoformat()
    assert "cli.invoked" in result.stderr
    assert "cli.command.complete" in result.stderr
    assert "cli.command.complete" not in result.stdout


def test_today_reports_a_news_failure_as_json(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.2/7.3: an expected failure is a JSON answer with exit code 1."""

    async def failing(topic: Topic, date_range: DateRange) -> list[NewsItem]:
        raise NewsSourceError("no news sources are configured")

    pipeline, _, _ = _pipeline(vector_store, fetcher=failing)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["kind"] == "NewsSourceError"
    assert "no news sources are configured" in report["error"]
    assert "cli.command.failed" in result.stderr


def test_today_reports_a_missing_llm_endpoint_as_json(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unconfigured endpoint surfaces as the documented error report, not a traceback."""
    context = AppContext(settings, store=vector_store)
    _install(monkeypatch, context)

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["kind"] == "LLMConfigurationError"
