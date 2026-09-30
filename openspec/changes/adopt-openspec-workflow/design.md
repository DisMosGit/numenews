# Design

## Context

See `proposal.md` — Why. Three properties of the current repository shape everything below:

1. **The roadmap is a citation hub.** ~11 markdown links, ~145 prose mentions that name the file, and
   a further ~131 lines that mention a phase without ever writing `ROADMAP` (D11) — 276 lines in all,
   across 108 files. The prose mentions are not decoration: test docstrings use roadmap task ids as
   their acceptance-criterion anchors
   (`"""ROADMAP 7.4: --date 2026-09-22 reads that day, not today."""`), and twelve ADRs cite phases as
   the origin of their decisions. Deleting the file without re-targeting them leaves ~330 claims
   pointing at nothing.
2. **The project treats ADRs as immutable.** The phase-10 notes state that the ADRs themselves are
   not rewritten, and that a factual correction to a forward-reference was made "as a factual
   correction, not a decision revision". Six ADRs hold links that this change breaks.
3. **`openspec/specs/` is empty**, so both backfilled capabilities are additions from OpenSpec's
   point of view even though the behaviour they describe has shipped.

## Goals / Non-Goals

**Goals:**

- Every removed citation resolves to a document or spec that actually owns the claim it was making.
- Each commit leaves the tree self-consistent: no intermediate state has a broken link or a
  half-deleted roadmap.
- The behaviour contract for the two external surfaces is captured in OpenSpec without duplicating
  the narrative documentation that already exists.

**Non-Goals:**

- Documenting the internals (numerology, news adapters, vector layer, agents, pipeline, memory, eval)
  in OpenSpec. Those arrive forward-only, when a real change touches them.
- Any change to product behaviour, dependencies, prompts, models or collections.
- Adding a link checker, a docs build or any CI. The project has none and this change does not
  introduce one; verification is a command run by hand.

## Decisions

### D1 — Delete the roadmap outright, with no archived copy

**Chosen:** `ROADMAP.md` is deleted. Nothing replaces it as a file.

**Alternatives considered:** a frozen copy at `docs/history/ROADMAP-v0.1.0.md`; a condensed history
page; keeping it with a "superseded" banner.

**Why:** the only thing a surviving copy preserves is the phase narrative, and that narrative is
already recoverable — `git log` holds every commit the roadmap sequenced, the `v0.1.0` tag marks the
end of it, and `CHANGELOG.md` records what shipped. A frozen copy would preserve that at the cost of
keeping the question "which file is authoritative?" permanently open, which is the exact problem this
change exists to close. `CONTRIBUTING.md` states where the history went so nobody goes looking.

### D2 — Citations are re-targeted by owner, not deleted

Each roadmap phase had a topic document that already owned its subject. The mapping below is the
substance of the migration; the prose around a citation keeps its meaning and only its anchor changes.

| Roadmap reference | New owner |
|---|---|
| Phase 0 — skeleton, tooling | `docs/STACK.md`, `docs/TESTING.md`, `CONTRIBUTING.md` |
| Phase 1 — numerology | `docs/NUMEROLOGY.md` |
| Phase 2 — news sources | `docs/NEWS_SOURCES.md` |
| Phase 3 — embeddings, Qdrant | `docs/EMBEDDINGS.md`, `docs/QDRANT_COLLECTIONS.md` |
| Phase 4 — LLM agents | `docs/PROMPTS.md`, `docs/STACK.md` |
| Phase 5 — RAG pipeline | `docs/RAG_PIPELINE.md`, `docs/CONTEXT_MANAGEMENT.md` |
| Phase 6 — MCP server | `mcp-surface` spec, `docs/MCP_TOOLS.md`, `docs/TOOL_USE.md` |
| Phase 7 — CLI | `cli-surface` spec, `docs/USER_FLOW.md` |
| Phase 8 — long-term memory | `docs/CONTEXT_MANAGEMENT.md`, `docs/adr/0012-long-term-memory.md` |
| Phase 9 — eval | `docs/EVAL.md`, `docs/eval_report.md` |
| Phase 10 — polish, coverage floors | `docs/coverage_report.md`, `CHANGELOG.md` |
| "Правила работы с роадмапом" | `AGENTS.md`, `CONTRIBUTING.md` |

