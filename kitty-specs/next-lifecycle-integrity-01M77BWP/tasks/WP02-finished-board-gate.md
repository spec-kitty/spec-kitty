---
work_package_id: WP02
title: Advancing next never rewinds a finalized software-dev board
dependencies:
- WP01
requirement_refs:
- C-001
- C-004
- C-005
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-016
- NFR-001
- NFR-004
- SC-001
- SC-002
- SC-005
planning_base_branch: fix/7548-next-lifecycle-integrity
merge_target_branch: fix/7548-next-lifecycle-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/7548-next-lifecycle-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7548-next-lifecycle-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T022
- T023
- T013
- T009
phase: 'Phase 2 - #7553 / #5929 / #7565'
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-11-12T09:30:00Z'
  actor: claude
  action: Revised after the post-tasks adversarial squad and operator rulings
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/next/test_finished_board_gate_7553.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_decision_mapping.py
- src/specify_cli/cli/commands/next_cmd.py
- tests/next/test_finished_board_gate_7553.py
- tests/next/test_next_advance_first_contact_5310.py
- tests/runtime/test_runtime_bridge_read_path_branches.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Advancing next never rewinds a finalized software-dev board

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role `implementer`), and behave according to its guidance before reading on.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission next-lifecycle-integrity-01M77BWP`). Address every item.

---

## Objectives & Success Criteria

This WP delivers FR-001 to FR-007 and FR-016. They close #7553 (replay after accept), and #5929 and #7565 (replay after every WP is approved, and mid-implementation).

**Operator rulings** (in `decisions/`): `finished_board_envelope`, `finished_board_state_map`, `plan.next.mid_implementation_replay`, `plan.next.acceptance_freshness`, `plan.next.gate_scope_family`, `plan.next.command_field_amendment`.

**Scope: software-dev only** (`mission_type == MISSION_TYPE_SOFTWARE_DEV`, following the #3407 precedent at `runtime_bridge.py:1006-1027`). Documentation, research, plan and custom Missions must stay byte-identical. Their DAGs carry steps after the WPs (validate, publish, synthesis) that the gate would otherwise starve.

**Applicability.** The gate applies when all three hold:
- a finalized board exists, meaning the board step authority (`_finalized_task_board_override_step`) returns a step;
- the persisted run is **not authoritative**, meaning one of:
  - no run in the index;
  - an untouched run;
  - a run whose `issued_step_id` is a planning step before analyze (discovery, research, specify, plan, tasks).
- Use `_mapping._is_wp_iteration_step(step)`, `== "analyze"` (match the constant the code already uses, e.g. `_cores.ANALYZE_STEP_ID`) and `== "accept"` for the authoritative set. Do not use bare literals.
- A `RunStateMissing` or other run-read error makes the gate **return None**, so the existing "Failed to start/load runtime run" blocker still reports the corruption.

**Answers when the gate applies** (for any `--result`):

| Board | Envelope |
|---|---|
| finished (step `accept`/`done`, acceptable endings incl. canceled), verdict `AWAITING_ACCEPTANCE` | `kind=blocked`, `mission_state="accept"`, `error_code=MISSION_AWAITING_ACCEPTANCE`, `next_command="spec-kitty accept --mission <slug>"`, `suppress_step_pairing=True`, reason names the command |
| finished, verdict `ACCEPTED` (acceptance newer than the board's latest WP transition) | `kind=terminal`, `mission_state="done"`, `suppress_step_pairing=True` |
| step implement/review and the board dispatches | fall through to the widened `_dn_finalized_board_override` (T022) |
| step implement/review and the board **declines** (e.g. a WP `in_progress`/`claimed`) | `kind=blocked`, `error_code=BOARD_STEP_NOT_DISPATCHABLE` (hoist as a constant), reason names the WP and its lane, `next_command` = the resume command for that WP (`spec-kitty agent action implement <WP> --agent <agent> --mission <slug>` for implement, the review action for review; verify the real command names with `--help`), `suppress_step_pairing=True` |
| `blocked:*` | the existing board blocked decision (as `_dn_finalized_board_override` builds it today) |

**Recording on a gate answer:**
- no run is started (no new `feature-runs.json` entry) or advanced (no `NextStepIssued`/`NextStepAutoCompleted`);
- no invocation lifecycle `completed`/`failed` pairing (T023);
- no issuance record;
- no Op `started` records or profile-invocation events;
- **exactly one** `MissionNextInvoked` row, with `decision_kind` in {blocked, terminal} (C-005; also the positive control).

**Unchanged:**
- landed Missions (merged short-circuit);
- authoritative runs at analyze, implement, review or accept;
- Missions with no WPs;
- every non-software-dev family.

## Context & Constraints

- **Read first:**
  - `plan.md` IC-02 (revised)
  - `research.md`, including Squad dispositions
  - `data-model.md`
  - `contracts/next-envelope-additions.md`
  - `research/code-grounding.md` §1
- **Repro:** `research/test_repro_7553.py`.
- **WP01 provides:**
  - `finished_board_verdict`, `FinishedBoardVerdict`, `FINISHED_BOARD_STEPS`, `MISSION_AWAITING_ACCEPTANCE_ERROR_CODE`
  - `Decision.next_command`, `Decision.suppress_step_pairing` and their `DecisionEnvelope` twins
  - `runtime_bridge_io.mission_accepted_at` and `board_latest_transition_at`
  - `DecisionEnvelope.error_code` (already exists)
- **Binding constraints:**
  - Read the status door only once on the decision path: reuse `status_read` from `_dn_progress`.
  - The blocked/terminal `MissionNextInvoked` row makes one more door read through `_consolidated_target_dir` (`next_invocation_lifecycle.py:331-347,434`). This is accepted; pin it with a count test next to `tests/runtime/next/test_advancing_decision_door_reads_7539.py`.
  - Run lookup is read-only: `_io_seam._existing_run_ref`.
  - Add no new writer, and keep complexity ≤ 15. `_dn_bootstrap` is at 15, so do T006 first.
- **Do not touch:**
  - `runtime_bridge_query.py` (WP03)
  - the cores, decision and io modules (WP01)
  - consolidation, the review prompt, and `packs/built-in/`

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`.
- Run `spec-kitty agent action implement WP02 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first tests (commit FIRST)

- **File**: `tests/next/test_finished_board_gate_7553.py`.
- **Fixture:**
  - `tests/next/test_finalized_task_routing._scaffold`, `tests/runtime/_next_mission_scaffold.provision_mission_type_activations` and `analysis_is_current`.
  - **Mint a ULID `mission_id` into the fixture's `meta.json`.** Without it, `pair_previous_lifecycle_record` and `write_issuance_lifecycle_record` return early (`next_invocation_lifecycle.py:209,291`), and the lifecycle assertions are blind.
  - Write acceptance as `record_acceptance` writes it (`accepted_at`, `accepted_by`, `acceptance_mode`). Control the timestamps against the board's latest WP transition explicitly.
- **Drive** cells 1, 2, 5 and 7 through the real CLI (`CliRunner`, as in `tests/next/test_next_command_integration.py`, which shows the charter-preflight bypass): `spec-kitty next --agent claude --mission <slug> --result <r> --json`. Bridge-level `decide_next_via_runtime` is acceptable for the other cells.
- **No-row probe helper:**
  - Snapshot the whole repository tree (excluding `.git/`) as path → sha256 before and after each gated call.
  - Assert the **only** changed path is `kitty-specs/<slug>/mission-events.jsonl`, grown by exactly one row whose `decision_kind` is in {blocked, terminal}. Requiring that row is the positive control that the probe reads the file `next` writes.
  - Also assert `.kittify/runtime/feature-runs.json` is absent (or unchanged) and that `.kittify/runtime/runs/` holds no new events.
- **Cells:**
  1. Approved board, not accepted: blocked, `MISSION_AWAITING_ACCEPTANCE`, `next_command == "spec-kitty accept --mission <slug>"`, no rows.
  2. Approved board, accepted later than the latest transition: terminal on 10 consecutive calls (SC-001), no rows.
  3. Done board, not accepted: blocked.
  4. All-canceled board and approved+canceled board: blocked.
  5. `--result failed` and `--result blocked` on cell 1's fixture: blocked, never `step`.
  6. Acceptance older than the latest transition (reopen then re-approve): blocked, not terminal (FR-002 freshness).
  7. Mid-implementation: `{WP01: approved, WP02: in_progress}` and `{…, WP02: claimed}` give blocked `BOARD_STEP_NOT_DISPATCHABLE`, naming WP02, with a resume `next_command`, and no rows (FR-016). Today they issue `discovery`.
  8. **Stale run, seeded engine-direct.** Use `_advance_runtime_to_step` from `tests/next/test_next_command_integration.py`, or the `advance_to_step` pattern from the 5310 test; the old CLI flow is gated at the head. Seed a run issued at `discovery` and another at `plan`. Each must be answered by the gate, and the snapshot (`completed_steps`, `issued_step_id`) must be unchanged.
  9. **Stale run with a lifecycle record, seeded through the CLI** before the board is finalized (or with `tasks.md` absent), so that a lifecycle `started discovery` record exists. Positive control: the seeding call wrote `started`. Then restore the finalized board. Assert that the gated `--result success` writes **no** `completed` record (T023).
  10. **Residual pins** (documented, not fixed): a stale run already at `analyze`, and one at `implement` with replayed `completed_steps`. Pin today's engine path in a test marked `# residual: indistinguishable from a legitimate run (research.md)`.
