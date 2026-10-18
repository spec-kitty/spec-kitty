---
work_package_id: WP06
title: Docs & migration-author guidance to the ledger model (IC-07)
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-016
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-18T08:03:03.857493+00:00'
subtasks:
- T031
- T032
- T033
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: curator-carla
authoritative_surface: docs/adr/3.x/
create_intent: []
execution_mode: code_change
lane: planned
owned_files:
- CLAUDE.md
- AGENTS.md
- docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – Docs & migration-author guidance to the ledger model

## ⚡ Do This First: Load Agent Profile

Load `curator-carla` (`role: implementer`) — doctrine/knowledge maintenance. Implementation command
(depends on WP01–WP05): `spec-kitty implement WP06 --base WP05`

> Land LAST — this documents the SHIPPED shape, so every other WP must be merged first.

---

## Objective

Update the migration-authoring guidance to the ledger model so future authors declare the routing
key, a manifest entry, and identity/hash correctly. Two docs only.

Grounded in `plan.md` **IC-07 (G1, G2)**; spec FR-016.

## Context & Constraints — design invariants (carry these exactly)

- Document the SHIPPED behaviour, not the mechanism as designed — verify against the merged code
  before writing.
- This is a `code_change` WP that owns `CLAUDE.md` + a `docs/` ADR (neither under `kitty-specs/`).
- Keep terminology canonical (Mission, migrate/upgrade); do not reintroduce retired terms.

## Pointcut Map (file → change)

| # | file | change | what |
|---|------|--------|------|
| G1 | `CLAUDE.md` (migration section) | **MODIFY** | author guidance → ledger model: `clone_local_effect` as routing key, adding a `order_manifest.txt` entry, declaring `identity` / `content_hash_sources`, and the `spec-kitty migrate ledger` read surface. |
| G2 | `docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md` (Author Checklist ≈`:91`) | **MODIFY** | checklist → ledger model; cross-reference ADR `2026-10-17-1`. |

## Owned files (disjoint)

- `CLAUDE.md`
- `docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md`

## Subtasks & Detailed Guidance

### T031 – CLAUDE.md: routing key + manifest entry (G1, FR-016)
Rewrite the migration-authoring guidance so an author knows a migration's `clone_local_effect`
routes its record to the tracked vs per-clone ledger, and that a new migration needs an
`order_manifest.txt` entry in execution order (annotate intentional `target_version` ties).

### T032 – CLAUDE.md: identity / content_hash + read surface (G1, FR-016)
Document `identity` (stable drift key) and `content_hash_sources` (multi-file hash input), and that
`spec-kitty migrate ledger` is the one read surface for what ran / partition / drift.

### T033 – ADR 2026-07-07-1 author checklist → ledger model (G2, FR-016)
Update the Author Checklist to the ledger model and cross-reference ADR `2026-10-17-1`
(`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`).

## Test strategy & blast radius

Docs-only; no code tests. If touching charter/offering prose or user-facing terms, run the fast
terminology guard `pytest tests/architectural/test_no_legacy_terminology.py` (≈0.1s). Changelog
spelling is a separate gate if `CHANGELOG.md` is touched (it is not here).

## Quality gates

Prose clean; links resolve; terminology canonical; no retired terms. No code suppressions.

## Acceptance criteria satisfied

FR-016 (doc diff present for both files, aligned to the shipped ledger model).

## Risks & Mitigations

- **Doc drift from code:** verify every documented field/surface against the merged WP01–WP05 code
  before writing.

## Review Guidance

Confirm both files describe the shipped ledger model (routing key, manifest entry, identity/hash,
`migrate ledger`) and cross-reference ADR `2026-10-17-1`.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
