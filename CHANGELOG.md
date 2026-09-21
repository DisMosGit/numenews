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

### Changed
-

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
