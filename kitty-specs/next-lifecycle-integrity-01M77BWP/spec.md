# Mission Specification: next lifecycle integrity (#7548)

**Mission Branch**: `kitty/mission-next-lifecycle-integrity-01M77BWP` → lands on `fix/7548-next-lifecycle-integrity`
**Created**: 2026-11-12
**Status**: Draft
**Input**: Sub-epic #7548, `next` lifecycle-integrity half. Delivers #7553 and #7582, folds #5929 and #7565 (operator rulings 2026-11-12, recorded as Decision Moments in `decisions/`). #5099 is out of scope.

## Intent Summary (confirmed)

- **Primary actor:** an agent or operator driving a Mission with `spec-kitty next` and the work-package lifecycle commands.
- **Trigger:**
  - an advancing `next` call (`--result …`) on a Mission whose work-package board is finished (every WP approved or done), or that is accepted or landed;
  - a read-only `next` call;
  - a rejection or reopen of a WP back to `planned`.
- **Desired outcome:**
  - `next` never records a step as run unless it was issued and completed. On a finished board it says what to do instead.
  - A read-only `next` always tells the caller what to run next.
  - A rejection's subtask reset is recorded with what was completed and why, and the operator can narrow it to the subtasks the review concerns.
- **Invariants:**
  - The Mission run record is evidence: a step row exists only for a step that was issued and then completed.
  - `question` is present on a read-only envelope exactly when a decision is pending.
- **Canonical terms:** Mission (never "feature"), work package (WP), board (the WP lane state read through the status read door), run record (run journal + invocation lifecycle + `MissionNextInvoked` rows).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A finished Mission is not replayed (Priority: P1)

An agent finishes every WP of a Mission without driving each step through `next`, for example through slash commands. It then calls `spec-kitty next --result success`.
- Today the runtime starts a fresh run at `discovery` and walks specify, plan, tasks and analyze. It records a completed row for each step, though none ran.
- After the fix, `next` does not advance the run, records no step row, and returns:
  - a `blocked` envelope that names the acceptance command, when the Mission is not yet accepted;
  - the existing `terminal` envelope, once the Mission is accepted or landed.

