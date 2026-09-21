# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project skeleton (phase 0): `src/` layout with the eight subpackages, the `uv` environment
  (`uv.lock`, Python 3.14) and `uv_build` packaging.
- Configuration via `pydantic-settings` (`Settings`, `get_settings`) with `.env.example`, and
  `structlog` logging: JSON on stderr in `prod`, readable in `dev`, correlation ids through
  `contextvars`.
- Tooling: ruff, `mypy --strict` with the pydantic plugin, pytest + pytest-asyncio, branch
  coverage, pre-commit hooks, and a self-documenting Makefile (`install`, `lint`, `format`,
  `test*`, `coverage`, `dev`, `dev-down`, `mcp`, `run`, `clean`).
- Qdrant 1.19.1 through Docker Compose, with a named volume, a healthcheck and the
  `qdrant_in_memory` test fixture.
- Test scaffolding: hermetic `settings` and `tmp_cache_dir` fixtures, `--run-eval` gating for the
  future ragas suite, and contract smoke tests for the CLI and MCP placeholders.
- Documentation: `docs/ARCHITECTURE.md`, `docs/NUMEROLOGY.md`, `docs/adr/` (ADR 0001 and the
  template) and `docs/agentic/AGENT_WORKFLOW.md`.
- Domain models (phase 1.1): `NewsItem`, `ExtractedNumbers`, `NumerologyResult`,
  `MasterCheckResult`, `Pattern`, `Forecast` and `NumberActivation`, plus the `NewsId`, `PatternId`
  and `ForecastId` wrappers — every one frozen and strict, in `numenews.models`.
- Pure numerology (phase 1.2–1.7): digit reduction with the 11/22/33 master stop, gematria for
  Latin (`A=1 … Z=26`) and the 33-letter Russian alphabet, date resonance, the regex extraction
  fallback (ISO dates, `DD.MM.YYYY`, Russian month names) and `compute_numerology` as the layer's
  entry point. The package imports only `numenews.models`, performs no I/O, and is 100% covered by
  unit and hypothesis property tests.
- Documentation for the layer: a complete `docs/NUMEROLOGY.md` and ADR 0002 recording the scope
  (reduction, master numbers, gematria, date resonance, regex fallback) and its limits.

### Changed
- `docs/ARCHITECTURE.md`: the `numerology` layer may import `models` (the result types it returns),
  and the "implemented so far" section now covers phases 0–1 (ADR 0002).

### Deprecated
-

### Removed
-

### Fixed
-

### Security
-

## [0.0.0] — 2026-01-01

### Added
- Initial commit. Repository bootstrap.
