---
work_package_id: WP06
title: Cross-command regression net
dependencies:
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-013
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-handle-resolution-consistency-01M2TPWG
base_commit: 647f3fbd577ce138f61c33132fdc02bf1612054e
created_at: '2026-09-18T19:44:18.616043+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
history:
- Created by /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_handle_resolution_consistency.py
execution_mode: code_change
owned_files:
- tests/specify_cli/cli/commands/test_handle_resolution_consistency.py
role: reviewer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `reviewer-renata` (role: reviewer) via `/ad-hoc-profile-load` first — this WP is the
adversarial safety net, so bring a skeptical, cross-command lens.

## Objective

One suite that proves the mission's promise holds ACROSS commands and that the pre-existing
correct commands are not regressed. This WP owns only a new test file; it must not edit source
(if a cross-command bug is found, report it for the owning WP to fix).

## Context

- Depends on WP02–WP05 being implemented (their fixes must exist for these assertions to pass).
- Canonical form: `Mission not found: <handle>` (capital M) for the FIXED commands.
- Excluded envelopes to PROTECT (must stay intact): the identity resolver error
  (`No mission found for handle "<h>"` + `spec-kitty migrate backfill-identity`,
  `context/mission_resolver.py:147`), `reconcile`'s "mission dossier not found"
  (`reconcile.py:130`). These are NOT to be flattened — assert they still carry their
  remediation/semantics.
- Use in-process `typer.testing.CliRunner`. Baseline pins to respect: `test_next_fail_closed.py:125`,
  `test_coordination_doctor.py:1385`.

## Subtasks

### T028 — Canonical message across fixed commands
Parametrized: for `research`, `plan`, `tasks`, `merge` (fresh) — a nonexistent handle in a
≥2-mission repo yields `Mission not found: <handle>` and none of the old defect strings
("to disambiguate", "lanes.json is required").

### T029 — NFR-001 snapshot invariance
For each fixed command above, snapshot `kitty-specs/` before/after the nonexistent-handle run;
assert byte-identical (the phantom-write guard, generalized).

### T030 — FR-013 correct-commands-stay-correct
Assert the identity resolver error still names the handle AND still contains
`backfill-identity`; assert `reconcile` still says "dossier not found". These envelopes are
intentionally NOT unified — regressing them (flattening to the bare constant) fails this test.

### T031 — Legacy-mission count agreement
A repo whose missions include a legacy (no `mission_id`) one: assert `next` discovery count ==
the plan/tasks auto-detect count (both see the legacy mission). Guards the shared-population
decision.

### T032 — Green + blast radius
Whole new suite green; run the union blast radius:
`PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_handle_resolution_consistency.py tests/next/ tests/research/ tests/merge/ tests/specify_cli/cli/commands/agent/ -q`.

## Definition of Done
- The consistency suite passes end-to-end with WP02–WP05 merged into this lane's base.
- Pre-existing correct-command tests remain green (no accidental unification regression).

## Branch Strategy
Base/merge target `issue-4631-4682-mission-handle-resolution`; lane worktree from `lanes.json`.
This WP depends on WP02–WP05; its lane base must include their merged work before implementation.

## Reviewer guidance
This IS the reviewer WP. Confirm the excluded envelopes are asserted intact (not flattened),
the snapshot guard is real, and the legacy-count agreement test actually stages a no-`mission_id`
mission.
