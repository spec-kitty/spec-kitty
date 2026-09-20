---
work_package_id: WP02
title: '#4758 move-task planned-boundary guard'
dependencies: []
requirement_refs:
- FR-002
- FR-006
- C-003
planning_base_branch: fix/canonical-state-recovery
merge_target_branch: fix/canonical-state-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/canonical-state-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/canonical-state-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-canonical-state-recovery-01M2ZE3D
base_commit: c3dade0edc7ad2c872e4157a834fdb251098502d
created_at: '2026-09-20T13:31:38.368730+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 1 - Guard
history:
- at: '2026-09-20T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/cli/test_move_task_planned_guard.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/cli/test_move_task_planned_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4758'
---

# Work Package Prompt: WP02 – #4758 move-task planned-boundary guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Add the defense-in-depth half of #4758: `move-task` must refuse to move a WP **out of `planned`** when `lanes.json` is absent — closing the escape that lets a WP leave `planned` into an unrecoverable state even if the minting fix (WP01) regresses.

**Done when:**
- `move-task --to doing` (and any transition out of `planned`) on a mission with no `lanes.json` **refuses** with a message that names `spec-kitty doctor mission-state --fix --mission <slug>` (FR-002, FR-006).
- A legitimate `move-task` on a mission that *has* `lanes.json` is completely unaffected (no new refusal).
- The protected-branch rollback refusal (`tasks_transition_core.py:407` `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH`) keeps its semantics but its message names the recovery path (FR-006).

## Context & Constraints

- Grounded sites (verify via Read): `tasks_move_task.py:638-642` (`require_lanes_json` already imported/used inside `_mt_resolve_owned_review_base` only — the guard must fire on the `planned`→non-`planned` transition, which is currently ungated); `tasks_transition_core.py:407-423` (protected-branch refusal + its guard).
- Do **NOT** touch attribution logic (`tasks_move_task.py:2891`/`:2970`) — that is WP04's read-root fix; this WP only adds the lanes-presence guard. Do NOT touch `status/models.py`.
- The guard uses the existing `require_lanes_json`/`read_lanes_json` accessor — do not re-author lane resolution.
- ATDD red-first (C-003); ruff/mypy clean; complexity ≤15.

## Subtasks

### T007 — Red: the escape
Add `tests/cli/test_move_task_planned_guard.py` (`pytest.mark.regression`, pinned #4758): on a mission with no `lanes.json`, assert `move-task WP01 --to doing` currently SUCCEEDS (the bug). RED against the desired refusal.

### T008 — Add the guard
Refuse a transition out of `planned` when `lanes.json` is absent; the message names `doctor mission-state --fix --mission <slug>`. Reword the protected-branch refusal to name the recovery too.

### T009 — Green + no false positives
T007's desired refusal passes; add a positive test that `move-task` with `lanes.json` present still works. 

### T010 — Blast radius
Run `tests/cli/` move-task coverage (narrow, file-scoped); record counts in `traces/test-evidence.md`.
