# Code conventions

> Phase 10.2. What the code in this repository already looks like, written down so an agent extends it
> instead of inventing a second style. The hard prohibitions are in
> [`GUARDRAILS.md`](GUARDRAILS.md); the tools that check these conventions are in
> [`TOOLING.md`](TOOLING.md). `ROADMAP.md` remains the authoritative status.

## Naming

- **Modules and functions** are `snake_case`. A module owns one subject —
  `numerology/reduction.py`, `vector/collections.py` — and a function reads as the thing it returns
  or does: `reduce_number`, `build_news_filter`, `read_news_range`, never `do_`/`handle_`/`process_`.
- **Pydantic models and Protocols** are `PascalCase` (`NewsItem`, `NewsSource`, `VectorStore`).
  Exceptions are `PascalCase` too and end in `Error` (`AgentError`, `CollectionNotFoundError`).
- **Module constants** are `UPPER_SNAKE`: `MASTER_NUMBERS`, `REDUCED_NUMBERS`, `DOMAIN_ERRORS`. An
  implementation detail keeps an underscore (`_LOG_PROCESSORS`); a public one is exported through the
  package `__all__`.
- **Private helpers** take a single `_` prefix (`_digit_sum`, `_imported_numenews_modules`). The
  prefix marks a name as not part of the layer's surface; it is not a place to hide logic that a
  second module would copy.

## Types

Every function and method is fully annotated — parameters and return, including `-> None`. `mypy`
runs `strict = true` with the `pydantic.mypy` plugin (`init_typed = true`,
`init_forbid_extra = true`), so an untyped constructor is an error, not a warning.

- `Any` does not appear in the package. `ruff` selects the `ANN` rules; `ANN401` is the single
  ignored code, because `AGENTS.md` already bans `Any` outright and re-checking it at third-party
  boundaries only adds noise. When a type is genuinely unknown, write the narrowest honest type
  (`object`, a `Protocol`, a `TypeVar`) instead.
- `# type: ignore` is never bare. If one is unavoidable it carries a code and an inline reason on the
  same line, as the tests do:
  `settings.log_level = "DEBUG"  # type: ignore[misc]  # frozen model, mypy cannot see it`. The
  package itself currently has none.
- Modern syntax is the norm: `X | None`, `list[str]`, `type LogLevel = Literal[...]`, and
  keyword-only arguments after `*`.
- `from __future__ import annotations` opens every module that defines functions or classes, right
  after the module docstring. The only files without it are the package and test `__init__.py` markers
  that carry no annotated code.

## Docstrings

A public module, class and function has a docstring. The summary is one line in the imperative or the
descriptive present; the body says *why* the thing exists, not how its loop works. The repository
mixes Google-style sections with Sphinx roles in the same docstring:

```python
async def fetch_news(
    topic: Topic, date_range: DateRange, *, settings: Settings | None = None
) -> list[NewsItem]:
    """Fetch every configured source and return the merged result.

    Args:
        topic: What to search for.
        date_range: The inclusive UTC range to keep.
        settings: Configuration, including the news keys.

    Raises:
        NewsSourceError: when no source is configured at all.
    """
```

- `Args:`, `Returns:` and `Raises:` sections are indented four spaces under the section name, one
  entry per parameter, `name: description`.
- Cross-references use Sphinx roles — `:func:`, `:class:`, `:mod:`, `:meth:`, `:data:` — so an editor
  and a future build can resolve them. The `~` prefix shortens the rendered name, as in
  `` :class:`~numenews.vector.errors.VectorStoreError` ``.
- Module docstrings are the longest: they state the layer's promise and its boundary (see
  `src/numenews/numerology/__init__.py` and `src/numenews/mcp/errors.py`). A decision that needs more
  than a paragraph gets an ADR, and the docstring links to it.
- `#:` comments on module constants are the one accepted exception to "docstrings only";
  `DOMAIN_ERRORS` carries its contract that way.

## Comments

A comment explains **why**, never what the line below already says. The existing comments are the
model: `# 5xx is the server asking for another attempt; 4xx is not.` above
`self.retryable = status_code >= 500`, and the note in `logging.py` explaining why the logger cache
is disabled. A comment that restates the code is deleted in review, and a `TODO` without a task is
not committed.

## Pydantic v2

- Models that cross a boundary are `frozen=True, strict=True`:
  `model_config = ConfigDict(frozen=True, strict=True)`. Validation never coerces and an instance
  never changes, so a value that crossed a boundary stays what it says it is.
- Fields hold tuples, not lists (`numbers: tuple[int, ...] = ()`), so a frozen model stays hashable.
- `None` is the explicit "not computed yet" where a sentinel is needed (`NewsItem.numerology_value`);
  `0` is never used as one when `0` is a legal value elsewhere.
- camelCase wire fields are mapped with `Field(alias=...)` rather than renaming the Python attribute,
  which would trip `N815`.
- `Settings` subclasses `BaseSettings` with `env_ignore_empty=True`, `extra="ignore"`, `frozen=True`,
  and secrets are `SecretStr`. A new setting arrives with a working default and a line in
  `.env.example`.

## Exceptions

Each layer that can fail owns one `errors.py` and one base class: `news/errors.py`
(`NewsSourceError`), `vector/errors.py` (`VectorStoreError`), `agents/errors.py` (`AgentError`) and
`pipeline/errors.py` (`PipelineError`). Subclasses carry the data a caller needs to react
(`retryable`, `status_code`, `retry_after`, `agent`) on the exception itself, because whether another
attempt is worth making is a property of the failure, not of the call site.

The pure `numerology/` layer is the deliberate exception: it has no `errors.py` and raises the builtin
`ValueError` for an out-of-domain input, since there is no layer-specific context to carry.
`mcp/errors.py` is not a fifth hierarchy — it is the translation point that turns the four domain
bases into a `ToolError` the model can read, and leaves anything else to crash loudly.

## Package surface

A package re-exports its public surface from `__init__.py` and lists it in `__all__`, sorted and
unique (`numerology/__init__.py`, `models/__init__.py`). Callers import
`from numenews.models import NewsItem`, not `from numenews.models.news import NewsItem`. Submodules
stay importable for a caller that wants one piece on its own, and a test asserts that every name in
`__all__` resolves and stays sorted (`tests/unit/test_numerology_api.py`).

## Async

Asynchrony is a boundary concern. The interfaces (`mcp/`, `cli/`) and the pipeline are `async`; the
vector layer is synchronous, and the two are bridged only by `asyncio.to_thread` (`mcp/context.py`,
`cli/commands.py`, `Pipeline.run_blocking`) — never by blocking the event loop, and never by making
`vector/` async just to match its caller (ADR 0011). All HTTP goes through `httpx.AsyncClient`;
`time.sleep` is never called.

## Commits and tests

Commits follow [Conventional Commits](../../CONTRIBUTING.md) — `feat(scope): …`, `fix(scope): …`,
`docs: …`, `test: …` — with the scopes `numerology`, `news`, `embeddings`, `vector`, `agents`,
`pipeline`, `mcp`, `cli`, `models`, `docs`, `deps`. One atomic commit per `ROADMAP.md` task: the code,
its tests, its docs and the ticked task checkboxes land together, and the subject names the task. A
change that needs two subjects is two tasks, split in `ROADMAP.md` first.

Tests are part of the task, not a follow-up: a unit test for pure logic, an integration test for I/O.
The layer floors, the markers and the fixtures are in [`../TESTING.md`](../TESTING.md).