- Commit alone: `test(next): red-first never-rewind gate (#7553, #5929, #7565)`. Confirm the tests are red for the right reason (the envelope or the rows), not because of fixture errors.

### Subtask T006 – Tidy-first: extract headroom from `_dn_bootstrap`

- Move "get or start run → read snapshot → seed emitter → operational context" (around lines 666–715) into `_dn_start_run_and_snapshot(...)`.
- Make it behaviour-preserving and give it its own commit (`refactor(next): extract run start from _dn_bootstrap`).

### Subtask T008 – Board-step accessor

- Extract the shared prefix of `_resolve_wp_board_action`: surface → mission context → task board dir → board from `status_read` → task error → progress → `_finalized_task_board_override_step`. The new function is `_resolve_finalized_board_step(...) -> tuple[str | None, <board/task_board_dir for reuse>] | _WpBoardAction`.
  - `_resolve_wp_board_action` calls it, so the two cannot diverge.
  - The gate calls only the accessor. It does **not** pay for the dispatch resolution (`resolve_workspace_for_wp` / `MissingLanesError`) unless it needs to know whether the board dispatches. In that case it calls `_board_step_action` (unchanged).
- `_board_step_action` keeps returning `_WP_BOARD_DECLINE` (identity) for accept/done. `tests/runtime/test_runtime_bridge_read_path_branches.py:209` stays green unchanged.

