---
work_package_id: WP04
title: Recorded and narrowable rollback subtask reset
dependencies: []
requirement_refs:
- C-002
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- SC-004
planning_base_branch: fix/7548-next-lifecycle-integrity
merge_target_branch: fix/7548-next-lifecycle-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/7548-next-lifecycle-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7548-next-lifecycle-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-next-lifecycle-integrity-01M77BWP
base_commit: 6969bd06a0ec7afcfc94a7009f5bb1a248042d54
created_at: '2026-11-12T09:17:03.732350+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
phase: 'Phase 2 - #7582'
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-11-12T09:30:00Z'
  actor: claude
  action: Revised after the post-tasks adversarial squad
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
tags: []
task_type: implement
tracker_refs: []
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

This WP delivers FR-011 to FR-015 (#7582), following the operator ruling of 2026-11-12: a recorded reset with narrowing (`decisions/`, `subtask_reset_policy`).

1. **FR-011.** Every `move-task --to planned` (rejection, reopen from approved/done, unclaim) records the reset on the PLANNED transition event:

   ```json
   "policy_metadata": {"rollback_reset": {"scope": "full|narrowed", "reset": [...], "previously_completed": [...], "reason": "..."}}
   ```

   - The pipeline merges `{**request, **added}` (`status/transition_pipeline.py:249`), so `lane_head` and `wp_window` survive.
   - `reason` is the operator's resolved `--note`/`--reason`, else derived as `"rollback to planned: <from_lane> -> planned"` plus the review ref.
2. **FR-012.** `--reset-subtasks T002[,T003]` resets only the named ids.
3. **FR-013.** The command is refused **before any write** (exit ≠ 0, git HEAD unchanged, no review-cycle file, event log byte-identical) when:
   - an id is not on the roster;
   - an id is `skipped` (it cannot be reset);
   - no note or reason is given;
   - `--to` is not `planned`.
   Each refusal has its own message naming the offending input.
4. **FR-014.** Without the flag, every non-skipped subtask resets, as today (#2513). The `for_review` subtask gate still blocks on a reset subtask.
5. **FR-015.**
   - The human line names the scope and the reason.
   - The JSON gains `subtasks_reset_scope` and `subtasks_reset_reason`.
   - The existing `subtasks_reset_*` keys are unchanged.

## Context & Constraints

- **Read first:**
  - `plan.md` IC-04 (revised);
  - `research.md` R-6 and the Squad dispositions;
  - `data-model.md`;
  - `contracts/rollback-reset-record.md`;
  - `research/code-grounding.md` §2.
- **Order facts from the squad:**
  - `_mt_finalize_plan` commits the rejected review-cycle artifact (`tasks_move_task_executor.py:139-140` → `persist_rejected_review_cycle_for_rollback`) **before** `_mt_execute`. The order is around `tasks_move_task.py:2041-2057`.
  - Validation must therefore run right after `_mt_resolve_targets`.
  - `st.note_text` is only set at `executor.py:136`, so read the resolved `--note`/`--reason` from the request args.
- **Single authority for the reset map.**
  - Today `_build_claim_review_override` (`hops.py:394-456`) recomputes the reset and the summary after the hop.
  - Compute `(reset_map, summary)` **once** onto the move-task state, before `_mt_emit_transitions`.
  - Both `_mt_hop_policy_metadata` (PLANNED hop only: `st.target_lane == PLANNED and hop target == PLANNED`) and `_build_claim_review_override` read it.
- **`--reason` already exists** as an alias of `--note`; the last one on the command line wins. Add no new reason flag.
- **No change to the event contract or the library.** The `InnerStateChanged` delta keeps the per-id lanes.
- **Architecture gates:**
  - `tests/architectural/test_status_events_writes_gate.py`
  - `test_innerstatechanged_invariants.py`
  - `test_no_write_side_rederivation.py`
  - `test_2093_authority_invariant.py`
  - `test_exemption_registry_ratchet.py`
  - `test_dossier_sha_provenance.py`
- **Complexity:** `_do_move_task` is at 15, so put the validation in a helper.
- **CI coverage:** `tests/specify_cli/cli/commands` is outside the per-PR CI matrix. Run it explicitly and record the counts.
- **Out of scope:** the assignee rebind on `--to planned --agent <reviewer>` (startup-assess F-3).

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`.
- Run `spec-kitty agent action implement WP04 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T015 – Red-first CLI tests (commit first)

- **File**: `tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py`.
- **Harness**: **copy and extend** `_build_in_review_repo` / `_move_task_cli` from `test_tasks_move_task_cli_4899.py`. `_move_task_cli` takes no extra args, so the copy must accept `*extra_args`.
  - Use roster `[T001, T002]`, both done.
  - Seed the done state through the real `spec-kitty agent tasks mark-status T001 T002 --status done` (or the same annotation seeding the harness uses).
  - **Create the lane branch** (`kitty/mission-<slug>-lane-a`, as the fixture's `lanes.json` names it), so `lane_head` is stamped.
- **Cells**:
  1. **Full rejection** (`--to planned --review-feedback-file fb.md`):
     - both subtasks reset;
     - the PLANNED event's `policy_metadata.rollback_reset == {"scope": "full", "reset": ["T001", "T002"], "previously_completed": ["T001", "T002"], "reason": <derived>}`;
     - **`lane_head` is present** on the same event (positive control).
  2. **Narrowed rejection** (`--to planned --review-feedback-file fb.md --reset-subtasks T002 --note "T002 regressed"`):
     - the snapshot has `T001` done and `T002` planned;
     - the record has `scope: narrowed`, `reset: [T002]`, `previously_completed: [T002]`, `reason: "T002 regressed"`.
  3. **Unknown id** (`--reset-subtasks T009 …`, all other args as in cell 2): refused. The message names `T009`. HEAD, the review-cycle dir and the event log are unchanged.
  4. **No reason** (cell 2 without `--note`): refused. The message says `--reset-subtasks requires --note/--reason`. Nothing is written.
  5. **Wrong lane** (`--to for_review --reset-subtasks T001 --note x`): refused. The message names the target-lane rule.
  6. **Skipped id**: T002 is `skipped` and named. Refused, with a message naming the skipped state.
  7. **Gate**: after cell 2, re-claim and move `--to for_review`. The refusal message **names T002**. Mark T002 done; the subtask refusal clears. Any remaining refusal must come from another gate, e.g. the lane-commit gate, and must not name subtasks.
  8. **Note/reason precedence**: `--note a --reason b` records `b` (last wins).
  9. **Reopen from approved**: a WP in approved with forced `--to planned` is recorded the same way, with `scope: full`.
  10. **JSON output**: `--json` carries `subtasks_reset_scope` / `subtasks_reset_reason`.
  11. **Skipped excluded**: a `skipped` subtask is never in `reset` (full scope).
- Cells 3–6 must be RED on the base **for the right reason**. Today the option does not exist and Typer exits 2. So also assert the specific message, which fails on the base. Pair each refusal with cell 2's fixture and arguments.
- Commit alone: `test(move-task): red-first rollback reset record and narrowing (#7582)`.

### Subtask T016 – Option and validation

- Add the option in `tasks.py` `move_task`: `--reset-subtasks` (`str | None`, comma-separated). Use help text that names the reason requirement.
- Thread it into the move-task request/state.
- Add `_mt_validate_reset_subtasks(...)`, called right after `_mt_resolve_targets` and before `_mt_finalize_plan`:
  - parse and dedup;
  - check against the roster (`core.subtask_rows.authored_subtask_roster`, the same reader `_mt_rollback_subtasks_reset` uses);
  - refuse a skipped id (using the current snapshot);
  - require a non-empty resolved note;
  - require the target `planned`.
  - Use the typed refusal style of the other move-task guards.

### Subtask T017 – Compute once; record on the PLANNED hop

- Before the transitions, compute `(reset_map, summary)` once and store them on the state.
- `_mt_hop_policy_metadata` returns `{"rollback_reset": {...}}` for the PLANNED hop. Hoist the derived-reason prefix into a constant.
- `_build_claim_review_override` reads the stored map (no recomputation).

### Subtask T018 – Narrow the annotation

- `_mt_rollback_subtasks_reset(..., only: frozenset[str] | None = None)`:
  - with `only`, map just those ids;
  - skipped ids are always excluded.

### Subtask T019 – Announcement and cutover pin

- Extend `_RollbackResetSummary` with `scope` and `reason`.
- Human line, narrowed: `↺ Reset 1 of 2 subtask(s) to planned (narrowed: T002 regressed)`.
- Human line, full: append `(full reset: <reason>)` to today's wording.
- Add the JSON keys.
- `test_move_task_rollback_signal.py`: only extend existing expectations; never delete assertions.
- **Cutover pin test.** `status/cutover_eligibility._policy_metadata_carries_runtime_evidence` (`:97-122`) returns True for a PLANNED event carrying `rollback_reset` and `lane_head`. Explain in the docstring why that is harmless: a WP being rolled back already had a claim carrying policy metadata.
  - This test lives under `tests/status/`, which is not in owned_files. Add it there under ownership leeway, with a one-line rationale, or put it in your owned test file.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py tests/specify_cli/cli/commands/agent/test_move_task_rollback_signal.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py -q -p no:cacheprovider
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent -q -n 4 --dist loadfile -k "move_task or mark_status or subtask or rollback"
.venv/bin/python -m pytest tests/status -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_status_events_writes_gate.py tests/architectural/test_innerstatechanged_invariants.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_2093_authority_invariant.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_dossier_sha_provenance.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/agent tests/specify_cli/cli/commands/agent/test_move_task_rollback_reset_7582.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/cli/commands/agent/tasks_move_task.py src/specify_cli/cli/commands/agent/tasks_move_task_executor.py src/specify_cli/cli/commands/agent/tasks_move_task_hops.py src/specify_cli/cli/commands/agent/tasks.py
uv run --frozen ruff check --select C901 src/specify_cli/cli/commands/agent/tasks_move_task.py src/specify_cli/cli/commands/agent/tasks_move_task_executor.py src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
```

## Risks & Mitigations

- **Writing before validating.** Mitigation: validate right after target resolution; cells 3–6 assert that HEAD and the review-cycle dir are unchanged.
- **Two reset authorities.** Mitigation: compute once onto the state.
- **Losing `lane_head`.** Mitigation: cell 1's positive control.

## Review Guidance

- The reset record sits on the transition, and the annotation still holds the lanes.
- The default stays a full reset.
- Narrowing needs a reason and roster ids, and is refused before any write, with its own messages.
- Red→green is proven, and the out-of-matrix suites were run and recorded.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
- 2026-11-12T09:30:00Z – claude – Revised: validation order, single authority, blind-cell fixes, skipped/precedence/reopen cells.
