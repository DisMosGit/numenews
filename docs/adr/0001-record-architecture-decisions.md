# 1. Record architecture decisions

## Status

Accepted (phase 0)

## Date

2026-09-21

## Context

numenews makes a series of choices that are not visible in the code and that will be questioned
again: numerology as the domain and reduction, master numbers and gematria as its entire scope;
`pydantic-ai` instead of hand-written orchestration; MCP as the primary interface; local
embeddings instead of a hosted API; Qdrant with hybrid search and payload indexes; long-term
memory in a payload-only collection; JSON-only stdout. Without a written record the reasoning
disappears as soon as the commit message scrolls out of view, and the same debates restart.

## Decision

Every architecturally significant decision is recorded as an Architecture Decision Record under
`docs/adr/`, in the format of Michael Nygard ("Documenting Architecture Decisions", 2011):

- one file per decision, named `NNNN-short-title.md`, numbered sequentially;
- the status starts at `Proposed` and becomes `Accepted`, `Deprecated`, or is superseded by a
  later ADR;
- ADRs are immutable: a change of mind is a **new** ADR that supersedes the old one;
- the template lives in [`template.md`](template.md).

`AGENTS.md` and `CONTRIBUTING.md` both require an ADR for an architectural change. The roadmap
reserves the numbers: 0002 numerology scope (1.8), 0003 local embeddings (3.9), 0004
`pydantic-ai` (4.6), 0005 JSON-only output and 0006 one-shot vs REPL (7.10), 0007 Qdrant hybrid
search, 0008 `fastembed` vs OpenAI embeddings and 0009 `hishel` caching (10.3), 0010 the MCP
server (6.12). 0011 records the RAG pipeline of phase 5, which the roadmap did not reserve a number
for; the phase that needs one takes the next free number and records it here.

## Consequences

- The reasoning behind the architecture is reviewable next to the code.
- Reviewers can point at an ADR instead of re-arguing a decision.
- A small, ongoing writing cost: any significant change is not "done" until its ADR exists.

## References

- [Documenting Architecture Decisions — Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [`template.md`](template.md)
- [`ROADMAP.md`](../../ROADMAP.md)