### Subtask T007 – The gate

- Add `_dn_never_rewind_gate(...)` in `_dn_bootstrap`, after `_dn_progress` and before `_dn_start_run_and_snapshot`. It returns `Decision | None`. Inputs: `agent`, `mission_slug`, `repo_root`, `owned`, `status_read`, `primary_metadata_dir`, `mission_type`, `now`, `progress`, `origin`, `config_root`, `result`.
- Logic, in order:
  1. Return None unless software-dev.
  2. Accessor → step. Return None if there is no finalized step.
  3. Read-only run lookup and authority check.
  4. Finished-board branch (verdict from the WP01 helpers).
  5. Non-dispatchable branch.
  6. `blocked:*` branch.
  7. Dispatchable: return None.
- Wrap the result with `_with_remediation`.
- **Owned path:** `primary_metadata_dir` comes from the mission context. Add one owned cell if `tests/integration/test_owned_lifecycle_acceptance_next.py` gives a cheap fixture; otherwise record the gap.

### Subtask T022 – Widen the front phase

- `_dn_finalized_board_override` currently requires `ctx.result == "success" and _run_is_untouched(ctx.run_dir)`. Widen that to "the run is not authoritative (same predicate as the gate; share one helper) for any result".
- With `--result failed|blocked` against a board-dispatched WP step, the board re-dispatches. The run is not authoritative, so the result is not applied to it. Document this in the docstring; it is #4898-adjacent, Refs only.
- Keep the analysis-currency check (B3) for implement.

### Subtask T023 – Suppress the stale pairing

