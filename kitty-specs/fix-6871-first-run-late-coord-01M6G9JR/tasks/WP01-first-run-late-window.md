---
work_package_id: "WP01"
title: "First-run late-coordination window"
dependencies: []
planning_base_branch: "main"
merge_target_branch: "main"
branch_strategy: "Planning artifacts were generated on the issue branch; completed changes must merge back into main."
requirement_refs:
  - FR-001
  - FR-002
  - FR-003
  - FR-004
  - FR-005
  - FR-008
subtasks:
  - "T001"
  - "T002"
  - "T003"
  - "T004"
  - "T005"
phase: "Phase 1 - Core fix"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2026-11-02T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 – First-run late-coordination window

## Objective

Give a first-run teardown the same protection the `--resume` path already has for a coordination
commit the target never received: project the window, commit it, prove every coordination record
in it is byte-identical on the target, and only then delete the branch.

## Context

- `src/specify_cli/consolidation/phase_teardown.py` — `_land_late_coordination_commits` starts
  with `if not run.is_resume: return`, so the first run has neither the projection nor the
  `assert_late_window_landed` proof (#6791/#6857).
- `run.coord_tip_after_projection` is captured at the end of
  `phase_bookkeeping._phase_record_done_and_project`, after every merge-owned coordination write.
  It is the tip the merge verified; the projection teardown gate already compare-and-swaps
  against it.
- The window base for a resume is `run.state.pre_mutation_coord_sha` (the pre-mutation snapshot),
  deliberately: it spans everything the coordination branch changed since the merge began.
- `tests/coordination/test_projection_teardown.py` has the real-git fixture helpers
  (`_init_repo`, `_make_coord_branch`, `_append_coord_commit`, `_coord_run_state`,
  `_gated_coord_fixture`) and the CAS cases.

## Subtasks

### T001 — Red: a first-run late commit is not lost

In `tests/coordination/test_projection_teardown.py`, next to
`test_status_commit_landing_between_gate_and_delete_is_never_destroyed`:

- fixture: `_gated_coord_fixture` + `_coord_run_state` (a FIRST run: `is_resume=False`,
  `coord_tip_after_projection == projected_tip`);
- inject one late coordination commit (`kitty-specs/<slug>/traces/late.md`) between the projection
  capture and `_teardown_coordination_triple(run)`;
- assert the record's bytes are at the target ref, the branch is gone, the marker is flattened.

At the base commit this fails: the branch is deleted, the record exists nowhere on the target,
and the call returns normally (exit-0 shape).

### T002 — Red: a late commit that cannot land refuses

Same fixture; the late commit DELETES a coordination record the target still holds (e.g.
`traces/projected.md`, which the fixture commits on the coord branch and the target holds).
Assert `CoordinationTeardownError`, the branch still exists at the late tip, the marker is
intact, and the message names the branch, the target and `spec-kitty consolidate --resume`.

At the base commit this fails: the branch is deleted silently.

### T003 — Window base selection

- Add `_late_window_base(run)` returning the resume base for a resume and
  `run.coord_tip_after_projection` for a first run (never `pre_mutation_coord_sha` for a first run
  — that would re-walk the merge).
- Drop the `if not run.is_resume: return`, keep `_refuse_unbuildable_late_window` reachable only
  on the resume path, and return (no window, behaviour unchanged) when a first run has no anchor.

### T004 — Advance the approved tip only under proof

After the projection commit and `assert_late_window_landed` both succeed on a first run, set
`run.coord_tip_after_projection` to the tip the assertion was made over — and only if the ref is
still at that tip (compare-and-swap; a fresh read must never be stamped). This keeps the
projection teardown gate and the branch-delete CAS anchored on a proven tip.

### T005 — Docstrings

Update the module docstring and `_land_late_coordination_commits`'s to describe both windows.
Keep the #5570 commit message; only the console line distinguishes the windows.

## Definition of Done

- `uv run pytest tests/coordination/test_projection_teardown.py -q` green, with T001/T002 red
  before the change.
- The clean-run positive controls (`test_unmoved_coord_branch_is_still_deleted_and_flattened`,
  `test_teardown_proceeds_when_gate_passes`) unchanged and green.
- No change to `bookkeeping_projection.py`, to the resume base, or to the assertion.
