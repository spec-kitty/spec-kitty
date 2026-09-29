---
work_package_id: WP01
title: Implementer of record resumes after a rework verdict
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: ccr-806fafb9-5qycab
merge_target_branch: ccr-806fafb9-5qycab
branch_strategy: Planning artifacts for this mission were generated on ccr-806fafb9-5qycab. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-806fafb9-5qycab unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-rework-resume-01M3QA1X
base_commit: f42909e4e948954537043f3add16eb49c07f7a96
created_at: '2026-09-29T19:37:33.445887+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-09-29T20:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/status/work_package_lifecycle.py
- src/specify_cli/status/review_roles.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py
- tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py
- tests/status/test_work_package_lifecycle.py
- tests/unit/status/test_review_roles.py
- docs/changelog/CHANGELOG.md
- docs/api/orchestrator-api.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Implementer of record resumes after a rework verdict

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

After a reviewer rejects a WP `in_review → in_progress` (unforced, with a `review_ref`),
`spec-kitty agent action implement WP01 --agent <implementer>` must exit 0 without `--force`.
An unrelated agent stays refused; a failed read of the implementer of record fails closed.
See `spec.md` (FR-001..FR-004) and `research.md` (R-01 reproduction, R-03 squad dispositions).

## Subtasks

- **T001 (red-first, commit first)** — `test_rework_unforced_loop.py::test_action_implement_resumes_after_in_progress_rejection`
  (marked `regression` until the fix lands) and
  `test_rework_guard_ratchets.py::test_unrelated_agent_refused_by_action_implement_after_in_progress_rejection`.
  The first is RED on the planning base (exit 1, `WorkPackageClaimConflict`); the second is a ratchet (green on base).
- **T002** — add `is_latest_implementer(latest: str | None, actor: object) -> bool` to
  `src/specify_cli/status/review_roles.py` (False for None / generic latest; else `_actor_key` equality).
  Refactor `tasks_transition_core._ownership_role_allowance` and `_implementer_arm` onto it without changing behaviour.
- **T003** — in `start_implementation_status`, IN_PROGRESS arm: when the slot-occupant check fails,
  call an extracted helper that lazily imports `review_roles`, reads the events with
  `coordination.status_transition.read_events_transactional` (same identity as the current-state read),
  and returns `is_latest_implementer(latest_implementer_actor(events, wp_id), actor)`; any exception → False.
  Return the existing no-op result with `claimed_by` set to the admitted requester. No lane event.
- **T004** — unit tests for every new branch; a real-CLI fail-closed test (patch
  `coordination.status_transition.read_events_transactional` to raise → refused; restored → admitted);
  remove the `regression` marker once green.
- **T005** — `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (bold impact-first lead with `(#5377)`, before → after);
  one line on `WP_ALREADY_CLAIMED` in `docs/api/orchestrator-api.md`.

## Validation (targeted test surface)

```
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py \
  tests/specify_cli/cli/commands/agent/test_rework_guard_ratchets.py \
  tests/specify_cli/cli/commands/agent/test_rework_override_classification.py \
  tests/status/test_work_package_lifecycle.py tests/unit/status/test_review_roles.py \
  tests/status/test_actor_identity_reconciliation_4665.py \
  tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py \
  tests/agent/test_implement_command.py -q
make test-fast
ruff check . && ruff format --check . && mypy --strict <changed modules>
```

## Activity Log