- In `next_cmd._dispatch_advancing_mode` (around `:447-470`), `_pair_previous_lifecycle_record` runs **before** `decide_next`. Move the pairing after `decide_next`, and skip it when `decision.suppress_step_pairing` is True.
  - First prove the move is otherwise behaviour-preserving: the pairing reads only the previous `started` record, and `decide_next` writes no lifecycle record. Run `tests/next/test_next_command_integration.py`, `tests/integration/test_owned_lifecycle_acceptance_next.py` and any test touching `pair_previous_lifecycle_record`.
  - If the move is not safe, report it instead of forcing it.
- Docstring: "a gate answer leaves a stale `started` record unpaired, which is truthful; pairing it would record a completion for a step that never ran (#7553)".

### Subtask T013 – Render `next_command`

- In `next_cmd.py`, print a `Next: <command>` line whenever `decision.next_command` is set. That covers both the query details printer (`_print_query_details`, around `:1453-1480`, which WP03's query envelopes need) and the blocked/terminal human printers.
- JSON needs no change.

### Subtask T009 – Re-pin and controls

- **Re-pin** `tests/next/test_next_advance_first_contact_5310.py::test_advance_declines_front_phase_on_all_approved_board` to the blocked contract. Keep its "no implement/review" assertions, and update its docstring (#7553, #5929).
- **FR-006 positive controls** (same fixture family):
  - one WP `planned` (claimable) dispatches implement, bridge-level with `analysis_is_current`, or CLI expecting `analyze`;
  - a run at `review` with the last WP approved issues the `accept` step, then terminal on success;
  - a no-WP Mission is unchanged;
  - a **documentation** Mission with a finished board is byte-identical (`scaffold_custom_analyze_mission` or a docs fixture under `tests/runtime/`; find one);
  - a reopened accepted Mission, with a WP moved to `planned` or `for_review`, follows the board.
- **Door-read count test:** a gated answer makes exactly two door reads, the bootstrap read and the `MissionNextInvoked` landed-routing read.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/next/test_finished_board_gate_7553.py tests/next/test_next_advance_first_contact_5310.py tests/next/test_finalized_task_routing.py tests/next/test_runtime_bridge_unit.py tests/next/test_runtime_bridge_blocked_paths.py tests/next/test_next_command_integration.py tests/next/test_next_dependency_wedge_5669.py tests/runtime/next/test_merged_mission_terminal.py tests/runtime/test_runtime_bridge_read_path_branches.py tests/runtime/test_next_board_authority.py tests/runtime/next/test_advancing_decision_door_reads_7539.py tests/integration/test_owned_lifecycle_acceptance_next.py -q -n 4 --dist loadfile -p no:cacheprovider
.venv/bin/python -m pytest tests/runtime/next tests/specify_cli/next tests/next tests/contract/test_next_no_unknown_state.py tests/contract/test_next_no_implicit_success.py -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_status_read_single_door.py tests/architectural/test_event_log_writes_gate.py tests/architectural/test_run_index_single_reader.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_bridge_cores_import_boundary.py -q
uv run --frozen ruff check src/runtime/next src/specify_cli/cli/commands/next_cmd.py tests/next/test_finished_board_gate_7553.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_decision_mapping.py src/specify_cli/cli/commands/next_cmd.py
uv run --frozen ruff check --select C901 src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_decision_mapping.py src/specify_cli/cli/commands/next_cmd.py
```

Record exact counts. Classify any red using the CLAUDE.md baseline-red gotcha: re-run it on the planning base before attributing it.

## Risks & Mitigations

- **Next-driven Missions lose `MissionRunCompleted`.** Mitigation: authoritative runs keep the engine path, with a positive control. The non-authoritative residual is documented.
- **Non-software-dev families.** Mitigation: the family check, plus a docs control.
- **Moving the pairing.** Prove it is safe first, or report it.
- **orchestrator-api.** It shares `decide_next`, and blocked answers are reported as `RUNTIME_NEXT_FAILED` (existing mapping). Add one note-level test or comment.

## Review Guidance

- Red→green: T005's commit is red on the base.
- The tree-snapshot probe allows only the one blocked/terminal row.
- Software-dev only; authoritative runs unchanged.
- One bootstrap door read, plus the pinned landed-routing read.
- Complexity ≤ 15. `_WP_BOARD_DECLINE` identity is unchanged.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
- 2026-11-12T09:30:00Z – claude – Revised: never-rewind (FR-016), software-dev scope, freshness, accessor, pairing suppression, renderer moved in, tree-snapshot probes.
