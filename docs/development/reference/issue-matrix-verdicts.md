---
title: Issue-Matrix Verdict Reference
description: The five issue-matrix verdict values, which transitions each one gates, the reference-classification model that decides whether a row is required, and the evidence-token rule.
doc_status: active
type: reference
updated: '2026-09-20'
related:
- docs/api/cli-commands.md
- docs/api/agent-subcommands.md
- docs/development/reference/index.md
---
# Issue-Matrix Verdict Reference

Look-up material for the `issue-matrix.json` verdict vocabulary and the
reference-classification model that decides which discovered `#NNNN` citations
require a verdict row at all (#3469). This page documents the two levers as a
single source of truth so an operator or agent never has to reverse-engineer
gating behavior from gate error text.

## The two levers

The issue-matrix approval gate has two independent decisions, and confusing
them is the root of most "why is this blocking approval" surprises:

- **Classification** decides whether a row is **required** (gating). It runs
  once, over every `#NNNN` reference discovered in mission artifacts
  (`spec.md`, `plan.md`, `research.md`, analysis docs, WP prompts, contracts),
  and is consumed identically by every site that computes
  "referenced-but-missing": the WP `approved`-transition blocker, the merge-time
  `merge_gates` check, and `status/doctor`. One shared function, one answer —
  a reference is never gating at one site and non-gating at another.
- **Verdict** decides whether an existing row is **resolved**. An operator may
  record any verdict on any row regardless of its classification; a
  `not-applicable` verdict makes a row non-gating regardless of classification,
  and an implementation-target classification requires a row to exist even if
  the scaffolder didn't produce one for it.

The two levers can disagree by design (an operator can always assert
`not-applicable` on a row the scaffolder classified gating), and that
disagreement always resolves in favor of the operator's explicit verdict.

## Verdict values

| Verdict | Meaning | Gates `approved`? | Gates `done`/merge? |
|---|---|---|---|
| `fixed` | The mission fixed the referenced issue. | No (resolves the row) | No |
| `verified-already-fixed` | The issue was confirmed already fixed before this mission touched it. | No | No |
| `deferred-with-followup` | Work is deliberately deferred; a follow-up is tracked. Requires an evidence-token (see below). | No | No |
| `in-mission` | A later work package in *this* mission will close the issue. | No — accepted at per-WP `approved` | **Yes** — rejected at `done`; must resolve to a terminal verdict before the mission merges |
| `not-applicable` | The reference is cited for context only, or is a PR/commit reference — the mission owes it no work. **Terminal.** | No | No — passes unchanged, unlike `in-mission` |

`not-applicable` is additive: it was added alongside the four pre-existing
values with no change to their meaning, so every `issue-matrix.json` file
written before this change continues to validate with zero migration.

## Reference classification: which citations become gating rows

Every discovered `#NNNN` token is classified into exactly one of three
buckets, aggregated over **all** of its occurrences in the mission's
artifacts (not just the first one found):

- **Implementation-target** (gating) — the default. A row is required and
  must carry a verdict before `approved`.
- **Context-only** (non-gating) — the citation is scaffolded as a row for
  audit purposes, but does not block approval. A row still records the
  citation truthfully (typically with `not-applicable`); it just isn't
  required to unblock the transition.
- **PR/commit reference** (non-gating) — the same as context-only: recorded,
  never blocking.

### Default-gating fail-safe

Classification only ever **demotes** a reference from gating to non-gating,
and only on a positive, explicit signal. An unmarked bare `#NNNN` in ordinary
prose always gates. The demoting signals are:

- A `PR ` or `pull` token immediately associated with the reference (either
  hash form, `PR #300`, or a full `/pull/<n>` URL) — classified as a
  PR/commit reference.
- A context marker on the same line: `Follow-up:`, `baseline-red`, `see #`,
  `parent`, `epic` — classified as context-only.
- A cross-repo reference (`owner/repo#NN`, or a full `/issues/<n>` URL for a
  different repository) — already excluded from discovery entirely; it never
  becomes a row of any kind.

Ambiguity never fails open: if none of the above signals is present, the
reference gates.

### Multi-occurrence aggregation: implementation-target wins

A `#NNNN` cited once as context (e.g. `parent: #200`) and once as an
implementation target (e.g. "fixes the defect from #200") is classified
**gating** — the least-demoted occurrence wins across the whole aggregate. A
reference is never silently downgraded because one of its several citations
happened to carry a demoting marker.

## The evidence-token rule (`deferred-with-followup`)

A `deferred-with-followup` verdict's `evidence_ref` must contain either:

- an issue reference in `#NNN` form (the follow-up issue), or
- a literal `Follow-up:` token.

A bare `deferred-with-followup` with no follow-up handle in `evidence_ref` is
rejected. `issue-verdict --help` documents this rule directly so it is
discoverable before the gate rejects a submission, not only after.

## Early discoverability

The specify/plan/tasks/analyze prompt templates carry a non-gating heads-up
that approvals require an issue-matrix verdict for every referenced
implementation-target issue — so the gate is not a surprise encountered only
at the first blocked approval.

## See also

- [`spec-kitty agent tasks move-task` and `spec-kitty agent issue-verdict`](../../api/agent-subcommands.md) — the generated CLI reference for the commands that read and write issue-matrix rows, including `move-task`'s `--actor`/`--reason` aliases and `issue-verdict`'s full `--help` text.
- [CLI Command Reference](../../api/cli-commands.md)
- ADR `2026-09-20-1-issue-matrix-not-applicable-verdict` (`docs/adr/3.x/`) — the design record for the `not-applicable` verdict, the classification narrowing, and how it supersedes the never-implemented WP09 `not_applicable` Gate-4 intent noted in `merge_gates.py`. *(Landed on this mission's WP02 lane; not yet present in this checkout — reconcile at mission consolidation once the lane branches merge.)*
