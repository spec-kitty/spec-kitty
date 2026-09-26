---
work_package_id: WP03
title: Cross-cutting integration regression (#4889 +
dependencies:
- WP01
- WP02
requirement_refs:
- C-003
- FR-002
- FR-005
- FR-006
- FR-007
- NFR-002
planning_base_branch: fix/implement-lane-recut-and-planning-commit-integrity
merge_target_branch: fix/implement-lane-recut-and-planning-commit-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/implement-lane-recut-and-planning-commit-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/implement-lane-recut-and-planning-commit-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-lane-recut-and-planning-commit-integrity-01M3CM55
base_commit: a944d5db5f7e2e361c378682ffd5809bb7ad8b55
created_at: '2026-09-25T17:16:46.530818+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Integration proof
history:
- at: '2026-09-25T16:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/lanes/
create_intent:
- tests/lanes/test_lane_allocation_integrity_e2e.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- tests/lanes/test_lane_allocation_integrity_e2e.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Cross-cutting integration regression (#4889 + #4905)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Prove both defects are dead **together** on a realistic coord mission, across every route and caller — live evidence over unit-green. Depends on WP01 and WP02 being present.

**Done when:**
- An end-to-end suite exercises the real `implement` / `agent action implement` entry points on a coord mission and shows: #4889 fails closed across REUSE / CRASH_RECOVERY / FRESH routes and both callers; #4905 lets WP01→WP02 both start with the coord tree clean after claim AND review-claim.
- The suite is RED before WP01/WP02 land and GREEN with them present (SC-004).

## Context & Source Map

- Depends on WP01 (`worktree_allocator.py` guard) and WP02 (`workflow.py` sink partition). This WP owns only `tests/lanes/test_lane_allocation_integrity_e2e.py` — no source edits (disjoint from WP01/WP02).
- Reuse the reproduction shapes in [../quickstart.md](../quickstart.md) and the two contracts in [../contracts/](../contracts/). Build isolated-HOME/XDG disposable repos with realistic content (per DIRECTIVE realistic-test-data), not stubs.

## Subtasks

### T020 — #4889 e2e across routes + callers
`test_destroyed_lane_fail_closed_e2e`: drive a coord mission to `in_progress`, then exercise the destroyed-lane refusal via CLI and via orchestrator; and confirm the three control arms (REUSE / CRASH_RECOVERY / genuinely-fresh) still resume/create. Assert the diagnostic names the missing branch and the stranded commit stays reachable via the named ref.

### T021 — #4905 e2e WP01→WP02
`test_coord_second_wp_starts_e2e`: coord mission, `agent action implement WP01` then `WP02`; assert WP02 starts (no `PlanningCommitMergeConflictError`) and the coord tree has zero `tasks/WP*.md` after claim AND after a WP01 review-claim.

### T022 — Interaction proof [P]
`test_fixes_are_independent`: assert that the #4905 sink partition does not alter #4889's FRESH-route behavior and vice-versa (a genuinely fresh lane on a clean coord still allocates normally; the fail-closed guard does not trip on a legitimate first claim). Guards against the two fixes re-opening each other.

### T023 — RED→GREEN confirmation + demotion
Document (in the test module docstring / mission trace) that these repros were RED pre-fix and GREEN post-fix. Where a WP01/WP02 transitional `@pytest.mark.regression` repro is now redundant with a focused unit test, note it for demotion (per red-first-tests-are-transitional) — do not leave duplicate regression markers where a unit home is better.

## Branch Strategy

Planning artifacts on `fix/implement-lane-recut-and-planning-commit-integrity`; merges back into it (then `main` via PR). Per-lane worktree from `lanes.json`.

## Test Strategy

Run foreground/narrow: `PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes/test_lane_allocation_integrity_e2e.py -q`. These are heavier e2e tests — keep them deterministic and isolated; do not run whole-dir sweeps in the WP.

## Definition of Done

- SC-001, SC-002, SC-003, SC-004 exercised end-to-end.
- `ruff check` + `ruff format --check` clean on the new test file.
- Suite green with WP01+WP02 present.

## Reviewer Guidance

Verify the suite hits the REAL entry points (not internal helpers only), uses realistic repos, and would actually catch a regression of either defect (mutation-style sanity: would it fail if the guard or the partition were reverted?).
