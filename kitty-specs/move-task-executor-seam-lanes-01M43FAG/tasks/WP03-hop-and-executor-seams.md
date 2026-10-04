---
work_package_id: WP03
title: Hop and executor seam modules
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-003
- C-004
planning_base_branch: claude/move-task-degod-slice-2
merge_target_branch: claude/move-task-degod-slice-2
branch_strategy: Planning artifacts for this mission were generated on claude/move-task-degod-slice-2. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/move-task-degod-slice-2 unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_hops.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_executor.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- src/specify_cli/cli/commands/agent/tasks.py
- tests/architectural/untrusted_path_audit/inventory.md
- tests/architectural/test_status_events_writes_gate.py
- tests/architectural/test_exemption_registry_ratchet.py
- tests/acceptance/test_accept_gate_rejection_cycle.py
- tests/integration/test_2939_move_task_clean_tree_after_rejection.py
- tests/integration/test_review_durability_matrix.py
- tests/integration/review/test_verdict_save_topologies.py
- tests/review/test_cycle.py
- tests/specify_cli/cli/commands/agent/test_claim_event_source.py
- tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py
- tests/specify_cli/cli/commands/agent/test_move_task_durability.py
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_signal.py
- tests/specify_cli/cli/commands/agent/test_move_task_orchestration.py
- tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_authority_staging.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_hops.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_executor.py
- tests/specify_cli/status/test_execution_mode_stamp_paths.py
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
- tests/status/test_work_package_lifecycle.py
- tests/status/test_cutover_eligibility.py
- tests/consolidation/test_merge_canceled_wp.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_no_read_side_bypass.py
- tests/architectural/test_untrusted_path_containment.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Hop and executor seam modules

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it. Read `.kittify/charter/charter.md`, then `kitty-specs/move-task-executor-seam-lanes-01M43FAG/spec.md` and `plan.md`.

## Objective

Slice 2 of #5629. Follow the slice-1 pattern exactly (commit "refactor(move-task): extract the transition-gate family into its own seam"; see `tasks_move_task_gates.py` and its module docstring):

- Bodies move VERBATIM. Only import plumbing changes.
- `tasks_move_task` re-imports every moved symbol in the `name as name` form, so `tasks_move_task.<name>` and `tasks.<name>` resolve by identity.
- The new modules import `_MoveTaskState` under `TYPE_CHECKING` only. Any runtime need for a `tasks_move_task` name is a lazy in-function import. NO module-scope import of `tasks_move_task`.
- Keep every existing `from specify_cli.cli.commands.agent import tasks as _tasks` lazy bridge and every `_tasks.<name>(...)` call. Tests patch `tasks.<name>` for `_mt_finalize_plan`, `_mt_hop_review_result`, `_mt_execute`, `_mt_resolve_targets` and `_mt_current_event_lane`, and expect interception.

## Symbol → module map (from spec.md)

- **`tasks_move_task_hops.py`**: `_binding_role_for_lane`, `_mt_hop_review_ref`, `_mt_hop_reason_source`, `_mt_hop_policy_metadata`, `_mt_approval_policy_metadata`, `_mt_hop_actor`, `_mt_hop_review_result`, `_mt_plan_review_result`, `_mt_reassignment_binding_fields`, `_build_claim_review_override`, `_mt_shell_pid_baseline`
- **`tasks_move_task_executor.py`**: `_mt_finalize_plan`, `_mt_persist_rejection_cycle`, `_mt_emit_transitions`, `_mt_emit_runtime_state`, `_mt_persist_wp_file`, `_mt_release_review_lock`, `_mt_execute`, `_RollbackResetSummary`, `_mt_build_rollback_summary`, `_mt_rollback_subtasks_reset`
- **Stay in `tasks_move_task.py`**: `_mt_apply_rollback_signal`, `_mt_rollback_signal_lines`, and everything else.

## Subtasks

