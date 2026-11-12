# Work Packages: next lifecycle integrity (#7548)

**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `research/code-grounding.md`
**Tests**: required. Each `[build]` FR has a red-first test through the pre-existing entry point (Charter Standing Order 4, NFR-004).
**Organization**: four WPs. WP01 is the tidy-first foundation (IC-01). WP02 depends on WP01 and delivers the finished-board gate (IC-02). WP03 depends on WP01 and delivers the query envelope (IC-03). WP04 is independent and delivers the rollback reset (IC-04).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the pure `finished_board_verdict` + `FinishedBoardVerdict` to the cores leaf, with unit tests | WP01 | [P] |
| T002 | Add additive `next_command` to `Decision` / `DecisionEnvelope` and thread it through `step_or_blocked` | WP01 | |
| T003 | Add the I/O helper `mission_is_accepted(primary_metadata_dir)` (canonical meta loader, fail-closed) | WP01 | [P] |
| T004 | Byte-identity regression: envelopes without `next_command` are unchanged | WP01 | |
| T005 | Red-first CLI tests for the finished-board gate (#7553, #5929, #7565 reproductions) | WP02 | |
| T006 | Tidy-first: extract the run-start/snapshot segment of `_dn_bootstrap` (complexity headroom) | WP02 | |
| T007 | Implement `_dn_finished_board_gate` before run start: blocked or terminal, no run touched | WP02 | |
| T008 | Expose the finished board step from the board selector without changing decline behaviour | WP02 | |
| T009 | Re-pin `test_advance_declines_front_phase_on_all_approved_board` and add the non-regression controls (FR-006) | WP02 | |
| T010 | Red-first tests for query `next_command` and the dropped first decision | WP03 | |
| T011 | Route an untouched run's first `decision_required` through the decision-required builder | WP03 | |
| T012 | Set `next_command` on every non-decision query envelope (shared verdict) | WP03 | |
| T013 | Human renderer prints `Next:` from `next_command` | WP03 | |
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
T003 Add the I/O helper `mission_is_accepted(primary_metadata_dir)` (WP01)
T004 Byte-identity regression: envelopes without `next_command` are unchanged (WP01)

**Dependencies**: none.

## WP02 – Advancing `next` never replays a finished board (Priority: P1)

**Goal**: FR-001 to FR-007. On a finished board, an advancing `next` returns `blocked` (MISSION_AWAITING_ACCEPTANCE) or `terminal` (accepted), and it starts, advances and records nothing.
**Independent test**: CLI `next --result success|failed|blocked --json` on a finished-board fixture; assert the envelope and that no run or step row is written.
**Prompt**: `tasks/WP02-finished-board-gate.md`

T005 Red-first CLI tests for the finished-board gate (WP02)
T006 Tidy-first: extract the run-start/snapshot segment of `_dn_bootstrap` (WP02)
T007 Implement `_dn_finished_board_gate` before run start (WP02)
T008 Expose the finished board step from the board selector (WP02)
T009 Re-pin the 5310 decline test; add the FR-006 non-regression controls (WP02)

**Dependencies**: Depends on WP01.

## WP03 – Read-only `next` names the next command (Priority: P2)

**Goal**: FR-008 to FR-010, plus FR-007 on the query side.
**Independent test**: Read-only `next --json` on fresh, in-flight, finished, accepted and first-decision fixtures.
**Prompt**: `tasks/WP03-query-next-command.md`

T010 Red-first tests for query `next_command` and the dropped first decision (WP03)
T011 Route an untouched run's first `decision_required` through the decision-required builder (WP03)
T012 Set `next_command` on every non-decision query envelope (WP03)
T013 Human renderer prints `Next:` from `next_command` (WP03)
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
