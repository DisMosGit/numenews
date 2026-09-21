# numenews — developer entry points.
#
# `make install` sets up the environment, `make dev` starts Qdrant, and
# `make lint && make test` is the gate every commit has to pass. `make test` ends with
# `make coverage-check`, which enforces the per-layer coverage floors of phase 10.4 (coverage.py has
# no per-path threshold, so each group is reported with its own `--fail-under`). `make mcp` serves
# the nine MCP tools over stdio (phase 6) and `make run` runs `numenews today` (phase 7), which needs
# Qdrant and an LLM endpoint. The ragas suite (phase 9) lives in `tests/eval` and runs in its own
# `.venv-eval`: ragas and `pydantic-ai` cannot share an environment (ADR 0013), so `make eval-env`
# builds it and `make test-eval` uses it.

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
PYTEST := uv run pytest
EVAL_PY := .venv-eval/bin/python

.PHONY: help install lint format test test-unit test-integration test-eval eval-env coverage coverage-check dev dev-down mcp run clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Create the environment from uv.lock
	uv sync --all-extras

lint: ## Ruff (lint + format check) and mypy strict
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy .

format: ## Apply ruff formatting and autofixes
	uv run ruff format .
	uv run ruff check --fix .

test: ## Unit and integration tests with coverage, then the per-layer floors
	$(PYTEST) tests/unit tests/integration --cov=numenews --cov-report=term-missing
	$(MAKE) --no-print-directory coverage-check

test-unit: ## Unit tests only
	$(PYTEST) tests/unit

test-integration: ## Integration tests (Qdrant :memory:, respx, mocked LLMs)
	$(PYTEST) tests/integration -m integration

test-eval: ## ragas evaluation in .venv-eval (needs an LLM endpoint; see docs/EVAL.md)
	@test -x $(EVAL_PY) || $(MAKE) eval-env
	RAGAS_DO_NOT_TRACK=true $(EVAL_PY) -m pytest tests/eval -v --run-eval

eval-env: ## Build .venv-eval: the locked runtime environment without pydantic-ai, plus ragas
	UV_PROJECT_ENVIRONMENT=.venv-eval uv sync --no-install-package pydantic-ai-slim
	uv pip install --python $(EVAL_PY) -r tests/eval/requirements-eval.txt

coverage: ## Tests with an HTML coverage report in docs/coverage.html
	$(PYTEST) tests/unit tests/integration --cov=numenews --cov-report=term-missing --cov-report=html:docs/coverage.html
	@echo "HTML report: docs/coverage.html"

# The per-layer floors of ROADMAP 10.4. `coverage report` reads the `.coverage` file the test
# targets just wrote, and `--format=total` keeps the output to the number being compared.
coverage-check: ## Enforce the per-layer coverage floors against the existing .coverage
	echo "numerology floor 95%:"
	uv run coverage report --include="src/numenews/numerology/*" --fail-under=95 --format=total
	echo "agents + pipeline floor 80%:"
	uv run coverage report --include="src/numenews/agents/*" --include="src/numenews/pipeline/*" --fail-under=80 --format=total
	echo "vector + news floor 70%:"
	uv run coverage report --include="src/numenews/vector/*" --include="src/numenews/news/*" --fail-under=70 --format=total

dev: ## Start Qdrant and wait until it is healthy
	$(COMPOSE) up -d --wait --wait-timeout 180

dev-down: ## Stop Qdrant, keep the volume
	$(COMPOSE) down

# `run` and `mcp` are silenced: make would otherwise echo the recipe into stdout and break
# the "stdout carries JSON (or JSON-RPC) and nothing else" contract.
mcp: ## Start the MCP server over stdio (nine tools, Ctrl-D to stop)
	@uv run python -m numenews.mcp

run: ## Run the sample one-shot CLI command (needs Qdrant and an LLM endpoint)
	@uv run numenews today

clean: ## Stop Qdrant, delete its volume and drop the local caches
	$(COMPOSE) down -v --remove-orphans
	rm -rf .mypy_cache .pytest_cache .ruff_cache .cache htmlcov .coverage docs/coverage.html .venv-eval
