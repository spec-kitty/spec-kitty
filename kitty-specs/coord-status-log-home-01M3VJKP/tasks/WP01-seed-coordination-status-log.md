---
work_package_id: WP01
title: Seed the coordination status log at create
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: claude/project-thread-oymt0g
merge_target_branch: claude/project-thread-oymt0g
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-oymt0g. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-oymt0g unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1
history:
- at: '2026-10-01T11:20:00Z'
  actor: claude
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/core/mission_creation.py
create_intent:
- tests/core/test_mission_create_coord_status_seed.py
- tests/e2e/test_coord_status_off_target_lifecycle.py
- tests/specify_cli/cli/commands/agent/test_finalize_lifecycle_event_dir.py
execution_mode: code_change
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/status/bootstrap.py
- tests/status/test_bootstrap.py
- tests/specify_cli/cli/commands/agent/test_finalize_lifecycle_event_dir.py
- tests/core/test_mission_creation_decomposition.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/core/test_mission_create_coord_status_seed.py
- tests/e2e/test_coord_status_off_target_lifecycle.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 -- Seed the coordination status log at create

## Goal

Turn `tests/core/test_mission_create_coord_status_placement.py` (PR #5518) green by giving a coordination mission's status log its coordination home at create, and prove the later lifecycle legs stay off the target branch.

## Subtasks

- **T001** In `_scaffold_mission_dir`, keep `status.events.jsonl` out of `scaffold_paths` (and do not touch a primary copy) when `routes_through_coordination(topology)` and the create is not owned. Hoist the repeated literal to a module constant.
- **T002** After `_build_create_meta` mints the coordination branch, call `materialize_coord_surface_for_write`, create the coordination mission dir, emit `MissionCreated` / `SpecifyStarted` there, and after the target scaffold commit commit the log on the coordination branch with `safe_commit` and `resolve_placement_only(STATUS_STATE)`. When no local coordination branch exists, fall back to the primary home and include the log in the scaffold commit. Hosted fanout reads the seeded log.
- **T003** In `_restore_git_state_after_failed_create`, for each orphan coordination branch, copy its worktree's status logs into retained primary mission dirs, then `git worktree remove --force` before `git branch -D`.
- **T004** Re-pin `test_scaffold_commit_is_single_commit_excluding_spec_md` and `test_status_log_holds_exactly_created_and_specify_started` per topology, and the four fanout-boundary tests so they read the log from its committed home. Add focused tests for the fallback and rollback helpers.
- **T005** Add `tests/e2e/test_coord_status_off_target_lifecycle.py` (marks `e2e`, `slow`, `git_repo`): create → setup-plan → finalize-tasks → record-analysis → implement → move-task, asserting no status byte-set on the target branch after each step and no status log in the primary mission dir. Show it red on `main`.
- **T007** (added during implementation) Route `finalize-tasks` lifecycle events (`TasksStarted` / `WPCreated` / `TasksCompleted`) to the canonical status surface, and skip bootstrap's final `materialize` when the primary dir holds no event log, so a coord mission's primary dir never gains a stray status byte-set (FR-007).
- **T006** Run the targeted set and `ruff check`, `ruff format --check`, `mypy` on the changed files.

## Validation (targeted test surface)

- `tests/core/test_mission_create_coord_status_placement.py`
- `tests/core -k creat` (all mission-create files)
- `tests/core/test_mission_create_coord_status_seed.py`
- `tests/e2e/test_coord_status_off_target_lifecycle.py` (by name)
- coordination surface: `tests/coordination/test_surface_resolver*.py`, `tests/integration/test_coord_loop_*.py`
- `tests/architectural/test_no_legacy_terminology.py`
