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
   - (Squad revision) The gate is scoped to software-dev and widened to **never rewind**. It applies whenever a finalized board exists and the run is not authoritative. A board step that cannot be dispatched (a WP in progress or claimed) returns `blocked` with a resume command (FR-016), and acceptance must be newer than the board's latest WP transition. See IC-02.
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

**Scale/Scope**: 4 work packages, about 10 source files, about 12 test files. The gate is scoped to the software-dev family (research, documentation, plan and custom Missions are unchanged).

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
├── runtime_bridge.py                   # bootstrap: extract run-start helper; never-rewind gate before run start; widened front phase
├── runtime_bridge_decision_mapping.py  # board-step accessor sharing the selector prefix
└── runtime_bridge_query.py             # next_command on non-decision query envelopes; first decision_required fix
src/specify_cli/cli/commands/
├── next_cmd.py                         # human renderer prints next_command; pairing skip (owned by WP02)
└── agent/tasks.py, tasks_move_task.py, tasks_move_task_executor.py, tasks_move_task_hops.py  # --reset-subtasks, rollback_reset
docs/architecture/runtime-loop.md       # finished-board answers, next_command, the start handshake
src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md  # envelope table: next_command, MISSION_AWAITING_ACCEPTANCE
```

**Structure Decision**: The existing single-project layout. No new modules: the predicate joins the pure cores leaf, and the rest are edits in place.

## Complexity Tracking

None.

## Implementation Concern Map

> Revised after the post-tasks adversarial squad (architecture and test lenses) and three more operator rulings (2026-11-12): widen to never-rewind, the question invariant enforced by construction, and acceptance freshness. Findings and their dispositions are in `research.md` §Squad dispositions.

### IC-01 — Tidy-first enablers (behaviour-preserving)

- **Purpose**: Additive scaffolding only. Nothing calls it yet, except where a validation is added at construction.
  - Pure `finished_board_verdict(board_step, accepted_at, latest_transition_at)` in the cores leaf.
  - Additive `Decision.next_command` (serialized only when set).
  - An internal, non-serialized `Decision.suppress_step_pairing` flag. A gate answer sets it so `next_cmd` does not pair a stale `started` record as completed.
  - A validated `PendingDecisionPrompt` value object (`decision_id`, `question`, `input_key`, `options`), plus a `Decision.__post_init__` check for kinds `query`/`decision_required`:
    - `question` set ⇔ `decision_id` set;
    - when set, `options` or `input_key` is present.
  - I/O helpers `mission_accepted_at(primary_dir)` (via `load_meta_or_empty`, which never raises) and `board_latest_transition_at(board)`.
- **Relevant requirements**: FR-002 (freshness), FR-007, FR-010, NFR-002, NFR-003.
- **Affected surfaces**: `runtime_bridge_cores.py`, `decision.py`, `runtime_bridge_io.py`.
- **Sequencing/depends-on**: none.
- **Risks**:
  - existing builders that violate the new invariant: grep and fix within the owned files, or hand off;
  - the cores leaf import gate.

### IC-02 — Advancing `next` never rewinds a finalized software-dev board

- **Purpose**: FR-001 to FR-007 and FR-016.
- **Gate placement**: in `_dn_bootstrap`, after `_dn_progress` and before the run start. The gate applies only to `mission_type == software-dev` (the #3407 precedent) with a finalized board, and only when the persisted run is **not authoritative**: there is no run, the run is untouched, or its issued step is a planning step before analyze (`RunStateMissing` falls through to the existing loader error).
- **Gate answers**:
  - finished board: `blocked` MISSION_AWAITING_ACCEPTANCE, or `terminal` when the acceptance is fresh;
  - board step implement/review that cannot be dispatched: `blocked`, a named code, the WP named, and a resume `next_command`;
  - dispatchable board step: falls through to `_dn_finalized_board_override`, now widened from "untouched and success" to "not authoritative, any result";
  - `blocked:*`: the existing board blocked decision.
- **Board accessor**: the gate reads the board through a NEW accessor that shares `_resolve_wp_board_action`'s prefix (surface, context, task error, progress, override step). It does not change `_board_step_action` (`_WP_BOARD_DECLINE` identity is unchanged), and it reuses the bootstrap's single `status_read`.
- **Pairing**: `next_cmd._dispatch_advancing_mode` skips `pair_previous_lifecycle_record` for a decision with `suppress_step_pairing`. The renderer prints `Next:` for every decision that carries `next_command` (query and blocked).
- **Affected surfaces**: `runtime_bridge.py`, `runtime_bridge_decision_mapping.py`, `next_cmd.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - the blocked/terminal `MissionNextInvoked` row adds a second door read (`_consolidated_target_dir`); pin it with a count test;
  - `_dn_bootstrap` complexity;
  - no new writer.

### IC-03 — Query envelopes name the next command

- **Purpose**: FR-007 to FR-010 on the query side.
- **Steps**:
  - `_query_resolve_primary` also returns the PRIMARY metadata dir.
  - `query_current_state` computes the override step and the verdict once, and passes them into dispatch.
  - A first `decision_required` on an untouched run keeps its decision fields (via `PendingDecisionPrompt`) **and** sets `next_command` to the advance command, because the decision is not yet pending and cannot be answered.
  - `next_command` is applied to every non-decision envelope, including the `task_error` early return and the no-WP runtime-terminal row (accept, or consolidate when accepted). It is not applied after landing.
  - Docs: runtime-loop.md and the runtime-next SKILL.md.
- **Affected surfaces**: `runtime_bridge_query.py`, the docs.
- **Sequencing/depends-on**: IC-01.

### IC-04 — Recorded and narrowable rollback reset

- **Purpose**: FR-011 to FR-015.
- **Steps**:
  - Validation runs right after `_mt_resolve_targets`, before `_mt_finalize_plan` commits the review-cycle artifact.
  - One `(reset_map, summary)` is computed onto the state before the transitions. Both `_mt_hop_policy_metadata` (the PLANNED hop) and `_build_claim_review_override` read it (single authority).
  - The pipeline merge `{**request, **added}` keeps `lane_head`/`wp_window`.
  - A skipped id in `--reset-subtasks` is refused.
- **Affected surfaces**: the move-task modules.
- **Sequencing/depends-on**: none.
