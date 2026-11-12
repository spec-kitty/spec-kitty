---
work_package_id: WP04
title: Recorded and narrowable rollback subtask reset
dependencies: []
requirement_refs:
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- C-002
- SC-004
subtasks:
- T015
- T016
- T017
- T018
- T019
phase: 'Phase 2 - #7582'
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_signal.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP04 – Recorded and narrowable rollback subtask reset

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role `implementer`) before reading on.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log and address every item.

---

## Objectives & Success Criteria

This WP delivers FR-011 to FR-015 (#7582). The operator ruled on 2026-11-12 for a recorded reset with narrowing (`decisions/`, `subtask_reset_policy`).

1. **FR-011.** Every `move-task --to planned` (rejection, reopen, unclaim) records the reset on the PLANNED transition event:

   ```json
   "policy_metadata": {"rollback_reset": {"scope": "full|narrowed", "reset": [...], "previously_completed": [...], "reason": "..."}}
   ```

   - It merges with any `policy_metadata` the pipeline stamps (e.g. `lane_head`). Never overwrite those.
   - `reason` is the operator `--note`/`--reason` when given. Otherwise it is derived from the transition: `"rollback to planned: <from_lane> -> planned"` plus the review ref when present.
2. **FR-012.** `--reset-subtasks T002[,T003]` resets only the named ids. The other subtasks keep their state.
3. **FR-013.** Refused **before any write** (exit non-zero, nothing persisted) when:
   - an id is not on the WP roster;
   - no `--note`/`--reason` is given;
   - `--to` is not `planned`.
   Use a typed error and message in the same style as other move-task refusals.
4. **FR-014.** Without the flag, the full reset is unchanged (#2513). The `for_review` subtask gate still blocks on any reset subtask.
5. **FR-015.**
   - The human line and the JSON output name the scope and the reason.
   - New JSON keys: `subtasks_reset_scope`, `subtasks_reset_reason`.
   - The existing `subtasks_reset_*` keys are unchanged.

## Context & Constraints

- **Read first:**
  - `plan.md` IC-04
  - `research.md` R-6
  - `data-model.md` (rollback_reset)
  - `contracts/rollback-reset-record.md`
  - `research/code-grounding.md` §2 (all file:line citations)
- **Current flow:**
  - `_mt_execute` (`tasks_move_task_executor.py:594`) → `_mt_emit_runtime_state` → at `:520-521`, `if st.target_lane == Lane.PLANNED: fields.update(_build_claim_review_override(st, ports))` → `_build_claim_review_override` (`tasks_move_task_hops.py:394-456`) → `_mt_rollback_subtasks_reset` (`executor.py:386-416`).
  - The annotation is written AFTER the lane transition.
  - The hop's `policy_metadata` comes from `_mt_hop_policy_metadata` (`hops.py:269-291`), which returns None for PLANNED today.
  - Summary: `_RollbackResetSummary` / `_mt_build_rollback_summary` (`executor.py:330-383`); output in `tasks_move_task.py:1872-1940`.
- **`--reason` already exists** as an alias of `--note` (last one on the command line wins). Read the resolved note value. Do not add a new reason flag.
- **No event-contract or library change.** `policy_metadata` is a free dict in `spec_kitty_events`. The `InnerStateChanged` delta keeps the per-id lanes as the single authority for subtask state.
- **Gates:**
  - `tests/architectural/test_status_events_writes_gate.py`
  - `test_innerstatechanged_invariants.py`
  - `test_no_write_side_rederivation.py`
  - `test_2093_authority_invariant.py`
  - `test_exemption_registry_ratchet.py`
  - `test_dossier_sha_provenance.py` (it gates SHA-valued policy keys; `rollback_reset` carries none)
- **Complexity.** `_do_move_task` (`tasks_move_task.py`) is at 15, so put the validation in a helper.
- **Test location.** `tests/specify_cli/cli/commands` is outside the per-PR CI matrix (nightly only), so run it explicitly and record the counts.
- **Out of scope.** The assignee rebind on `--to planned --agent <reviewer>` (startup-assess F-3) is a separate defect. Do not change `--agent` semantics.

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`.
- Run `spec-kitty agent action implement WP04 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T015 – Red-first CLI tests (commit first)

- **File**: `tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py`.
- **Harness**: reuse `_build_in_review_repo` and `_move_task_cli` from `test_tasks_move_task_cli_4899.py` (import them, or copy them into a shared helper only if the import is awkward). Extend the roster to `[T001, T002]`, both done, via `mark-status` events or the same seeding approach.
- **Cells**:
  1. Full rejection: `--to planned --review-feedback-file fb.md`.
     - Both subtasks reset.
     - The PLANNED transition event's `policy_metadata.rollback_reset == {"scope": "full", "reset": ["T001", "T002"], "previously_completed": ["T001", "T002"], "reason": <derived>}`.
     - Any `lane_head` is still present.
  2. Narrowed rejection: `--reset-subtasks T002 --note "T002 regressed"`.
     - The snapshot shows `T001` done and `T002` planned.
     - The record has `scope: narrowed`, `reset: [T002]`, `previously_completed: [T002]`, `reason: "T002 regressed"`.
  3. Unknown id → refused, exit ≠ 0, the event log is byte-identical before and after.
  4. No reason → refused, same check.
  5. `--to for_review --reset-subtasks T001` → refused.
  6. After the narrowed rejection, re-claim then `--to for_review`: the subtask gate refuses until T002 is marked done (FR-014 positive control).
  7. JSON output carries `subtasks_reset_scope` and `subtasks_reset_reason`.
  8. A `skipped` subtask is never in `reset` (adapt the existing #3578 cell).
- Commit alone: `test(move-task): red-first rollback reset record and narrowing (#7582)`.

### Subtask T016 – Option and validation

- `tasks.py` `move_task`:
  - add `reset_subtasks: Annotated[str | None, typer.Option("--reset-subtasks", help="Comma-separated subtask ids to reset on a rollback to planned (default: every subtask). Requires --note/--reason.")] = None`;
  - thread it into the move-task state (the dataclass near `tasks_move_task.py:301`).
- Add a helper, `_mt_validate_reset_subtasks(st, roster) -> tuple[str, ...] | None` (or one raising the typed refusal). It:
  - parses and dedups the ids;
  - checks every id against the roster (`core.subtask_rows.authored_subtask_roster`, the same reader `_mt_rollback_subtasks_reset` uses);
  - requires a non-empty note;
  - requires the target lane to be `planned`.
- Call it before any write (before `_mt_execute`).

### Subtask T017 – Record on the PLANNED hop

- Compute the reset map and the summary BEFORE the hop. The pre-reset snapshot is unchanged by the transition, so computing it earlier is safe.
- Thread `rollback_reset` into the PLANNED hop's `policy_metadata` through `_mt_hop_policy_metadata`, or the place the hop's policy dict is assembled, so the transition pipeline merges it with its own stamps (`transition_pipeline.py:235-244` stamps `lane_head`).
- Verify the merge order: never drop `lane_head` or `wp_window`.
- `reason` comes from the operator note, else the derived text (hoist the literal prefix into a constant).
- `previously_completed` uses the existing summary logic (`_mt_build_rollback_summary`), restricted to the ids in `reset`.

### Subtask T018 – Narrow the annotation

- `_mt_rollback_subtasks_reset` takes an optional `only: frozenset[str] | None`. With `only`, it maps just those ids to `Lane.PLANNED`; skipped subtasks are still excluded.
- The full default is unchanged.

### Subtask T019 – Announcement and cutover pin

- Extend `_RollbackResetSummary` with `scope` and `reason`.
- Update the human line, e.g. `↺ Reset 1 of 2 subtask(s) to planned (narrowed: T002 regressed)`. Keep the existing wording for the full case and append `(full reset: <reason>)`.
- Add the JSON keys.
- Update `test_move_task_rollback_signal.py` only where its existing expectations must grow. Never delete assertions.
- Add a test pinning that `status/cutover_eligibility._policy_metadata_carries_runtime_evidence` (`:97-122`) returns True for a PLANNED event carrying only `rollback_reset` plus `lane_head`. This documents that the key counts as runtime evidence. Research R-6 says that is harmless; state why in the test docstring.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py tests/specify_cli/cli/commands/agent/test_move_task_rollback_signal.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py -q -p no:cacheprovider
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent -q -n 4 --dist loadfile -k "move_task or mark_status or subtask"
.venv/bin/python -m pytest tests/status -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_status_events_writes_gate.py tests/architectural/test_innerstatechanged_invariants.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_2093_authority_invariant.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_dossier_sha_provenance.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/agent && uv run --frozen ruff format --check --force-exclude <changed files> && uv run --frozen mypy <changed src files>
```

## Risks & Mitigations

- **Losing `lane_head` on merge.** Explicit test cell 1.
- **Write-before-validate.** Cells 3 to 5 assert an unchanged event log.
- **The `--note`/`--reason` last-wins alias.** Read the resolved value only.

## Review Guidance

- The record is on the transition; the annotation still holds the lanes; no new library field.
- The full reset is the default. Narrowing needs a reason and roster ids, and is refused before any write.
- Red→green is proven; the out-of-matrix suites were run and recorded.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
