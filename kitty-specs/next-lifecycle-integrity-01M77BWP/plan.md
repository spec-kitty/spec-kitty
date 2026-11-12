# Implementation Plan: next lifecycle integrity (#7548)

**Branch**: `kitty/mission-next-lifecycle-integrity-01M77BWP` (lands on `fix/7548-next-lifecycle-integrity`) | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/next-lifecycle-integrity-01M77BWP/spec.md`

## Summary

This Mission fixes two run-record integrity defects in the `next` loop and the work-package (WP) lifecycle.

1. **Finished-board gate in advancing `next` (#7553, #5929, #7565).** The gate runs during bootstrap, after the one status read-door read and *before* `get_or_start_run`.
   - It fires when the board is finished and no persisted run legitimately sits on a WP-iteration or accept step.
   - It returns `blocked`, with `error_code=MISSION_AWAITING_ACCEPTANCE` and the accept command in a new additive `next_command` field, when the Mission is not accepted.
   - It returns `terminal` when the Mission is accepted.
   - Either way, it starts, advances and records nothing.
   - A single pure predicate in `runtime_bridge_cores` gives the verdict for advance and query alike.
2. **Query envelopes say what to run next.**
   - Every read-only envelope that has no pending decision gains `next_command`.
   - The bug that dropped `question`/`decision_id`/`options` on an untouched run's first `decision_required` is fixed.
3. **Rollback subtask reset is recorded and can be narrowed (#7582).**
   - The PLANNED hop's `policy_metadata` gains `rollback_reset` (scope, reset ids, previously completed, reason), computed before the hop.
   - `move-task --to planned --reset-subtasks <ids>` resets only the named ids. It requires `--note`/`--reason` and is validated against the roster before any write.
   - A full reset stays the default.

## Technical Context

**Language/Version**: Python 3.11+ (CLI, mypy strict on new code)
**Primary Dependencies**: typer, rich, `spec_kitty_events` (unchanged: `policy_metadata` is already a free dict), pytest
**Storage**: Local files. `meta.json` (read only: `accepted_at`), status event log `status.events.jsonl` (existing transition door), run index / run journal (read-only lookup on the gated path), `mission-events.jsonl` (unchanged door)
**Testing**: pytest, red-first through the real entry points:
- `CliRunner` over `spec-kitty next`, in `tests/next/test_next_command_integration.py` style plus the `_scaffold` fixture of `tests/next/test_finalized_task_routing.py`;
- `move-task` via the `tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py` harness;
- bridge-level unit tests beside `tests/runtime/next/test_merged_mission_terminal.py`;
- pure-predicate unit tests.

**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single (existing `src/` layout)
**Performance Goals**: an advancing `next` on a finished board stays under 2 s. The gate adds one `meta.json` read and one read-only run-index lookup, and no extra status read-door read (#7539 "read once").
**Constraints**:
- status only through `resolve_status_read`;
- metadata only through `load_meta_or_empty`;
- no new writer;
- no reducer or event-contract change;
- complexity ≤ 15 (`_dn_bootstrap` is at 15, so the run-start segment is extracted first);
- additive envelope fields only.

**Scale/Scope**: 4 work packages, about 10 source files, about 12 test files.

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | ✅ One finished-board predicate (cores) used by both modes. Acceptance is read via the canonical metadata loader. The reset record lives on the transition only (the annotation keeps the per-id lanes). |
| Architectural alignment / status read door (ADR `2026-11-06-2`) | ✅ The gate reuses the bootstrap's one door read (`status_read.board`). No second reader. |
| Standing Order 2 (tidy-first) | ✅ IC-01 is a behaviour-preserving enabler (extracts headroom from `_dn_bootstrap`, plumbs the additive field). |
| Standing Order 4 (red-first) | ✅ Every `[build]` FR gets a test that is red on the planning base, driven through `next` / `move-task`. |
| Standing Order 5 (gates) | ✅ No new allowlist or ratchet. The existing door gates (`test_event_log_writes_gate`, `test_status_read_single_door`, `test_inline_meta_read_gate`, `test_run_index_single_reader`, `test_bridge_cores_import_boundary`) must stay green unchanged. |
| Escalation rulings | ✅ Recorded in `decisions/` (fold set, envelope, state map, query contract, subtask policy). |
| NO_FULL_HEAVY_SUITES_IN_MISSION | ✅ Targeted suites plus named gate files only. |
| Out-of-scope surfaces | ✅ No consolidation, review prompt, `packs/built-in` or #5099 changes. |

No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/next-lifecycle-integrity-01M77BWP/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/next-envelope-additions.md
├── contracts/rollback-reset-record.md
├── research/code-grounding.md, research/foldable-issues.md
├── traces/ (tooling-friction.md, approach.md, design-decisions.md)
└── decisions/
```

### Source Code (repository root)

