---
title: Engineering notes — Architectural reviews
description: 'Landing page for the architectural-reviews engineering notes: on-demand deep-dive reviews of the spec-kitty codebase by architect-profile agents.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/architectural-review/2026-05-25-deep-dive-architectural-review.md
- docs/plans/engineering-notes/architectural-review/2026-09-27-kitty-shared-architecture-alignment.md
---
# Engineering notes — Architectural reviews

This directory holds **deep-dive architectural reviews** of the spec-kitty codebase, performed by architect-profile agents on demand (typically post-merge of a substantial mission or before a major release).

It is the third sibling of [`reflections/`](../reflections/) and [`finding/`](../finding/). The trio together capture the operator-side, system-side, and architect-side observations.

## What belongs here

- DDD bounded-context audits.
- Logical duplication scans.
- Module-scope / package-boundary findings.
- Cross-references between observations stored in `finding/` and `reflections/` and concrete code locations.
- Recommended scopes for follow-up remediation missions.
- Alignment reviews of spec-kitty against external architecture documents (for example the Kitty Shared Architecture).

## What does NOT belong here

- Per-mission ADRs — those go to the current-era ADR folder (see the [ADR index](../../../adr/index.md)).
- Operator-side process notes — those go to `finding/`.
- Orchestrator self-corrections — those go to `reflections/`.
- Ad-hoc code reviews of a single PR — use `code-review` skill output.

## File format

One file per review run. Filename: `YYYY-MM-DD-<focus-slug>.md`. Suggested structure (see [`2026-05-25-deep-dive-architectural-review.md`](./2026-05-25-deep-dive-architectural-review.md) for the canonical shape):

1. Executive summary
2. Bounded-context map
3. Logical duplication findings
4. Module-scope findings
5. Mapping to existing engineering notes
6. Open-issue triage (candidates for remediation missions)
7. Recommended next-mission scope
8. Out-of-scope statement

Each numbered finding gets a stable ID (`LD-1`, `MS-2`, etc.) so it can be referenced from mission specs and tracker issues.

## Index

- [2026-05-25 — Deep-dive post-mission-122 audit](2026-05-25-deep-dive-architectural-review.md) — Architect Alphonso
- [2026-09-27 — Engine-side alignment review against the Kitty Shared Architecture](2026-09-27-kitty-shared-architecture-alignment.md) — adversarial squad, consolidated by Architect Alphonso; engine-side findings only
