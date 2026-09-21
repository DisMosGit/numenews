# Evaluating agent output

> Phase 10.2. How a human reviews work an agent produced in this repository: what to diff, which
> commands to re-run, and what counts as evidence. The prompts that ask for the work are in
> [`PROMPTING_PLAYBOOK.md`](PROMPTING_PLAYBOOK.md); the prohibitions a review enforces are in
> [`GUARDRAILS.md`](GUARDRAILS.md).

The review answers one question: **does the change satisfy the task's Definition of Done, and can I
see that it does?** A convincing summary is not an answer. Everything below is something the reviewer
reproduces, not something the agent reports.

## Start from the Definition of Done

Open `ROADMAP.md` at the task and turn its DoD into a checklist. Then diff the working tree against
the base revision and walk the checklist item by item. If an item is not observable from the diff or a
command, it is not done; "the code looks right" closes nothing. Record the deviations the agent
reported and decide whether each is legitimate — a documented deviation next to the task is fine, a
silent one is a finding.

## Re-run the verification commands yourself

Never accept an agent's transcript of a command. Run the same commands and read the output:

```bash
make lint           # ruff check, ruff format --check, mypy --strict
make test           # tests/unit + tests/integration, coverage, then the per-layer floors
make coverage       # the same run with an HTML report in docs/coverage.html
make coverage-check # re-checks the floors of ROADMAP 10.4 against the existing .coverage
make test-eval      # ragas metrics in .venv-eval; needs an LLM endpoint (docs/EVAL.md)
```

The per-layer coverage floors (numerology ≥ 95 %, `pipeline/` + `agents/` ≥ 80 %, `vector/` + `news/`
≥ 70 %) are enforced by `make coverage-check`, which `make test` runs at the end; coverage.py has no
per-path threshold, so each group gets its own `--fail-under`. The dated numbers are in
[`../coverage_report.md`](../coverage_report.md) and the levels are described in
[`../TESTING.md`](../TESTING.md). Do not report a gate you did not run.

A task that touches an interface also needs its live check: `make dev` plus a Qdrant health probe for
the vector layer, `uv run numenews <command> | jq .` for the CLI, the stdio handshake for MCP
(`tests/integration/test_mcp_stdio.py`).

## Check that no test got weaker

Diff `tests/` line by line; this is where a green suite can hide a broken change.

- A removed or renamed test, a deleted assertion, a loosened comparison (`==` to `in`, an `assert`
  to a comment), a new `pytest.mark.skip`/`xfail` without a reason, or a narrowed parametrization.
- An `assert` replaced by a `print` or a log line "for debugging".
- A test that now mocks the very thing it used to exercise, so it can no longer fail.
- A coverage `# pragma: no cover` added to a branch that used to be tested.

An intentional change to a test is allowed only when the decision it encoded was superseded, and then
the commit message carries the reason and an ADR carries it if the decision was architectural.
`AGENTS.md` is explicit: never weaken or delete a test to make a check pass.

## Check the paperwork landed in the same change

One `ROADMAP.md` task is one atomic commit. That commit is expected to contain:

- the task's checkboxes ticked in `ROADMAP.md`, with a deviation note if reality differed;
- `CHANGELOG.md` under `[Unreleased]` when the change is user-facing;
- the docs the task names — `docs/MCP_TOOLS.md` for a renamed tool,
  `docs/QDRANT_COLLECTIONS.md` for a payload change, `docs/PROMPTS.md` for a prompt change;
- an ADR in `docs/adr/` copied from [`../adr/template.md`](../adr/template.md) when the decision is
  architectural, recording the reason and not only the change.

A doc that promises behaviour the code does not have is a finding, not a nitpick — that is the next
section.

## Check the failure paths

The design degrades rather than crashes on expected failures, so a change that only handles the happy
path is incomplete. Ask what happens when:

- the LLM endpoint is unset, down, or returns unparseable output (`agents/errors.py`,
  `LLMConfigurationError`, `AgentExecutionError`, and the regex fallback in extraction);
- Qdrant is unreachable or the collection does not exist (`vector/errors.py`,
  `VectorStoreError`, `CollectionNotFoundError`; the store raises a message naming `make dev`);
- a news source returns 401/403/429/5xx or a non-JSON body (`news/errors.py`, the `retryable` flag,
  and the aggregator's graceful degradation);
- the collection is empty, the ingest is a duplicate, or a day already has a stored reading (the
  one-shot commands must stay idempotent).

Every one of these has a test somewhere in `tests/`; a change to the path with no matching test is a
finding.

## Demand evidence, and check the claims

Evidence has three parts: **the command, its observed output, and the date**. "Tests pass" is none of
them. A review comment is stronger still when it points at the code that would have to change.

Treat every factual claim in agent-written prose as a claim to verify against the code — a docstring,
a README line, a doc paragraph. The repository has a real example. Until phase 10.2,
`CONTRIBUTING.md`'s import-rules section said the layering was "enforced by `import-linter`". No such
tool is installed and no `[tool.importlinter]` section exists; the actual guard is the subprocess and
AST tests in `tests/unit/test_numerology_api.py`
(`test_numerology_does_not_import_the_layers_above_it`,
`test_models_depend_on_nothing_beyond_the_package_root`), backed by the layer table in
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) and the rule in `AGENTS.md`. The check is mechanical,
because the tool it names remains absent from the toolchain:

```bash
grep -rn "importlinter" pyproject.toml uv.lock .pre-commit-config.yaml   # no hit
grep -rn "import-linter" CONTRIBUTING.md docs/agentic/EVAL_OF_AGENT.md   # only the correction
```

A claim that names a tool, a command or a file is cheap to verify and expensive to leave wrong; the
correction belongs in the same change, which is what phase 10.2 did.

## Review checklist

- [ ] The DoD is open next to the diff, and every item is checked against it.
- [ ] `make lint`, `make test`, and `make test-eval` when the eval is touched were re-run by the
      reviewer, with the output read.
- [ ] `tests/` was diffed for removed, skipped or weakened assertions.
- [ ] `ROADMAP.md` checkboxes, `CHANGELOG.md`, the named docs and any ADR are in the same commit.
- [ ] The failure paths (LLM, Qdrant, news source, empty/duplicate data) were considered and tested.
- [ ] The evidence is command + observed output + date, not a summary.
- [ ] Every factual claim in new prose was checked against the code.
- [ ] The change is one atomic commit, ready to land, with nothing unrelated in the diff.