A citation becomes a **capability name in inline code** where a spec owns the behaviour, and a
**link to the owning docs page** everywhere else. For example the docstring above becomes
`"""cli-surface: a named --date resolves against the pipeline clock."""`, and
`docs/QDRANT_COLLECTIONS.md`'s header drops "ROADMAP.md is the authoritative status" for a link to
`docs/ARCHITECTURE.md`.

### D3 — Citations name requirements, never task numbers

**Chosen:** anchor on a stable identifier — the capability name plus the behaviour — rather than on a
number that no longer exists. Task ids (`7.4`) are replaced by requirement or scenario names.

**Alternative considered:** keep a mapping table from task ids to specs so old ids stay resolvable.

**Why:** a mapping table is a new artifact whose whole purpose is to preserve identifiers nobody needs
any more, and it would need maintaining forever. Requirement names are the natural stable anchor and
they already exist in the two specs.

### D4 — Spec links avoid paths that do not exist yet

**Chosen:** markdown links point at targets that exist at apply time (`docs/` pages, the
`openspec/specs/` directory, which exists and holds `.gitkeep`). Specific capabilities are named in
inline code rather than linked.

**Alternative considered:** link straight to `openspec/specs/<capability>/spec.md`.

**Why:** the spec files only land at that path when the change is archived, so linking to it during
apply would leave every touched document carrying a broken link until archive — and the task that
verifies "no broken links" would fail on its own output. Naming the capability keeps the reference
unambiguous without betting on a path.

### D5 — ADR edits stop at the reference, never the decision

Every one of the twelve ADRs mentions the roadmap, and nine link it from a trailing References or
"See also" list. In those files the **file name may be removed or re-pointed and its phase
description updated**; decision text, rationale and alternatives are otherwise untouched, and no ADR
gains or loses a decision.

An in-body mention is reworded only as far as the dead file name: "`ROADMAP.md` 1.1 additionally
places …" becomes "Phase 1 additionally places …". The phase number stays, because in an ADR it
records *when* a decision was made, which is what an ADR is for (D11).

**Why:** the project's immutability rule protects decisions, not hyperlinks, and the phase-10 notes
set the precedent that a purely factual correction to a reference is not a revision. A dangling link
to a deleted file is not history; it is a broken link that this change exists to remove, and leaving
nine of them inside the ADRs would contradict the whole point. Reviewing an ADR diff during apply
means checking exactly this: if a sentence changes anything other than how the roadmap is named, it is
a mistake.

### D6 — The two specs describe behaviour and stop there

`mcp-surface` and `cli-surface` are behaviour contracts: inputs, outputs, error conditions, defaults
and guarantees, each requirement carrying testable scenarios. They deliberately exclude client setup
snippets, worked JSON examples, the recipes list and the transport configuration, which stay in
`docs/MCP_TOOLS.md` and `docs/USER_FLOW.md`. Those documents gain a line naming the spec as
authoritative for behaviour, so the split is stated rather than implied.

**Why:** the alternative — folding the narrative docs into the specs — would make the specs a copy of
two well-written documents and create a second place to update on every change.

### D7 — The coverage floors stay out of OpenSpec

The per-layer floors currently cited as "ROADMAP 10.4" are re-anchored to
`docs/coverage_report.md`, which already holds the numbers, the command and the date.

**Why:** a coverage floor is a quality gate on the build, not externally observable behaviour, and the
spec guidance is explicit that a spec describes behaviour. Putting it in a spec would also make it
look like something a future change must issue a MODIFIED delta to adjust, which is process for its
own sake.