```
src/runtime/next/
├── decision.py                         # + Decision.next_command (additive)
├── runtime_bridge_cores.py             # + DecisionEnvelope.next_command, + finished_board_verdict (pure)
├── runtime_bridge.py                   # bootstrap: extract run-start helper; finished-board gate before run start
├── runtime_bridge_decision_mapping.py  # expose finished board_step from the selector (no decline-collapse loss)
└── runtime_bridge_query.py             # next_command on non-decision query envelopes; first decision_required fix
src/specify_cli/cli/commands/
├── next_cmd.py                         # human renderer prints next_command
└── agent/tasks.py, tasks_move_task.py, tasks_move_task_executor.py, tasks_move_task_hops.py  # --reset-subtasks, rollback_reset
docs/architecture/runtime-loop.md       # finished-board answers, next_command, the start handshake
src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md  # envelope table: next_command, MISSION_AWAITING_ACCEPTANCE
```

**Structure Decision**: The existing single-project layout. No new modules: the predicate joins the pure cores leaf, and the rest are edits in place.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Tidy-first enablers (behaviour-preserving)

- **Purpose**: Make room for the gate and the new field without behaviour change. Extract the run-start/snapshot segment of `_dn_bootstrap` (complexity 15) into a helper, add `next_command: str | None = None` to `Decision` and `DecisionEnvelope` (emitted in `to_dict` only when set), and add the pure `finished_board_verdict(board_step, accepted) -> FinishedBoardVerdict` (NONE / AWAITING_ACCEPTANCE / ACCEPTED) to the cores leaf.
- **Relevant requirements**: FR-007 (predicate), NFR-002, NFR-003.
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_cores.py`, `decision.py`.
- **Sequencing/depends-on**: none.
- **Risks**:
  - `test_bridge_cores_import_boundary.py` (cores must stay a leaf);
  - byte-identical envelopes when `next_command` is None (`tests/specify_cli/next/test_next_output_preservation.py`).

### IC-02 — Finished-board gate in advancing `next`

- **Purpose**: Stop advancing `next` from falling through to the DAG on a finished board. Answer `blocked` (MISSION_AWAITING_ACCEPTANCE, `next_command` = accept) or `terminal` (accepted), before any run start or advance.
- **Relevant requirements**: FR-001 to FR-007, FR-003 and C-005 (keep the blocked/terminal `MissionNextInvoked` audit row).
- **Affected surfaces**: `runtime_bridge.py` (`_dn_bootstrap`, new `_dn_finished_board_gate`), `runtime_bridge_decision_mapping.py` (the selector reports `accept`/`done` instead of collapsing into a bare decline, or a sibling accessor does), and a read-only run lookup through `_io_seam._existing_run_ref`.
- **Gate rule**: fire iff the board step is `accept`/`done` AND (no persisted run, OR the run's `issued_step_id` ∉ {implement, review, accept}). A run legitimately at a WP-iteration or accept step keeps the engine path, so `MissionRunCompleted` and the retrospective gate stay reachable for Missions driven through `next`.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - re-pin `test_advance_declines_front_phase_on_all_approved_board` (5310) on purpose;
  - owned-checkout path (`primary_metadata_dir` from the mission context);
  - the frozen run-journal and run-index single-reader gates (read-only lookup only);
  - an unreadable `meta.json` reads as not accepted (fail toward blocked, never terminal).

### IC-03 — Query envelopes name the next command

- **Purpose**:
  - Every read-only envelope with no pending decision carries `next_command`:
    - the advance command for not_started or an in-flight run;
    - the accept command for a finished, unaccepted board;
    - the consolidate command for an accepted, unlanded Mission;
    - none once landed.
  - An untouched run's first `decision_required` keeps question, decision_id and options.
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-007 (same predicate).
- **Affected surfaces**: `runtime_bridge_query.py`, `next_cmd.py` (human renderer), `docs/architecture/runtime-loop.md`, runtime-next SKILL.md.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - the merged short-circuit query (`terminal_kind=query`) stays without `next_command`;
  - the specify prompt's replay guard (packs) keys on `kind`/`mission_state`/`preview_step`, all of which stay unchanged;
  - `test_json_contract_enumeration.py` triage for the new key.

### IC-04 — Recorded and narrowable rollback reset

- **Purpose**:
  - Compute the reset map and summary before the PLANNED hop.
  - Record `policy_metadata.rollback_reset` on that hop.
  - Add `--reset-subtasks` (comma-separated ids, needs `--note`/`--reason`, roster-validated, refused before any write).
  - Extend the human line and JSON with scope and reason.
- **Relevant requirements**: FR-011 to FR-015.
- **Affected surfaces**: `agent/tasks.py` (option), `tasks_move_task.py` (state, validation, output), `tasks_move_task_executor.py` (`_mt_rollback_subtasks_reset`, `_RollbackResetSummary`), `tasks_move_task_hops.py` (`_mt_hop_policy_metadata`, `_build_claim_review_override`).
- **Sequencing/depends-on**: none (independent of IC-01 to IC-03).
- **Risks**:
  - `_do_move_task` is at complexity 15, so validation goes into a helper;
  - `cutover_eligibility._policy_metadata_carries_runtime_evidence` counts the new key (harmless, pinned by a test);
  - `test_status_events_writes_gate.py`;
  - `tests/specify_cli/cli/commands` is out of the per-PR CI matrix, so run it explicitly.
