---
work_package_id: WP01
title: Derived compat keysets and generalised seam guard
dependencies: []
requirement_refs:
- FR-005
- FR-006
planning_base_branch: claude/move-task-degod-slice-2
merge_target_branch: claude/move-task-degod-slice-2
branch_strategy: Planning artifacts for this mission were generated on claude/move-task-degod-slice-2. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/move-task-degod-slice-2 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-executor-seam-lanes-01M43FAG
base_commit: c66ee0b78cd6ab84d9a66cf5f1c975157688a357
created_at: '2026-10-04T12:49:17.825716+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_gates_seam.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Derived compat keysets and generalised seam guard

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it. Read `.kittify/charter/charter.md`, then `kitty-specs/move-task-executor-seam-lanes-01M43FAG/spec.md` and `plan.md`.

## Objective

DIRECTIVE_041 and the development-assist test-cleanup procedure apply here. `test_tasks_compat_surface.py` hand-lists every seam symbol (`_TASKS_MOVE_TASK` and friends) and carries count-ratchet comments, so every behaviour-neutral move turns it red. Make the guard derive its keysets instead, keeping the real invariant: each `tasks.<name>` re-export is the seam module's object by identity, not a copy.

## Subtasks

- **T001**: Replace the per-seam tuples with a derivation. For each seam module in `_SEAM_MODULES`, take its native definitions: callables whose `__module__` equals the module name, plus the `_EXTRA_NON_CALLABLE_NATIVE_DEFS` constants. Only include names that `tasks` actually exposes (`hasattr(tasks, name)`).
  - Keep the identity test (`tasks.<sym> is seam.<sym>`), parametrised over the derived set.
  - Keep a disjointness check (no symbol natively defined in two seams).
  - Keep a floor check: every seam contributes at least one symbol.
  - Remove the "75 → 76 → 81" count comments. Keep `test_seam_maps_agree` as a contract on the seam set.
  - Names native to a seam but NOT exposed on `tasks` are allowed. Record that decision in a comment: the compat surface is "whatever `tasks` re-exports must be the seam's object".
- **T002**: Generalise `test_tasks_move_task_gates_seam.py` into `test_tasks_move_task_seams.py`, parametrised over a `MOVE_TASK_SEAMS` list (currently `[tasks_move_task_gates]`). WP03 will append the hops and executor modules.
  - Per seam: identity re-export on `tasks_move_task`, no native shadow in `tasks_move_task`, and no module-scope `ImportFrom` of `tasks_move_task`.
  - Delete the old file.
- **T003**: Negative control. Build a throwaway module object holding a copy of a function (same name, a different object) and assert that the identity predicate the guard uses reports it. Factor the predicate into a small helper so the control exercises the real code.

## Validation

`.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py`. Run ruff check, `ruff format --check --force-exclude` and mypy on the touched files. Commit with a message citing #5629 and DIRECTIVE_041.
