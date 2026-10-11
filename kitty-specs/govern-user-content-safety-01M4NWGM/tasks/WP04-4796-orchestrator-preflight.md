---
work_package_id: WP04
title: '#4796 orchestrator-api pre-mutation preflight parity'
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- SC-003
- NFR-001
- NFR-002
planning_base_branch: fix/5964-5434-4796-govern-user-content
merge_target_branch: fix/5964-5434-4796-govern-user-content
branch_strategy: Planning artifacts for this mission were generated on fix/5964-5434-4796-govern-user-content. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5964-5434-4796-govern-user-content unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-govern-user-content-safety-01M4NWGM
base_commit: 712caec82fa7fa265cca177d3b978ecf168806b9
created_at: '2026-10-11T17:37:46.240341+00:00'
subtasks:
- T013
- T014
phase: Phase 2 - Fixes
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent: []
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/specify_cli/orchestrator_api/consolidation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4796'
---
# Work Package Prompt: WP04 – #4796 orchestrator-api pre-mutation preflight parity

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/spk-charter-profile-load`, then `spec-kitty charter context --action implement --json`.

## Problem (grounded at HEAD 3498b426)
`src/specify_cli/orchestrator_api/consolidation.py::_execute_lane_merge` (def ~:524) runs its pre-checks (`_build_merge_preflight` ~:820 git-preflight only; `_origin_gate`; `_refuse_protected_status_target`; `evaluate_merge_gates`; `_refuse_post_approval_lane_content`) with NO lane-worktree dirty check, then MUTATES: `consolidate_lane_into_mission` per lane (~:588), `integrate_mission_into_target` (~:593), `_mark_wp_merged_done` (~:602), `git push origin <target>` (~:606). Only at `_apply_lane_merge_cleanup` (~:611 → `guarded_worktree_remove` ~:425 → `git/destructive_guard.py::assert_worktree_clean` :280) does the FIRST lane-worktree dirty check run, post-mutation + post-push. The refusal is enveloped `PREFLIGHT_FAILED` (`_fail_from_destructive_op_refused` ~:168/:195) for a merge that COMPLETED. WP01 `test_consolidate_mission_premutation_timing.py` is RED on the timing (items 2-4).

## Approach (C-001 reuse; C-002 minimal)
Hoist a pre-mutation safety preflight into `_execute_lane_merge` AFTER retention resolution (`_resolve_lane_merge_retention` ~:566-571) and BEFORE the first `consolidate_lane_into_mission` (~:588). Reuse the CLI parity target `src/specify_cli/consolidation/entry_preflight.py::_pre_mutation_safety_preflight` (~:111), which already takes `lanes_manifest`, `remove_worktree`, `teardown_coordination` and iterates lane worktrees calling `assert_worktree_clean(..., treat_untracked_as_dirty=True)` (leg 2, ~:182-196), plus the on-target/clean primary (leg 1) and coord-worktree (leg 3) legs. Gate on the SAME resolved `remove_worktree`/`teardown_coordination` as cleanup so behaviour matches. Either call it directly or extract its lane-worktree leg — do NOT write a new ad-hoc check. The raised `DestructiveOpRefused` is still caught at ~:859 and enveloped `PREFLIGHT_FAILED` — now truthfully pre-mutation. The planning-only subpath already routes through the CLI preflight; leave it.

## Acceptance
- WP01 `test_consolidate_mission_premutation_timing.py` → GREEN: dirty lane worktree refuses `PREFLIGHT_FAILED`/`MERGE_UNSAFE_WORKTREE_DIRTY` with target ref unchanged, no done-stamp, no push (NFR-001/002 on the orchestrator path).
- A clean lane worktree merges exactly as before (no behaviour change on the happy path).
- Existing `tests/orchestrator_api/test_merge_mission_destructive_refusal.py` and `test_worktree_cleanup_guard.py` still pass.

## Validation
`PWHEADLESS=1 .venv/bin/python -m pytest tests/orchestrator_api/ -q` (targeted dir); `make test-fast`. `ruff`/`mypy --strict` clean; no suppressions. Record counts.
