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
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from numenews.cli import main as cli_main
from numenews.cli.main import app
from numenews.config import Settings
from numenews.mcp.context import AppContext
from numenews.models import (
    DateRange,
    Forecast,
    NewsId,
    NewsItem,
    NumberActivation,
    Pattern,
    PatternId,
    PatternType,
    Topic,
)
from numenews.news.errors import NewsSourceError
from numenews.numerology import compute_numerology
from numenews.pipeline import NewsFetcher, Pipeline, reading_text
from numenews.vector import (
    VectorStore,
    record_activation,
    save_forecast,
    save_pattern,
    upsert_news,
)
from numenews.vector.payloads import news_embedding_text, pattern_embedding_text

from ..unit.pipeline_fakes import (
    FrozenClock,
    ModelCounter,
    extract_agent,
    fetcher_returning,
    forecast_agent,
    pattern_agent,
    summarize_agent,
)
from .fakes import FakeEmbedder

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


def test_forecast_reads_the_requested_day(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.4: ``--date 2026-09-22`` reads that day, not today."""
    stored = _item("11th hour deal").model_copy(update={"numbers": (11,), "numerology_value": 11})
    upsert_news(vector_store, [stored])
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["forecast", "--date", "2026-09-22"])

    assert result.exit_code == 0, result.stderr
    reading = json.loads(result.stdout)
    assert reading["date"] == "2026-09-22"
    assert reading["dominant_number"] == 11


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("today", "2026-09-21"),
        ("tomorrow", "2026-09-22"),
        ("yesterday", "2026-09-20"),
        ("+3d", "2026-09-24"),
        ("-2d", "2026-09-19"),
    ],
)
def test_forecast_resolves_relative_dates_against_the_pipeline_clock(
    settings: Settings,
    vector_store: VectorStore,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: str,
) -> None:
    """ROADMAP 7.4: relative forms are resolved against the frozen clock, not the wall clock."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["forecast", "--date", value])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["date"] == expected


def test_forecast_defaults_to_today(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare ``numenews forecast`` is the reading for today."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["forecast"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["date"] == TODAY.isoformat()


def test_forecast_rejects_an_unknown_date_as_a_usage_error(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mistyped ``--date`` exits 2 with an empty stdout, so a pipe never sees a half-document."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["forecast", "--date", "banana"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "--date" in result.stderr


def _activation(number: int, *, day: date) -> NumberActivation:
    """Return one activation row for a number on a day."""
    return NumberActivation(
        number=number,
        date=day,
        news_id=NewsId(uuid4()),
        context=f"the {number} appeared here",
    )


def test_history_reads_the_window_newest_first(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.5: the activations of one number come back newest first, with the question."""
    today = datetime.now(UTC).date()
    record_activation(vector_store, _activation(11, day=today))
    record_activation(vector_store, _activation(11, day=today - timedelta(days=2)))
    record_activation(vector_store, _activation(7, day=today))
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["history", "--number", "11"])

    assert result.exit_code == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["number"] == 11
    assert report["days"] == 30
    assert [entry["date"] for entry in report["activations"]] == [
        today.isoformat(),
        (today - timedelta(days=2)).isoformat(),
    ]
    # The same rows folded per day (roadmap 8.2), newest day first.
    assert report["by_day"] == [
        {"date": today.isoformat(), "count": 1},
        {"date": (today - timedelta(days=2)).isoformat(), "count": 1},
    ]
    assert {entry["number"] for entry in report["activations"]} == {11}


def test_history_excludes_activations_outside_the_window(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--days 1`` is today: an activation from forty days ago is not in the answer."""
    today = datetime.now(UTC).date()
    record_activation(vector_store, _activation(11, day=today))
    record_activation(vector_store, _activation(11, day=today - timedelta(days=40)))
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["history", "--number", "11", "--days", "1"])

    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)["activations"]) == 1


def test_history_reads_a_wide_window(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--days 365`` reaches back a year, which is the read of the whole memory."""
    today = datetime.now(UTC).date()
    record_activation(vector_store, _activation(11, day=today - timedelta(days=40)))
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["history", "--number", "11", "--days", "365"])

    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)["activations"]) == 1


def test_history_without_the_collection_is_an_error_report(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store that never recorded an activation says so instead of crashing."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["history", "--number", "11"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["kind"] == "CollectionNotFoundError"


def test_history_refuses_a_window_without_days(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--days 0`` is a call-site bug the parser catches before the read."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["history", "--number", "11", "--days", "0"])

    assert result.exit_code == 2
    assert result.stdout == ""


def test_search_ranks_the_stored_news(
    settings: Settings,
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ROADMAP 7.6: ``search`` runs the hybrid news search and returns typed entities."""
    near = _item("budget deal signed")
    far = _item("weather report published")
    fake_base_embedder.register_axis(news_embedding_text(near), 0)
    fake_base_embedder.register_axis(news_embedding_text(far), 1)
    fake_base_embedder.register_axis("budget", 0)
    upsert_news(vector_store, [near, far])
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["search", "-q", "budget"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["collection"] == "news"
    assert payload["query"] == "budget"
    assert [item["title"] for item in payload["items"]] == [
        "budget deal signed",
        "weather report published",
    ]


def test_search_honours_the_limit(
    settings: Settings,
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--limit`` bounds the answer, which is what a pipeline into ``jq`` relies on."""
    first = _item("budget deal signed")
    second = _item("budget vote scheduled")
    fake_base_embedder.register_axis(news_embedding_text(first), 0)
    fake_base_embedder.register_axis(news_embedding_text(second), 0)
    fake_base_embedder.register_axis("budget", 0)
    upsert_news(vector_store, [first, second])
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["search", "-q", "budget", "--limit", "1"])

    assert result.exit_code == 0, result.stderr
    assert len(json.loads(result.stdout)["items"]) == 1


def test_search_can_ask_the_patterns_collection(
    settings: Settings,
    vector_store: VectorStore,
    fake_base_embedder: FakeEmbedder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--collection patterns`` finds saved interpretations instead of news items."""
    pattern = Pattern(
        id=PatternId(uuid4()),
        type="resonance",
        numbers=(11, 22),
        news_ids=(NewsId(uuid4()),),
        strength=0.8,
        interpretation="Числа 11 и 22 резонируют в новостях.",
    )
    fake_base_embedder.register_axis(pattern_embedding_text(pattern), 0)
    fake_base_embedder.register_axis("резонанс", 0)
    save_pattern(vector_store, pattern)
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["search", "-q", "резонанс", "--collection", "patterns"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["collection"] == "patterns"
    assert [item["id"] for item in payload["items"]] == [str(pattern.id.root)]
    assert payload["items"][0]["numbers"] == [11, 22]


def test_search_reports_a_missing_collection(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store that was never ingested is an error report, not a crash."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["search", "-q", "budget"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["kind"] == "CollectionNotFoundError"


def test_search_refuses_an_unknown_collection(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``--collection`` choice is the contract: anything else is a usage error."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["search", "-q", "budget", "--collection", "numbers"])

    assert result.exit_code == 2
    assert result.stdout == ""


def _pattern(
    interpretation: str,
    *,
    kind: PatternType = "resonance",
    strength: float = 0.5,
) -> Pattern:
    """Return a valid pattern with a fresh id, for seeding the collection."""
    return Pattern(
        id=PatternId(uuid4()),
        type=kind,
        numbers=(11,),
        news_ids=(NewsId(uuid4()),),
        strength=strength,
        interpretation=interpretation,
    )


def test_patterns_filters_by_type_and_strength(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROADMAP 7.7: ``--type`` and ``--min-strength`` select through the indexed fields."""
    save_pattern(vector_store, _pattern("strong resonance", strength=0.8))
    save_pattern(vector_store, _pattern("strong repetition", kind="repetition", strength=0.9))
    save_pattern(vector_store, _pattern("weak resonance", strength=0.4))
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(
        app,
        ["patterns", "--type", "resonance", "--min-strength", "0.7"],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["pattern_type"] == "resonance"
    assert payload["min_strength"] == 0.7
    assert [pattern["interpretation"] for pattern in payload["patterns"]] == ["strong resonance"]


def test_patterns_lists_everything_strongest_first(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no filters the command lists the collection, strongest first."""
    save_pattern(vector_store, _pattern("weak", strength=0.2))
    save_pattern(vector_store, _pattern("strong", strength=0.9))
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["patterns"])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["pattern_type"] is None
    assert payload["min_strength"] is None
    assert [pattern["interpretation"] for pattern in payload["patterns"]] == ["strong", "weak"]


def test_patterns_reports_a_missing_collection(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store without a stored pattern says so instead of crashing."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["patterns"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["kind"] == "CollectionNotFoundError"


def test_patterns_refuses_an_unknown_type(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The five pattern kinds are the contract; anything else is a usage error."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["patterns", "--type", "cosmic"])

    assert result.exit_code == 2
    assert result.stdout == ""


def test_patterns_refuses_a_strength_outside_the_unit_interval(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``strength`` lives in ``[0, 1]``; 1.5 is a usage error, not a filter."""
    _install(monkeypatch, AppContext(settings, store=vector_store))

    result = runner.invoke(app, ["patterns", "--min-strength", "1.5"])

    assert result.exit_code == 2
    assert result.stdout == ""


def _seed_history(store: VectorStore) -> None:
    """Give the store one recorded activation, so ``history`` has a collection to read."""
    record_activation(store, _activation(11, day=datetime.now(UTC).date()))


def _seed_news(store: VectorStore) -> None:
    """Give the store one news item, so ``search`` has a collection to search."""
    upsert_news(store, [_item("budget deal signed")])


def _seed_patterns(store: VectorStore) -> None:
    """Give the store one pattern, so ``patterns`` and ``search`` have a collection to read."""
    save_pattern(store, _pattern("strong resonance", strength=0.8))


#: Every command that answers with one JSON document, with the smallest seed each one needs. ``mcp``
#: is absent on purpose: its stdout is the JSON-RPC wire, not a command result (ADR 0005).
_SMOKE_CASES = [
    pytest.param(["today"], None, id="today"),
    pytest.param(["forecast"], None, id="forecast"),
    pytest.param(["history", "--number", "11"], _seed_history, id="history"),
    pytest.param(["search", "-q", "budget"], _seed_news, id="search-news"),
    pytest.param(
        ["search", "-q", "резонанс", "--collection", "patterns"],
        _seed_patterns,
        id="search-patterns",
    ),
    pytest.param(["patterns"], _seed_patterns, id="patterns"),
]


@pytest.mark.parametrize(("argv", "seed"), _SMOKE_CASES)
def test_every_command_answers_with_one_json_document(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    fake_base_embedder: FakeEmbedder,
    fake_small_embedder: FakeEmbedder,
    argv: list[str],
    seed: Callable[[VectorStore], None] | None,
) -> None:
    """ROADMAP 7.9: each command exits 0 and writes exactly one JSON document to stdout.

    The store is built per case because a run closes its context; the decoder check is what makes
    "exactly one" precise — nothing may follow the document but the newline ``print_json`` adds.
    """
    store = VectorStore.in_memory(base=fake_base_embedder, small=fake_small_embedder)
    if seed is not None:
        seed(store)
    pipeline, _, _ = _pipeline(store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, argv)

    assert result.exit_code == 0, result.stderr
    document, end = json.JSONDecoder().raw_decode(result.stdout)
    assert result.stdout[end:].strip() == ""
    assert document


def test_today_returns_exit_code_zero_and_the_dominant_number(
    settings: Settings, vector_store: VectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The phase DoD in test form: ``jq .dominant_number`` has an integer to read."""
    pipeline, _, _ = _pipeline(vector_store)
    _install(monkeypatch, AppContext(settings, pipeline=pipeline))

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0, result.stderr
    assert isinstance(json.loads(result.stdout)["dominant_number"], int)
