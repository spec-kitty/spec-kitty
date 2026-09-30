---
title: Engineering notes — Findings
description: 'Landing page for the findings engineering notes: process observations from running missions end-to-end, as read-only inputs to future doctrine improvements.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/finding/2026-05-24-mission-01KSAF14-orchestration-findings.md
---
# Engineering notes — Findings

This directory holds **process findings** from running missions end-to-end: places where the orchestration, the CLI gates, the lane model, or the doctrine surfaces produced friction or behaved in ways that surprised an attentive operator.

It is the sibling of [`reflections/`](../reflections/). Both directories are read-only inputs to future tactic/skill/doctrine improvements; neither is load-bearing.

## What belongs here

- A specific orchestration step that needed remediation (schema mismatch, hidden gate, missing CLI flag, etc.).
- A point where the operator's mental model diverged from what the runtime actually did.
- A class of test fragility surfaced by a refactor that the refactor itself didn't introduce.
- Observations about which automation succeeded and which silently no-op'd.
- Per-mission process notes that the auto-generated retrospective.yaml didn't capture (because the retrospective generator's heuristics are still narrow).

## What does NOT belong here

- One-line typos in messages — those are bug fixes.
- Long-form architectural decisions — those are ADRs.
- Strong opinions about how Spec Kitty *should* work — those are RFC-style proposals.
- Per-WP-implementation diary entries — the WPs themselves are the record.

## Difference from `reflections/` and `architectural-review/`

Loose rules of thumb:
- **`reflections/`**: the orchestrator's own failure modes during a mission. "I should have done X earlier."
- **`finding/`**: the system's failure modes during a mission. "When the operator does X, the CLI does Y, but only after Z."
- **`architectural-review/`**: deep-dive code/structure audits done by architect-profile agents. "Module X and Y duplicate the same concept under different names."

When in doubt, write the note as a finding. Curators can promote/demote later.

## File format

One file per finding. Filename: `YYYY-MM-DD-short-kebab-slug.md`. Suggested structure:
- H1 title
- One-sentence summary
- *What happened* — concrete observation with file paths / commands / exit codes
- *Why it matters* — what an operator without context would have hit
- *Workaround that worked* — what the orchestrator (or implementer) did to move past it
- *Follow-up candidate* — a sketch of what a permanent fix might look like (not a commitment)

Notes here are **not load-bearing**. The Spec Kitty project may distill recurring themes into ADRs, doctrine, or skills — at which point the corresponding finding can be archived.

## Index

(append as new findings land)

- [2026-05-24 — Mission 01KSAF14 orchestration findings (10 items)](2026-05-24-mission-01KSAF14-orchestration-findings.md)
