---
work_package_id: WP02
title: Advancing next never replays a finished board
dependencies: [WP01]
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-004
- C-001
- C-004
- C-005
- SC-001
- SC-002
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: 'Phase 2 - #7553 / #5929 / #7565'
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/next/test_finished_board_gate_7553.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_decision_mapping.py
- tests/next/test_finished_board_gate_7553.py
- tests/next/test_next_advance_first_contact_5310.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP02 – Advancing next never replays a finished board

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role `implementer`), and behave according to its guidance before reading on.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission next-lifecycle-integrity-01M77BWP`) and address every item.

---

## Objectives & Success Criteria

Deliver FR-001 to FR-007 (spec.md). These issues share one root cause: #7553 (replay after accept), #5929 and #7565 (replay once every WP is approved).

On a **finished board**, an advancing `spec-kitty next --result <any>`:

| Mission state | Envelope |
|---|---|
| not accepted | `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE`, `next_command="spec-kitty accept --mission <slug>"`, and a reason that names the command |
| accepted (board still finished) | `kind=terminal`, `mission_state="done"` |
| landed | unchanged: the existing merged short-circuit returns terminal |

A finished board has at least one WP, and every WP is in `approved` or `done`, or acceptable endings (the board step is `accept` or `done`).

In both new cases, `next`:
- starts no run, so `feature-runs.json` gets no new entry;
- advances no run, so `run.events.jsonl` gets no `NextStepIssued` and no `NextStepAutoCompleted`;
- writes no `MissionNextInvoked` with `decision_kind: step`;
- writes no issuance lifecycle record.

The `MissionNextInvoked` row that records a blocked or terminal invocation stays (C-005, #7539 landed routing).

**The gate does not fire, and the engine path is unchanged, when** a persisted run legitimately sits on a WP-iteration step or `accept` (`issued_step_id in {"implement", "review", "accept"}`). That keeps `MissionRunCompleted` and the retrospective gate reachable for Missions driven through `next` (research R-3).

## Context & Constraints

- **Read first:** `plan.md` IC-02, `research.md` R-1 to R-4, `data-model.md`, `contracts/next-envelope-additions.md`, and `research/code-grounding.md` §1 (all file:line citations are there).
- **Repro:** `research/test_repro_7553.py` is a bridge-level reproduction using the `_scaffold` fixture of `tests/next/test_finalized_task_routing.py`. Output on main: `QUERY0 query done`, `ADV0 step discovery`, `ADV1 specify`, …
- **WP01 provides:**
  - `runtime_bridge_cores.finished_board_verdict`, `FinishedBoardVerdict`, `FINISHED_BOARD_STEPS`, `MISSION_AWAITING_ACCEPTANCE_ERROR_CODE`;
  - `Decision.next_command` / `DecisionEnvelope.next_command`;
  - `runtime_bridge_io.mission_is_accepted(primary_metadata_dir)`.
- **Binding constraints:**
  - Status is read only through the door. Reuse the bootstrap's one read (`status_read` from `_dn_progress`); **do not** read the door again (#7539/#7564 "read once").
  - Look up the run read-only with `_io_seam._existing_run_ref` (never `get_or_start_run` before the gate). The run index literal stays in `run_index.py` (`tests/architectural/test_run_index_single_reader.py`).
  - Add no new writer (`tests/architectural/test_event_log_writes_gate.py`).
  - Keep complexity ≤ 15. `_dn_bootstrap` is AT 15 today, so T006 comes first.
- **Do not touch:** `runtime_bridge_query.py` or `next_cmd.py` (WP03 owns them), the cores, decision or io modules (WP01), consolidation, or the review prompt.
- **Mission scope:** Missions with no WPs (artifact-only) and research/custom Missions without a finalized board must behave byte-identically. `_finalized_task_board_override_step` already returns None for `total_wps == 0` or with no tasks.md, so the verdict is `NONE` and the gate is a no-op.

## Branch Strategy

- **Planning base branch**: `fix/7548-next-lifecycle-integrity`; **merge target**: `fix/7548-next-lifecycle-integrity`.
- Lane worktrees come from `lanes.json`. Run `spec-kitty agent action implement WP02 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first CLI tests (commit FIRST, before any product change)