### D8 — GitHub Issues becomes the backlog, and the roadmap rules move to AGENTS.md

**Chosen:** `AGENTS.md` names OpenSpec as the source of truth for what is built and for work in
flight, and the `.github/` issue templates give an idea somewhere to live before it is a change.

**Why:** the roadmap's rules carried one job OpenSpec does not: a place for a thought that is not yet
a change. `openspec/changes/` only holds work that has been proposed and designed, so without the
issue templates a v0.2 idea has nowhere to sit — the gap is real and worth closing deliberately rather
than discovering later.

### D9 — `CODE_OF_CONDUCT.md` and `SECURITY.md` are skipped

No community to moderate, no hosted service, no user data at rest. The only secret involved is the
author's own API key in a gitignored `.env`, which `.env.example` and `.gitignore` already cover.
**Revisit when** the repository starts accepting contributions from people other than its author, or
something it runs becomes reachable from a network.

### D10 — Apply in two commits so every intermediate state is consistent

1. **Re-target the citations first**, while `ROADMAP.md` still exists. Every link resolves both
   before and after this commit, so it is safe to land on its own.
2. **Delete `ROADMAP.md` second**, once nothing points at it.

The process documents (`AGENTS.md`, `docs/agentic/`, `CONTRIBUTING.md`, `README.md`) can land in
either commit, but the deletion must be in the same commit as nothing else, so the diff that removes
the roadmap is readable on its own.

**Alternative considered:** one commit doing both.

**Why:** a single commit mixes ~330 mechanical citation edits with the deletion and makes the
deletion unreviewable. Two commits also means the tree is green after each one, which the project's
one-atomic-commit rule requires.

### D11 — A bare phase number is a citation; build history is not

**Chosen:** a phase reference that never names the file — `(phase 8.3)`, `> Phase 3.`, "the MCP tools
of phase 6", "Roadmap 5.3", "roadmap 3.8", or a bare "the phase that needs it" — is a roadmap citation
and is re-pointed by the same D2/D3 rules. The sweep pattern is case-insensitive on both words,
`/[Rr]oadmap|[Pp]hase/`, because the citations appear in three casings (`ROADMAP 7.4` in test
docstrings, `Roadmap 5.3` and `roadmap 3.8` in source docstrings and prose). It has no false positives
in this tree: every occurrence is the roadmap sense.

Three surfaces keep their phase vocabulary, and their in-body mentions of "the roadmap" as a plain
noun, because there the number records *when* something was decided rather than *where* it is
specified:

- `CHANGELOG.md` — what each release contained, labelled with the phase ids it was built from.
- `docs/adr/` — an ADR states the context in which a decision was made, and that context is frozen.
  Several ADRs reason explicitly about what "Roadmap 5.1 asks for" or "the roadmap's fifteen
  minutes"; that is decision rationale, and D5 forbids rewriting it.
- the "How it was built" narrative in `docs/ARCHITECTURE.md` — the same history in prose.
- `tests/eval/fixtures/news.jsonl` — retrieved article text, not prose about the project. One fixture
  is a story headlined "Vaccine trial enters phase 3"; rewriting it would corrupt the eval corpus and
  the assertions that read it. A sweep that matches it has found data, not a citation.

Two narrower rules sit on top of those exemptions:

- **The dead file name is stricter than the phase vocabulary.** `ROADMAP.md` — the filename, in any
  casing — survives only where the deletion itself is being documented: the `CONTRIBUTING.md` section
  that says where the history went (D1) and the `CHANGELOG.md` `Removed` entry. It is gone from every
  other file, `docs/adr/` included.
- **`blank_issues_enabled`-style config and the two entrance documents** (`.github/`, `README.md`,
  `AGENTS.md`, `.env.example`) get the strictest check of all: no `roadmap` and no `phase` in any
  casing, because a newcomer reads those first and must not meet a term that resolves nowhere.

