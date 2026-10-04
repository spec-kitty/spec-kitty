---
work_package_id: WP02
title: Shell-owned runtime-annotation emit
dependencies: []
requirement_refs:
- FR-004
- C-001
planning_base_branch: claude/move-task-degod-slice-2
merge_target_branch: claude/move-task-degod-slice-2
branch_strategy: Planning artifacts for this mission were generated on claude/move-task-degod-slice-2. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/move-task-degod-slice-2 unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/status_transition.py
create_intent:
- tests/specify_cli/coordination/test_emit_runtime_annotation.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- tests/specify_cli/coordination/test_emit_runtime_annotation.py
- tests/integration/test_owned_checkout_mark_status.py
- tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py
- tests/git_ops/test_atomic_status_commits_unit.py
- tests/specify_cli/orchestrator_api/test_commands_fail_closed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Shell-owned runtime-annotation emit

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it. Read `.kittify/charter/charter.md`, then `kitty-specs/move-task-executor-seam-lanes-01M43FAG/spec.md` and `plan.md`.

## Objective

`_mt_emit_runtime_state` in `tasks_move_task.py` (~:2026-2160) and `tasks_mark_status.py` (~:377-420) each choose an inner-state emitter. Move that choice behind one coordination-shell helper.

## Precedence (must be preserved exactly)

1. `owned is not None` → `emit_inner_state_changed_transactional(..., owned=owned)` (#3866).
2. Otherwise, `auto_commit` truthy → the transactional emitter.
3. Otherwise → the plain `emit_inner_state_changed`. It does NO worktree or transaction resolution before branching (#3460).

Read both call sites first and confirm the exact argument lists. The helper forwards keyword arguments unchanged; it must not re-derive anything.

## Subtasks

- **T004** (signature, post-tasks squad fold):
  - Use `emit_runtime_annotation(*, owned, auto_commit, operation: str | None = None, **emit_kwargs)`.
  - `operation` and `owned` go ONLY to the transactional emitter, never to `emit_inner_state_changed`, which has no `operation` parameter (`status/emit.py:1182`).
  - Return the chosen emitter's result. The plain emitter may return None, so mark-status keeps appending `applied_event_ids`/`applied_wps` only when `owned is not None`.
  - Lazy-import the plain emitter at call time with `from specify_cli.status import emit_inner_state_changed`, so the existing `specify_cli.status.emit_inner_state_changed` patches keep intercepting.
  - Call the transactional emitter as `status_transition`'s module global, because tests patch `status_transition.emit_inner_state_changed_transactional`.

  Original wording: Add `emit_runtime_annotation(*, owned, auto_commit, **emit_kwargs)` to `src/specify_cli/coordination/status_transition.py`. Import the emitters lazily inside the function, so the `status` → `coordination` import direction is unchanged. Return whatever the chosen emitter returns.
  - Check how tests patch the emitters today. They may patch `tasks_mark_status.emit_inner_state_changed_transactional` or similar. If so, keep mark-status calling through names those patches can still intercept, OR repoint those patches to the helper's lazy import target. Prefer repointing, and list the files you change in the commit message. Do NOT edit `tasks_move_task.py`; WP03 adopts the helper there.
- **T005**: Adopt the helper in `tasks_mark_status.py`. Its current choice is owned → transactional, else plain, which equals `auto_commit=False`. Behaviour must be identical.
- **T006**: Add `tests/specify_cli/coordination/test_emit_runtime_annotation.py`:
  - all three branches, with fake emitters patched at the lazy import target;
  - an assertion that the plain branch never calls the transactional emitter and never touches `BookkeepingTransaction` / worktree resolution (patch those to raise);
  - an assertion that `owned=` is forwarded;
  - an assertion that the plain branch receives no `operation` or `owned` kwarg.

## Validation

Run `.venv/bin/python -m pytest -q tests/specify_cli/coordination tests/specify_cli/cli/commands/agent -k "mark_status or emit_runtime_annotation"` plus every test file that references `tasks_mark_status` (`grep -rl tasks_mark_status tests`). Run ruff, format and mypy. Commit citing #5629.
