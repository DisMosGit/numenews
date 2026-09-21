# numenews — developer entry points.
#
# `make install` sets up the environment, `make dev` starts Qdrant, and
# `make lint && make test` is the gate every commit has to pass. `make mcp` serves the nine
# MCP tools over stdio (phase 6). The CLI and the ragas suite arrive in phases 7 and 9: until
# then `make run` and `make test-eval` exercise the placeholders in `src/numenews/*/__main__.py`.

SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
PYTEST := uv run pytest

.PHONY: help install lint format test test-unit test-integration test-eval coverage dev dev-down mcp run clean

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

test: ## Unit and integration tests with coverage
	$(PYTEST) tests/unit tests/integration --cov=numenews --cov-report=term-missing

test-unit: ## Unit tests only
	$(PYTEST) tests/unit

test-integration: ## Integration tests (Qdrant :memory:, respx, mocked LLMs)
	$(PYTEST) tests/integration -m integration

test-eval: ## ragas evaluation (phase 9; needs --run-eval)
	$(PYTEST) tests/eval -v --run-eval

coverage: ## Tests with an HTML coverage report in docs/coverage.html
	$(PYTEST) tests/unit tests/integration --cov=numenews --cov-report=term-missing --cov-report=html:docs/coverage.html
	@echo "HTML report: docs/coverage.html"

dev: ## Start Qdrant and wait until it is healthy
	$(COMPOSE) up -d --wait --wait-timeout 180

dev-down: ## Stop Qdrant, keep the volume
	$(COMPOSE) down

# `run` and `mcp` are silenced: make would otherwise echo the recipe into stdout and break
# the "stdout carries JSON (or JSON-RPC) and nothing else" contract.
mcp: ## Start the MCP server over stdio (nine tools, Ctrl-D to stop)
	@uv run python -m numenews.mcp

run: ## Run the sample one-shot CLI command (phase 7 placeholder)
	@uv run python -m numenews.cli

clean: ## Stop Qdrant, delete its volume and drop the local caches
	$(COMPOSE) down -v --remove-orphans
	rm -rf .mypy_cache .pytest_cache .ruff_cache .cache htmlcov .coverage docs/coverage.html