The sweep is run with `git grep`, not `grep -r`: it searches tracked files only, so the two virtual
environments (`.venv`, `.venv-eval`) and the `__pycache__` trees cannot produce matches and mask a
clean result. `grep -r .` reaches all of them.

Two files sit outside the obvious `*.py` / `*.md` / `*.toml` / `Makefile` set and are easy to miss:
`.env.example`, whose section headers carried phase tags, and the `news.jsonl` fixture above.

One further, narrower exemption: two test *functions* carry a phase word in their name
(`test_the_phase_surface_is_exactly_nine_distinct_tools`,
`test_mcp_entry_point_serves_the_phase_six_server`). They are renamed anyway, and `tasks.md` 3.4 names
both so that "no test name changed" stays a checkable invariant rather than a loophole.

**Alternative considered:** limit the sweep to the literal string `ROADMAP` and add one line defining
"phase N".

**Why not:** the literal grep is a verification that passes on a broken tree. It returns nothing while
leaving ~276 lines across 108 files referring to a numbering scheme that no longer exists, and
`CHANGELOG.md` cannot absorb them — it records coarse ids (`phase 3.1`, `phase 8`) while the docs cite
fine-grained ones (`8.3`, `3.7`, `6.7`, `9.2`), so a definitional note still leaves about twenty
unresolvable. Every verification grep in `tasks.md` therefore matches `/ROADMAP|[Pp]hase/` and excludes
the surfaces above, which is the only form that can fail when the work is incomplete. This roughly
doubles the edit count, to ~276 lines, without changing its kind: the same prose-only, mechanical
re-anchoring.

## Risks / Trade-offs

- **A generated document is edited without its generator** → `docs/eval_report.md` is rewritten on
  every metric run from the string literals in `tests/eval/test_rag.py`, so changing the committed
  report alone would be silently reverted by the next `make test-eval`. The two are edited together
  and must end up byte-identical. This is the one place where the "docstrings and comments only" rule
  has to bend, and `tasks.md` 3.4 names it as a sanctioned exception rather than leaving it implied.
- **A docstring edit breaks a test** → the 71 test docstrings are edited as prose only; no assertion,
  name, marker or fixture may change, and the full suite runs after the edit. A test that changes
  behaviour is a mistake, not a fix.
- **An ADR edit crosses the immutability line** → D5 bounds it to References sections; the review
  step diffs the ADRs and rejects anything touching decision prose.
- **The specs drift from the narrative docs** → the ownership split is declared in both the specs'
  purpose and the docs' headers (D6), and `docs/MCP_TOOLS.md` / `docs/USER_FLOW.md` keep only the
  material the specs exclude.
- **Someone needs the phase narrative after deletion** → `CONTRIBUTING.md` says where it lives (git
  history, the `v0.1.0` tag, `CHANGELOG.md`), so the deletion is explained rather than surprising.
- **A missed citation survives** → verification runs two greps over tracked files, excluding only
  `openspec/` (where this change's own artifacts legitimately name the file being deleted):
  `ROADMAP` must return nothing **anywhere**, `docs/adr/` and `CHANGELOG.md` included; and
  `/ROADMAP|[Pp]hase/` must return nothing outside the three frozen-history surfaces of D11.
- **The backfilled specs are mistaken for new work** → the specs' `## Purpose` and this design both
  record that they describe shipped behaviour, and the change declares no product change.

## Migration Plan

Docs and process only; nothing to deploy and nothing to roll back beyond `git revert`. The order is
D10: re-target citations, then delete the file, then archive the change so the two spec deltas land in
`openspec/specs/`. If the specs are wrong, a future change issues a MODIFIED delta — the normal path —
rather than editing the archived spec by hand.

## Open Questions

- When a real change first touches an internal layer, does that layer get a backfilled capability spec
  (as `mcp-surface` and `cli-surface` did here), or only a delta describing the change? Deferrable: it
  does not affect these specs, the approach or the task breakdown, and the first such change will make
  the answer obvious.