- **Purpose**: ATDD contract (Charter C-011). The tests must be RED on the planning base.
- **File**: `tests/next/test_finished_board_gate_7553.py` (new).
- **Fixture**: reuse `tests/next/test_finalized_task_routing._scaffold(repo, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})`, `tests/runtime/_next_mission_scaffold.provision_mission_type_activations` and `analysis_is_current`. Write acceptance into `meta.json` with the same keys `record_acceptance` writes (`accepted_at`, `accepted_by`, `acceptance_mode`), as the repro does.
- **Drive** through the real CLI entry point where feasible. `tests/next/test_next_command_integration.py` shows the `CliRunner` + git pattern and the charter-preflight bypass fixture: `spec-kitty next --agent claude --mission <slug> --result success --json`. Where the CLI wrapper adds heavy prerequisites, a bridge-level `decide_next_via_runtime` test is acceptable for the secondary cells. At least scenarios 1 and 2 must be CLI-level (NFR-004).
- **Cells:**
  1. Board approved, not accepted → `kind == "blocked"`, `error_code == "MISSION_AWAITING_ACCEPTANCE"`, `next_command == "spec-kitty accept --mission <slug>"`.
  2. Board approved and accepted → `kind == "terminal"`; 5 consecutive calls all terminal.
  3. Board all `done`, not accepted → blocked (same as 1).
  4. Stale walked run: start the run and advance it once on the OLD path to issue `discovery` (seed it via `get_or_start_run` + the engine, or by running the old flow before acceptance). Then assert that the gate answers and the snapshot's `completed_steps`/`issued_step_id` do not change.
  5. `--result failed` and `--result blocked` on a finished board → blocked/terminal, never a `step`.
  6. **No-row assertions for 1–5:**
     - no new `NextStepIssued`/`NextStepAutoCompleted` in any `.kittify/runtime/runs/*/run.events.jsonl`;
     - no new run entry in `feature-runs.json` when none existed;
     - no `MissionNextInvoked` row with `decision_kind == "step"` in `kitty-specs/<slug>/mission-events.jsonl`. A blocked or terminal row is allowed.
- Commit these tests alone, with message `test(next): red-first finished-board gate (#7553, #5929, #7565)`, and confirm they fail.

### Subtask T006 – Tidy-first: extract headroom from `_dn_bootstrap`

- **Purpose**: `_dn_bootstrap` (`runtime_bridge.py:519`) is at complexity 15.
- **Steps**:
  - Move the segment "get or start run → read snapshot → seed emitter → operational context" (roughly lines 666–715) into a helper, e.g. `_dn_start_run_and_snapshot(...) -> tuple[MissionRunRef, Path, str | None] | Decision`.
  - Make it behaviour-preserving, with its own commit: `refactor(next): extract run start from _dn_bootstrap`.
  - Run `tests/next/test_runtime_bridge_unit.py tests/next/test_runtime_bridge_blocked_paths.py tests/runtime/next/` to confirm it stays green.

### Subtask T007 – `_dn_finished_board_gate`

