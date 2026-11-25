---
work_package_id: WP01
title: Accurate, recoverable stale refusal
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: fix/7755-stale-lane-auto-rebase-recovery
merge_target_branch: fix/7755-stale-lane-auto-rebase-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/7755-stale-lane-auto-rebase-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7755-stale-lane-auto-rebase-recovery unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-11-20T18:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/consolidation/test_7755_stale_sibling_lane_recovery.py
- tests/consolidation/stale_sibling_lane_support.py
- tests/lanes/test_stale_sibling_lanes.py
- docs/changelog/unreleased/7780.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/stale_check.py
- src/specify_cli/lanes/consolidation.py
- tests/consolidation/test_p0_repro_7755_auto_rebase_halt_reason.py
- tests/consolidation/test_7755_stale_sibling_lane_recovery.py
- tests/consolidation/stale_sibling_lane_support.py
- tests/lanes/test_stale_remediation_cli_command.py
- tests/lanes/test_stale_check.py
- tests/lanes/test_stale_sibling_lanes.py
- tests/integration/test_consolidate_upgraded_mission_recovery.py
- CLAUDE.md
- docs/changelog/unreleased/7780.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Accurate, recoverable stale refusal

Profile: `python-pedro` (implementer). Read `plan.md` (Option A, Design) and `research/code-grounding.md` first.

## Objective

Make the stale-lane refusal at `consolidate` recoverable without touching rollback (C-001): surface the in-run auto-rebase halt reason (FR-001), name sibling lanes and their branches (FR-002), redirect the remedy to the sibling branch (FR-003), start the code-lane remedy with the reopen step for an approved work package (FR-004, #7754), and prove recovery through the CLI (FR-005). Remove the `p0_repro` marker (FR-006).

## Subtasks

- **T001** Red-first. Remove `@pytest.mark.p0_repro(issue=7755)` from `tests/consolidation/test_p0_repro_7755_auto_rebase_halt_reason.py`; add `tests/consolidation/test_7755_stale_sibling_lane_recovery.py` (+ fixture module) driving `spec-kitty consolidate`, following the printed remedy and re-running. Record red on pre-fix sources.
- **T002** `src/specify_cli/lanes/stale_check.py`: `SiblingLane`, `find_sibling_lanes` (kernel.git probes, ≤ 2 per candidate), `refine_stale_result`, remedy text.
- **T003** `src/specify_cli/lanes/consolidation.py`: `_try_auto_rebase_if_stale` returns the halt reason; candidates from the manifest via `lane_branch_name`; refine the result. No new `subprocess.run`.
- **T004** Unit tests; update pinned texts in `tests/lanes/` and `tests/integration/test_consolidate_upgraded_mission_recovery.py`.
- **T005** CLAUDE.md sentence, `docs/changelog/unreleased/7780.fixed.md`, gates (`test_single_rollback_authority.py`, `test_merge_pipeline_ratchets.py`, `test_no_worktree_name_guess.py`, `test_marker_job_completeness.py`, `test_issue_named_test_census.py`, `test_no_legacy_terminology.py`), ruff, mypy.

## Validation (targeted test surface)

`make test-fast`; `tests/consolidation/`; `tests/lanes/`; `tests/integration/test_consolidate_upgraded_mission_recovery.py`; the gate files listed in T005.
