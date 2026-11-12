# Work Packages: next lifecycle integrity (#7548)

**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `research/code-grounding.md`
**Tests**: required. Each `[build]` FR has a red-first test through the pre-existing entry point (Charter Standing Order 4, NFR-004).
**Organization**: four WPs. WP01 is the tidy-first foundation (IC-01). WP02 depends on WP01 and delivers the finished-board gate (IC-02). WP03 depends on WP01 and delivers the query envelope (IC-03). WP04 is independent and delivers the rollback reset (IC-04).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the pure `finished_board_verdict` (with acceptance freshness) + `FinishedBoardVerdict` to the cores leaf, with unit tests | WP01 | [P] |
| T002 | Add additive `next_command` and internal `suppress_step_pairing` to `Decision` / `DecisionEnvelope`; thread through `step_or_blocked` | WP01 | |
| T003 | Add I/O helpers `mission_accepted_at(primary_dir)` and `board_latest_transition_at(board)` | WP01 | [P] |
| T004 | Byte-identity regression: envelopes without `next_command` are unchanged | WP01 | |
| T020 | `PendingDecisionPrompt` value object + construction-time question ⇔ decision_id invariant | WP01 | |
| T005 | Red-first tests for the never-rewind gate (#7553, #5929, #7565), tree-snapshot no-row probes | WP02 | |
| T006 | Tidy-first: extract the run-start/snapshot segment of `_dn_bootstrap` (complexity headroom) | WP02 | |
| T007 | Implement `_dn_never_rewind_gate` before run start (software-dev, non-authoritative run) | WP02 | |
| T008 | Board-step accessor sharing the selector prefix (decline identity unchanged) | WP02 | |
| T022 | Widen the front phase to non-authoritative runs, any result | WP02 | |
| T023 | `next_cmd`: skip stale lifecycle pairing on a gate answer | WP02 | |
| T009 | Re-pin `test_advance_declines_front_phase_on_all_approved_board`; FR-006 controls; door-read count | WP02 | |
| T010 | Red-first tests for query `next_command` and the dropped first decision | WP03 | |
| T011 | Route an untouched run's first `decision_required` through the decision-required builder | WP03 | |
| T012 | Set `next_command` on every non-decision query envelope (shared verdict) | WP03 | |
| T013 | Human renderer prints `Next:` from `next_command` (query and blocked) | WP02 | |
| T014 | Docs: runtime-loop.md + runtime-next SKILL.md (start handshake, finished-board answers, invariant) | WP03 | [P] |
| T015 | Red-first CLI tests for the rollback reset record and narrowing | WP04 | |
| T016 | Add the `--reset-subtasks` option and its pre-write validation (roster, reason, target lane) | WP04 | |
| T017 | Compute the reset map before the PLANNED hop; record `policy_metadata.rollback_reset` | WP04 | |
| T018 | Narrow the subtask reset annotation to the named ids | WP04 | |
| T019 | Extend the announcement (human line + JSON scope/reason); cutover-eligibility pin test | WP04 | |

## WP01 – Foundations: finished-board verdict and additive `next_command` (Priority: P1)

**Goal**: Behaviour-preserving enablers: a single pure predicate, an additive envelope field, and an acceptance reader.
**Independent test**: Unit tests for the predicate; the envelope byte-identity suite is unchanged.
**Prompt**: `tasks/WP01-foundations-verdict-and-next-command.md`

T001 Add the pure `finished_board_verdict` + `FinishedBoardVerdict` to the cores leaf, with unit tests (WP01)
T002 Add additive `next_command` to `Decision` / `DecisionEnvelope` and thread it through `step_or_blocked` (WP01)
T003 Add I/O helpers `mission_accepted_at` and `board_latest_transition_at` (WP01)
T004 Byte-identity regression: envelopes without `next_command` are unchanged (WP01)
T020 `PendingDecisionPrompt` value object + construction-time invariant (WP01)

**Dependencies**: none.

## WP02 – Advancing `next` never rewinds a finalized software-dev board (Priority: P1)

**Goal**: FR-001 to FR-007 and FR-016. With a finalized board and a non-authoritative run, an advancing `next` never issues a DAG step before the board's step. A finished board answers `blocked` (MISSION_AWAITING_ACCEPTANCE) or `terminal` (fresh acceptance). A non-dispatchable board step answers `blocked` with a resume command. Nothing is recorded as run.
**Independent test**: CLI `next --result success|failed|blocked --json` on a finished-board fixture; assert the envelope and that no run or step row is written.
**Prompt**: `tasks/WP02-finished-board-gate.md`

T005 Red-first CLI tests for the finished-board gate (WP02)
T006 Tidy-first: extract the run-start/snapshot segment of `_dn_bootstrap` (WP02)
T007 Implement `_dn_never_rewind_gate` before run start (WP02)
T008 Board-step accessor sharing the selector prefix (WP02)
T022 Widen the front phase to non-authoritative runs, any result (WP02)
T023 `next_cmd`: skip stale lifecycle pairing on a gate answer (WP02)
T013 Human renderer prints `Next:` from `next_command` (WP02)
T009 Re-pin the 5310 decline test; FR-006 controls; door-read count (WP02)

**Dependencies**: Depends on WP01.

## WP03 – Read-only `next` names the next command (Priority: P2)

**Goal**: FR-008 to FR-010, plus FR-007 on the query side.
**Independent test**: Read-only `next --json` on fresh, in-flight, finished, accepted and first-decision fixtures.
**Prompt**: `tasks/WP03-query-next-command.md`

T010 Red-first tests for query `next_command` and the dropped first decision (WP03)
T011 Route an untouched run's first `decision_required` through the decision-required builder (WP03)
T012 Set `next_command` on every non-decision query envelope (WP03)
T014 Docs: runtime-loop.md + runtime-next SKILL.md (WP03)

**Dependencies**: Depends on WP01.

## WP04 – Recorded and narrowable rollback subtask reset (Priority: P2)

**Goal**: FR-011 to FR-015 (#7582).
**Independent test**: `move-task --to planned` through the CLI with and without `--reset-subtasks`; read the status event log.
**Prompt**: `tasks/WP04-rollback-reset-record.md`

T015 Red-first CLI tests for the rollback reset record and narrowing (WP04)
T016 Add the `--reset-subtasks` option and its pre-write validation (WP04)
T017 Compute the reset map before the PLANNED hop; record `policy_metadata.rollback_reset` (WP04)
T018 Narrow the subtask reset annotation to the named ids (WP04)
T019 Extend the announcement; cutover-eligibility pin test (WP04)

**Dependencies**: none.

## Parallelization

- WP01 and WP04 can start in parallel.
- After WP01, WP02 and WP03 can run in parallel: their files do not overlap.