- **Purpose**: The fix.
- **Placement**: in `_dn_bootstrap`, AFTER `_dn_progress(...)` (which yields `progress, feature_dir, status_read`) and BEFORE the run start (T006's helper). Call a new helper:

  ```python
  gate = _dn_finished_board_gate(agent=..., mission_slug=..., repo_root=..., owned=..., status_read=status_read,
                                 primary_metadata_dir=primary_metadata_dir, mission_type=mission_type,
                                 now=now, progress=progress, origin=origin, config_root=config_root)
  if gate is not None:
      return None, _with_remediation(gate, remediation)
  ```

- **Logic**:
  1. `board = _mapping._resolve_wp_board_action(mission_slug=..., repo_root=..., owned=..., status_read=status_read)`. Read the finished board step from it (T008).
  2. `accepted = primary_metadata_dir is not None and _io_seam.mission_is_accepted(primary_metadata_dir)`.
  3. `verdict = _cores.finished_board_verdict(board_step, accepted=accepted)`. If `NONE`, return None.
  4. Read-only run lookup: `run_ref = _io_seam._existing_run_ref(mission_slug, config_root, mission_type, owned=owned)`.
     - If a run exists, read its snapshot.
     - If `issued_step_id in {"implement", "review", "accept"}`, return None, so the engine owns that run.
     - Treat a `RunStateMissing` (or any read error) as "no legitimate position": the gate still answers. Document why.
  5. `AWAITING_ACCEPTANCE` → `_mapping._materialize_decision(DecisionEnvelope(kind=blocked, mission_state="accept", reason="All work packages are approved or done; the Mission awaits acceptance. Run `spec-kitty accept --mission <slug>`.", error_code=MISSION_AWAITING_ACCEPTANCE, next_command=f"spec-kitty accept --mission {mission_slug}", progress=progress, origin=origin))`.
  6. `ACCEPTED` → `DecisionEnvelope(kind=terminal, mission_state="done", reason="Mission is accepted; nothing left to run through next", progress=..., origin=...)`.
  7. `run_id` is set only when a run exists. Never start one.
- **Checks**:
  - Confirm `DecisionEnvelope` supports `error_code`. If not, it is a WP01 hand-off gap: coordinate rather than editing the cores.
  - Confirm `_with_remediation` keeps `next_command` (it uses `dataclasses.replace`).
- **Recording audit**: trace `next_cmd._dispatch_advancing_mode` → `_emit_mission_next_invoked` / `_write_issuance_lifecycle_record` for a blocked/terminal decision, and confirm nothing step-like is written. `write_issuance_lifecycle_record` writes only for `kind == "step"`. `pair_previous_lifecycle_record` pairs the previous *genuinely issued* step on success, which is truthful and unchanged. Note this in the test docstring.
- **Owned path**: `primary_metadata_dir` comes from the mission context in the owned branch of `_dn_bootstrap`. Pass `owned` through. Add one owned-checkout test cell if a fixture exists (`tests/integration/test_owned_lifecycle_acceptance_next.py` shows the pattern); otherwise note the gap.

### Subtask T008 – Expose the finished board step

- **Purpose**: `_board_step_action` (`runtime_bridge_decision_mapping.py:582`) collapses `accept`/`done` into the shared `_WP_BOARD_DECLINE`, so the step name is lost.
- **Steps**:
  - Return `_WpBoardAction(board_step=board_step, action=None, wp_id=None, workspace_path=None, blocked_reason=None)` for `accept`/`done`, so that `board.board_step` carries the finished step.
  - **Audit every reader** of `_WpBoardAction.board_step` and `_WP_BOARD_DECLINE` identity checks: `_build_wp_iteration_decision`, `_map_wp_step_decision`, `_dn_finalized_board_override`, and grep for `is _WP_BOARD_DECLINE`. Confirm a finished step with `action=None` takes the same branch as the old decline everywhere.
  - If any reader branches on `board_step is None` or identity with the decline sentinel, prefer adding a separate accessor instead: `_resolve_finished_board_step(...) -> str | None`, reading the same `status_read`, no second door read. Pick whichever keeps every existing branch byte-identical, and record the choice in `traces/design-decisions.md` via your hand-off note.

### Subtask T009 – Re-pin and non-regression controls

- `tests/next/test_next_advance_first_contact_5310.py::test_advance_declines_front_phase_on_all_approved_board` pins the old walk-to-discovery. Its docstring (`:8`) blesses "keeps its pre-existing path". Re-pin it to the new contract (blocked, MISSION_AWAITING_ACCEPTANCE), keeping its original assertions (no implement/review dispatched). Update the docstring to cite #7553/#5929 and this Mission.
- Add FR-006 positive controls to the new test file, on the same fixture:
  - one WP `in_progress`, so the board dispatches implement as before;
  - a run legitimately at `review` with the last WP approved, so the engine still advances to the `accept` step (`kind=step`, `action` accept). That is the MissionRunCompleted-preserving path;
  - a no-WP Mission behaves as before.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/next/test_finished_board_gate_7553.py tests/next/test_next_advance_first_contact_5310.py tests/next/test_finalized_task_routing.py tests/runtime/next/test_merged_mission_terminal.py tests/next/test_runtime_bridge_unit.py tests/next/test_runtime_bridge_blocked_paths.py tests/next/test_next_command_integration.py tests/integration/test_owned_lifecycle_acceptance_next.py -q -n 4 --dist loadfile -p no:cacheprovider
.venv/bin/python -m pytest tests/runtime/next tests/specify_cli/next tests/contract/test_next_no_unknown_state.py tests/contract/test_next_no_implicit_success.py -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_status_read_single_door.py tests/architectural/test_event_log_writes_gate.py tests/architectural/test_run_index_single_reader.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_inline_meta_read_gate.py -q
uv run --frozen ruff check src/runtime/next tests/next/test_finished_board_gate_7553.py && uv run --frozen ruff format --check --force-exclude <changed files> && uv run --frozen mypy src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_decision_mapping.py
uv run --frozen ruff check --select C901 src/runtime/next/runtime_bridge.py src/runtime/next/runtime_bridge_decision_mapping.py
```

Record exact counts. Classify any red per the CLAUDE.md baseline-red gotcha (verify on the planning base).

## Risks & Mitigations

- **A Mission driven through `next` loses MissionRunCompleted.** Mitigation: the legitimate-position exemption, plus a positive control.
- **Double door read.** Reuse `status_read`. `tests/architectural/test_status_read_single_door.py` and any door-read counter tests (grep `read once` / `#7539` in tests) must stay green.
- **Sticky `accepted_at`.** The verdict requires a finished board. Add a cell: accepted, then a WP reopened to `in_progress` → implement dispatch, not terminal.
- **Exit code.** A `blocked` kind maps to the existing blocked exit code in `next_cmd`; no mapping changes. Mention it in the hand-off.

## Review Guidance

- Red→green: T005's commit is red on the base and green at the WP head.
- No run is started or advanced on the gated path: inspect the test assertions, not just the envelope.
- One door read, no new writer, complexity ≤ 15.
- The re-pin of the 5310 test is deliberate and documented.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