- **Before T007**: record `grep -rn 'validate_transition(' src | wc -l` in `traces/approach.md` (C-002 baseline).
- **T007**: Create the hops module. A script approach works well: parse with `ast`, cut the top-level nodes by line range, copy the import block, then let `ruff check --select F401 --fix` prune it. Add a module docstring in the slice-1 style.
- **T008**: Create the executor module the same way.
  - Some executor functions call hop builders directly (not via `_tasks.`). Import those from the hops module.
  - A call that went through `_tasks.<name>` stays that way.
  - If a moved body references a module-level constant in `tasks_move_task`, either move the constant (if only moved code uses it) or lazy-import it.
- **T009**: In `_mt_emit_runtime_state`, replace ONLY the transactional-vs-plain selection with a call to `emit_runtime_annotation(owned=..., auto_commit=st.resolved_auto_commit, ...)` from `specify_cli.coordination.status_transition` (added by WP02). Arguments must be identical. Check that tests patching the emitters still intercept, and repoint them if needed.
- **T010**:
  - Re-home every `patch.object(tasks_move_task, "<moved>")`, `monkeypatch.setattr(tasks_move_task, ...)` and `patch("...tasks_move_task.<moved>")` that intercepts a call made INSIDE the moved family. Point it at the module where the call now happens.
  - A patch on `tasks.<name>` that is called via `_tasks.` needs no change.
  - Watch for setattr on names that are now dead on the old module: they stay green but stop intercepting (spec edge case). Verify each re-home with a quick run.
  - Update `tests/architectural/test_status_events_writes_gate.py`'s module allow-list, the exemption registry and `untrusted_path_audit/inventory.md` rows, moving entries rather than adding allowances (C-004).
  - Append `tasks_move_task_hops` and `tasks_move_task_executor` to `MOVE_TASK_SEAMS` in `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py`. That file is owned by WP01 and was created there; this one-line append is the only edit. Note it in the commit.
  - Add focused tests:
    - `test_tasks_move_task_hops.py`: table tests for `_binding_role_for_lane` and `_mt_hop_review_ref` with plain inputs;
    - `test_tasks_move_task_executor.py`: the `_mt_release_review_lock` no-op when no lock is held, and the `_mt_build_rollback_summary` happy path with a fake `ports.fs`. Read the bodies to pick realistic inputs.
    - For US2, add `test_execute_reverts_verdict_on_emit_failure` and `test_review_lock_released_after_emits`, using fake ports. Alternatively, cite the existing tests that cover them by node id in the commit message after re-homing.
    - Add a test asserting each moved symbol's `__module__` equals its new seam module.
    - Owned files that end up needing no edit are listed in the commit message.

## Acceptance

- `wc -l src/specify_cli/cli/commands/agent/tasks_move_task.py` ≤ 2050.
- `grep -rn "validate_transition(" src | wc -l` is unchanged from before (record both numbers).
- Run `.venv/bin/python -m pytest -q -n 8 --dist loadfile tests/specify_cli/cli/commands/agent tests/review tests/status tests/cli tests/tasks tests/specify_cli/coordination tests/specify_cli/status tests/integration/test_2939_move_task_clean_tree_after_rejection.py tests/integration/test_review_durability_matrix.py tests/integration/review tests/acceptance/test_accept_gate_rejection_cycle.py`. `tests/cli/commands/test_charter_io.py::test_resolve_charter_path_raises_when_directory_not_readable` fails on the base too (root container), so ignore it.
- Also run the architectural gates: `tests/architectural/test_untrusted_path_containment.py test_status_events_writes_gate.py test_exemption_registry_ratchet.py test_no_write_side_rederivation.py test_no_read_side_bypass.py test_timing_coverage_invariant.py test_2093_authority_invariant.py test_layer_rules.py test_coverage_breadth.py`.
- ruff check, `ruff format --check --force-exclude` and mypy on the touched src files.
- One commit per subtask is fine. Cite #5629 in each.