**Why this priority**: Replayed rows are false evidence in the run record (#7553), and the benchmark harness uses `next` as its step authority. This is also open P1s #5929 and #7565.

**Independent Test**: Build a Mission whose WPs are all approved or done, with no run started, and drive `spec-kitty next --result success --json` through the CLI.
- Assert the envelope kind and error code.
- Assert that no run-journal step events, no lifecycle `completed` record and no `MissionNextInvoked` row with `decision_kind: step` were written.

**Acceptance Scenarios**:

1. **Given** a software-dev Mission with every WP approved, not accepted and no run started, **When** `next --result success` is called, **Then** the envelope is `kind=blocked` with `error_code=MISSION_AWAITING_ACCEPTANCE` and a remediation naming `spec-kitty accept` for that Mission, and no step row is recorded.
2. **Given** the same Mission after `accept` (the board is still finished), **When** `next --result success` is called repeatedly, **Then** every call returns `kind=terminal`, and no run is started or advanced.
3. **Given** a Mission whose persisted run has already been walked onto the DAG by the old behaviour (an issued `discovery`), **When** `next --result success` is called on its finished board, **Then** the same blocked or terminal answer is returned and the stale run is not advanced further.
4. **Given** a finished board, **When** `next --result failed` or `--result blocked` is called, **Then** no DAG step is issued (no fall-through to `discovery`).
5. **Given** a Mission still in implementation (some WPs not approved or done), **When** `next --result success` is called, **Then** behaviour is unchanged: the board-derived implement or review dispatch.
6. **Given** a Mission with no WPs (artifact-only) or a research/custom Mission type, **When** `next` is called, **Then** behaviour is byte-identical to today.

---

### User Story 2 - Read-only `next` says what to run next (Priority: P2)

An agent calls `spec-kitty next --json` without `--result` on a fresh Mission. It receives `kind=query`, `mission_state=not_started` and a null `question`, and does not know that `--result success` starts the loop.

**Why this priority**: This is recurring tracer friction (two Missions). It also contains one real defect: a pending first decision is dropped from the read-only envelope.

**Independent Test**: Call read-only `next --json` on a fresh software-dev Mission and on a Mission whose first step needs a decision.

**Acceptance Scenarios**:

1. **Given** a fresh Mission, **When** `next --json` is called without `--result`, **Then** the envelope carries `next_command` naming the advancing command (`spec-kitty next --agent <agent> --mission <handle> --result success`), and `question` stays null.
2. **Given** a Mission whose untouched run's first runtime decision is `decision_required`, **When** read-only `next --json` is called, **Then** `question`, `decision_id` and `options` are present, and `next_command` is absent.
3. **Given** any read-only envelope, **Then** `question` is non-null if and only if `decision_id` and `options` are present.

---

### User Story 3 - A rejection's subtask reset is recorded and can be narrowed (Priority: P2)

A reviewer rejects a WP back to `planned`. Today every subtask resets to `planned`. The reset is printed, but the status event does not record which subtasks were completed or why the reset happened. A rework that touches one subtask still has to re-mark all of them.

**Why this priority**: The run record must show what the rejection concerned (#7582). Re-marking churn is measured: subtask status is set 14 times by the model and 17 by the walker in the rc7 register.

**Independent Test**: Drive `spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file …` through the CLI on a WP whose subtasks are done, then read the status event log.

**Acceptance Scenarios**:

1. **Given** WP01 in review with T001 and T002 done, **When** it is rejected to `planned` without narrowing, **Then** both subtasks reset (the default stays a full reset), the output announces it, and the PLANNED transition event records the reset subtask ids, those previously completed and the reason.
2. **Given** the same WP, **When** it is rejected with `--reset-subtasks T002 --reason "<why>"`, **Then** only T002 resets, T001 stays done, and the event records the narrowed reset and its reason.
3. **Given** `--reset-subtasks` naming an id that is not on the WP's roster, **When** the move is run, **Then** it is refused before anything is written.
4. **Given** `--reset-subtasks` without an operator reason, **When** the move is run, **Then** it is refused before anything is written.
5. **Given** a narrowed rejection, **When** the WP is moved to `for_review` again, **Then** the existing subtask gate still blocks until the reset subtasks are marked done.

### Edge Cases

- **Acceptance recorded but a WP reopened afterwards** (the board is no longer finished): `next` follows the board (implement or review), not `terminal`. `accepted_at` is sticky and is never read alone.
- **Board finished, but the run already reached `accept` or completed through `next`:** the engine's own terminal path is unchanged.
- **A rejection from a lane other than `in_review`** (unclaim, reopen from approved or done): the same recording applies; narrowing is accepted on the same terms.
- **A subtask already `skipped`:** never reset (unchanged). The record lists it as neither reset nor completed.
- **Concurrency:** no new writer. The fix writes through the existing status and run-record doors only.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Finished board blocks on acceptance | As an agent, I want an advancing `next` on a finished, unaccepted board to return `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE`, and a remediation naming `spec-kitty accept --mission <handle>`, so that I am told what to do instead of being sent back to discovery. | High | Open | [build] | no — today the same fixture issues `discovery` |
| FR-002 | Accepted or landed Mission is terminal | As an agent, I want an advancing `next` on an accepted Mission with a still-finished board, or on a landed Mission, to return `kind=terminal`, so that the loop ends. | High | Open | [build] | no — today an accepted, unlanded fixture issues `discovery` |
| FR-003 | No step row without a run step | As an operator, I want a finished-board or terminal answer to start or advance no run and record no step completion (run journal, lifecycle `completed`, `MissionNextInvoked` with `decision_kind: step`), so that the run record stays evidence. | High | Open | [build] | no — today five false rows are written (tracer `upgrade-seeded-list-hint-01M6BV1A`) |
| FR-004 | Stale walked runs are not advanced | As an operator, I want a run that the old behaviour already pushed onto the DAG to be answered by FR-001/FR-002 when the board is finished, so that wedged Missions recover with no manual edit. | High | Open | [build] | no — a fixture with an issued `discovery` advances today |
| FR-005 | Failed or blocked results do not fall through | As an agent, I want `--result failed` and `--result blocked` on a finished board to issue no DAG step, so that no result value replays the lifecycle (#5929). | Medium | Open | [build] | no — paired with FR-001 on the same fixture |
| FR-006 | Unchanged outside the finished board | As a maintainer, I want implementation-phase dispatch, no-WP (artifact-only) Missions, and research/custom Mission types to behave exactly as before, so that the fix is local. | High | Open | [ratchet] | yes — positive control: FR-001's fixture with one WP still in progress must dispatch that WP |
| FR-007 | One finished-board predicate | As a maintainer, I want read-only and advancing `next` to ask the same predicate whether the board is finished and accepted, so that the two modes cannot disagree again. | Medium | Open | [build] | no — today query returns `accept`/`done` while advance returns `discovery` |
| FR-008 | Read-only envelope names the next command | As an agent, I want every read-only `next` envelope that carries no pending decision to include an additive `next_command` field naming the command to run next, so that I know how to proceed. | Medium | Open | [build] | no — the field is absent today |
| FR-009 | Pending first decision is not dropped | As an agent, I want read-only `next` to keep `question`, `decision_id` and `options` when an untouched run's first decision is `decision_required`, so that I can answer it. | Medium | Open | [build] | no — today they are dropped |
| FR-010 | Question iff decision pending | As a consumer of the `next` contract, I want `question` to be non-null on a read-only envelope exactly when `decision_id` and `options` are present, so that the field keeps one meaning. | Medium | Open | [ratchet] | yes — paired with FR-009 on the same fixture |
| FR-011 | Reset recorded on the transition | As an operator, I want a rejection or reopen to `planned` to record, on the PLANNED transition event, the subtasks reset, those previously completed and the reason, so that the record shows what the rejection concerned. | High | Open | [build] | no — today the transition carries no such record |
| FR-012 | Narrowed reset | As a reviewer, I want `move-task --to planned --reset-subtasks <ids> --reason "<why>"` to reset only the named subtasks and keep the rest, so that rework re-verifies only what was questioned. | Medium | Open | [build] | no — today every subtask resets |
| FR-013 | Narrowing is validated | As a maintainer, I want `--reset-subtasks` refused before any write when an id is not on the WP roster or no reason is given, so that a narrowed reset is always deliberate and well-formed. | Medium | Open | [build] | no — paired with FR-012 |
| FR-014 | Full reset stays the default | As a maintainer, I want a rejection without `--reset-subtasks` to keep resetting every non-skipped subtask (#2513), and the subtask gate to keep blocking `for_review` on a reset subtask, so that rework cannot pass the gate untouched. | High | Open | [ratchet] | yes — positive control: the narrowed case leaves T001 done on the same fixture |
| FR-015 | Announcement names the scope | As an operator, I want the human line and the JSON fields of the reset announcement to state whether the reset was full or narrowed, and its reason, so that the output matches the record. | Low | Open | [build] | no — today there is no narrowed or reason field |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added latency | An advancing `next` on a finished board completes in under 2 seconds on the test fixtures, and adds at most one metadata read per call. | Performance | Medium | Open |
| NFR-002 | Contract additivity | Every envelope change is additive. Existing `next` JSON fields keep their names, types and meanings, and the existing contract tests pass unchanged except where a row in this spec changes them on purpose. | Compatibility | High | Open |
| NFR-003 | Quality gates | Changed code passes `ruff check`, `ruff format --check --force-exclude`, and mypy with zero new issues. No function exceeds complexity 15. Coverage of the new code is at least 90%. | Maintainability | High | Open |
| NFR-004 | Red-first evidence | Every FR marked `[build]` has a test that fails on the planning base and passes at the end, driven through `spec-kitty next` or `move-task`. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Status through the read door | Mission status is read only through the status read door (`resolve_status_read`, ADR `2026-11-06-2`). Acceptance is read from Mission metadata through the canonical metadata loader. No second status reader. | Technical | High | Open |
| C-002 | No reducer or event-contract change | Do not change the reducer ordering or the `spec-kitty-events` contract. The reset record lives in the transition's existing free `policy_metadata`. | Technical | High | Open |
| C-003 | Out-of-scope surfaces | Do not touch consolidation, the review prompt assembly, `packs/built-in/`, or #5099 (one writer per checkout). Add no new size or ratchet gates. | Business | High | Open |
| C-004 | Existing doors only | No new writer to the run journal, the status event log or `mission-events.jsonl`. The frozen door-caller gates stay at their counts. | Technical | High | Open |
| C-005 | Invocation audit rows stay | The `MissionNextInvoked` row that records a blocked or terminal invocation (landed routing, #7539) is kept. It records that the call happened, not that a step ran. | Technical | Medium | Open |

### Key Entities

- **Finished board:** a software-dev Mission with at least one WP, every WP in `approved` or `done`, read through the status read door.
- **Acceptance:** the Mission's recorded acceptance (`accepted_at`). It counts only while the board is still finished.
- **Run record:** the run journal (`NextStepIssued` / `NextStepAutoCompleted`), invocation lifecycle records, and `MissionNextInvoked` rows.
- **Reset record:** `policy_metadata.rollback_reset` on the PLANNED transition. It holds the scope (full or narrowed), the reset subtask ids, the previously completed ids and the reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a finished-board fixture, 0 step rows are recorded across 10 consecutive `next --result success` calls (today: one per call). — [build] · no-op passable: no
- **SC-002**: The reproductions of #5929, #7565 and #7553 return a blocked or terminal answer on 100% of calls. — [build] · no-op passable: no
- **SC-003**: 100% of read-only envelopes either carry a pending decision (question + decision_id + options) or a `next_command`. — [build] · no-op passable: no
- **SC-004**: A narrowed rejection of 1 of N subtasks leaves N−1 subtasks done, and the event records which subtask was reset and why. — [build] · no-op passable: no
- **SC-005**: Every existing test in the targeted `next`, runtime, status and move-task suites passes unchanged, except the test that pinned the replay (`test_advance_declines_front_phase_on_all_approved_board`), which is re-pinned on purpose. — [ratchet] · no-op passable: yes

## Assumptions

- The `MissionNextInvoked` audit row for a blocked or terminal invocation is not a "step row" (C-005). #7553's "records nothing" is read as "records no step as run".
- #7553's sub-point "a `query` envelope always carries a question" is amended, not delivered literally. A two-lens research squad disproved it, and the operator ruled on 2026-11-12. The PR records the amendment.
- `MissionRunCompleted` and the retrospective gate are not reached through `next` for a Mission whose WPs finished outside the DAG. This is a residual, and a follow-up issue is filed.
- The assignee rebind on `move-task --to planned --agent <reviewer>` (tracer `startup-assess-cold-concurrency-01M3EQ9S`, F-3) is a separate defect, filed separately and not folded.

## Out of Scope / References

- **Refs:** #5797, #4898, #5670, #3932, #5112, #2513, #3578, #7540, #7543.
- **Excluded:** #5099 (proposed to move to #1795), #7197, #7547, #7578.
