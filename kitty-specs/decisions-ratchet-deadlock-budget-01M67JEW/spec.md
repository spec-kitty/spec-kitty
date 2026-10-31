# Decisions Ratchet: One Wall Clock, Owned by the Harness

**Mission**: `decisions-ratchet-deadlock-budget-01M67JEW`
**Type**: software-dev
**Branch**: `issue-6773-decisions-ratchet-deadlock-budget`
**Closes**: #6773 — "Flaky under xdist: `test_terminal_calls_do_not_deadlock_with_other_decision_lock_holders` times out its thread joins"

---

## Purpose

`tests/specify_cli/decisions/test_service_terminal_concurrency.py` carries the NFR-002
"no deadlock between terminal calls, an open, the doctor repair and a status-lock
writer" ratchet. Under xdist on a loaded machine it has gone red without a deadlock
existing, and it was reported as a pre-existing flake (#6773).

This mission makes that ratchet's **verdict** deterministic: the test, not the
product's wall-clock budgets, decides what "deadlocked" means. A participant that is
merely slow may never be reported as a deadlock, and a participant that is genuinely
stuck may never be reported as healthy — with the failure naming the stuck
participant and the lock it is waiting on.

## Grounding (evidence gathered before scoping, current `main` @ `512567eee7`)

1. **The scenario has no lock-order cycle.** Every participant that takes two locks
   takes the decisions lock before the status lock: `resolve`/`defer`/`cancel`
   (`decisions/service.py` holds `_decisions_lock` across the index save, the artifact
   write and the terminal event, whose append takes `feature_status_lock`),
   `open_decision` (same order), the doctor's `_repair` (decisions lock alone), and the
   status-lock writer (status lock alone). No path anywhere in the four takes the
   status lock first and then waits for the decisions lock, so the scenario cannot
   deadlock by ordering.
2. **It does not reproduce on the reported command.** The issue's command
   (`pytest tests/specify_cli/cli/commands/test_decision*.py tests/specify_cli/decisions
   -q -n 4 --dist loadfile`) ran 7 times (2,107 test executions); the file alone ran 14
   times under `-n 4` (including 6 runs under 6 extra CPU burners); the single test ran
   40 times in one process; and the file ran serially, pinned to one core. All green.
   The flake is rare and load-shaped, not reproducible on demand.
3. **The one way this ratchet reds with no deadlock is a wall-clock budget it does not
   own.** A participant that holds the decisions lock for longer than the product's
   fixed `_LOCK_ACQUIRE_TIMEOUT_S` (10 s, `decisions/service.py` and
   `_decisions_doctor.py`) makes its peers fail with `DecisionError(LOCK_TIMEOUT)` /
   `LockAcquireTimeout` — a *retryable refusal by design*, not a deadlock — and
   `_Worker.finish()` reports it as `assert self.error is None`. Proven deterministically:
   pin the acquire bound to 0.2 s and slow every holder by 0.4 s (finite: each holder
   releases), and the ratchet reds with
   `DecisionError("Timed out after 0.2s waiting for the decisions lock ...")` while every
   worker finishes. Same shape as a 10 s fsync stall on a loaded box; the test cannot
   tell "slow" from "stuck".
4. **The joins the issue title blames are in the safe direction.** `thread.join(0.5)` /
   `thread.join(0.3)` in the two preceding tests are followed by `assert
   thread.is_alive()`: load can only make those *more* likely to pass. The unsafe wait
   is the opposite one — `_Worker.finish()`'s fixed 30 s join, which turns any
   unbounded-by-the-test wait into a bare `worker did not finish`.

Conclusion: a **Tier-2 harness defect** (a correctness ratchet that leans on wall-clock
budgets it does not own), not a real lock bug. `docs/development/testing/testing-flakiness.md`
prescribes the fix: remove the wall-clock dependency, do not retry.

## User Scenarios & Testing

### User Story 1 - A slow machine is never reported as a deadlock (Priority: P1)

As a maintainer reading a red CI run, I want the decisions coexistence ratchet to go red
only when a participant is genuinely stuck, so that a loaded runner does not cost me a
review cycle chasing a deadlock that never happened.

**Why this priority**: this is the reported defect — a false red erodes trust in the
ratchet and in every other red on the same run.

**Independent Test**: pin the ambient decisions-lock acquire bound to a value smaller
than the holders' run time, run the coexistence scenario, and assert every participant
finishes and the doctor report is clean. Red before the fix (`DecisionError(LOCK_TIMEOUT)`),
green after.

**Acceptance Scenarios**:

1. **Given** the coexistence scenario runs under an ambient acquire bound tighter than a
   participant's legitimate hold, **When** every holder eventually releases, **Then** all
   four workers finish without an error and the doctor reports the ledger clean.
2. **Given** the same scenario with no ambient bound at all, **When** it runs, **Then**
   it stays green (the scenario's own behaviour is unchanged).

---

### User Story 2 - A genuinely stuck participant still reds, and says who (Priority: P1)

As a maintainer, I want the ratchet's deadlock verdict to fire, and to name the stuck
participant and the lock it is waiting on, so that a real regression is diagnosed from
the failure output instead of a bisect.

**Why this priority**: making the test tolerant of slowness must not make it blind to a
deadlock; the ratchet is the only guard on this lock span.

**Independent Test**: run a worker that blocks forever, finish it with the harness's
backstop budget, and assert the harness raises with a report naming the worker state and
the decisions lock.

**Acceptance Scenarios**:

1. **Given** a participant that never finishes, **When** the harness joins it, **Then**
   the backstop fails the test inside its budget and the failure carries a thread dump
   (and the recorded holder of the decisions lock when one is held).
2. **Given** a participant that finishes just inside the budget, **When** the harness
   joins it, **Then** the test passes — the backstop is a deadlock detector, not a
   latency assertion.

---

### User Story 3 - The ratchet still asserts what it always asserted (Priority: P2)

As a maintainer, I want the scenario's substance untouched — one terminal event per
decision, a clean doctor report, the pause/interleaving guarantees — so that the flake
fix cannot become a quiet weakening.

**Why this priority**: "make the test deterministic" must not become "make the test
easier".

**Independent Test**: the existing assertions in the file run unchanged, and the
`@pytest.mark.quarantine` / skip / xfail / retry surfaces stay untouched.

**Acceptance Scenarios**:

1. **Given** the fixed file, **When** it runs, **Then** no assertion was removed, no test
   is skipped/xfailed/quarantined, and the resolved-event-count and doctor-clean
   assertions are still there.

### Edge Cases

- **A holder that stalls past the product's 10 s bound**: must not be reported as a
  deadlock; covered by User Story 1 (the scenario pins the bound, so the scenario's
  verdict cannot depend on it).
- **A holder that never releases**: must red inside the harness budget, not hang the
  session, and must not leave a live thread spinning into later tests of the same
  xdist worker.
- **A participant that raises before it reaches the rendezvous**: keeps the existing
  `_WAIT_S` event backstop, whose failure names the missed rendezvous.
- **The whole test exceeding `pytest-timeout`**: the harness budget must stay below the
  test's `@pytest.mark.timeout` marker so the harness verdict wins over a bare timeout.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Scenario owns the acquire bound | As a maintainer, I want the coexistence scenario to pin the decisions-lock acquire bound it runs under, so that an ambient product bound cannot turn a slow holder into a failed worker. | High | Open | [build] | no |
| FR-002 | One deadlock budget | As a maintainer, I want a single named backstop budget to decide "stuck", derived from the longest legitimate wait inside the scenario, so that no second wall clock competes with it. | High | Open | [build] | no |
| FR-003 | Diagnostic deadlock verdict | As a maintainer, I want a join that times out to fail with a report naming the live participants and the decisions lock, so that a real deadlock is diagnosable from the failure text. | High | Open | [build] | no |
| FR-004 | Stuck participant still reds | As a maintainer, I want a participant that never finishes to fail the ratchet inside the budget, so that removing the false red does not remove the guard. | High | Open | [ratchet] | no |
| FR-005 | Existing guarantees preserved | As a maintainer, I want the scenario's original assertions (one terminal event per decision, clean doctor report, pause-driven interleavings) unchanged, so the flake fix cannot weaken it. | High | Open | [ratchet] | no |
| FR-006 | Flake-surface row recorded | As a maintainer, I want this surface recorded in the flakiness audit table with its tier and disposition, so the next reader does not re-diagnose it. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Green-path cost unchanged | The fixed file's green-path wall clock stays within 15 s under `-n 4 --dist loadfile` on the development host (today: ~5-7 s serial, ~6-9 s under `-n 4`); no new sleep in the green path. | Performance | High | Open |
| NFR-002 | Budget below the pytest backstop | The harness deadlock budget plus the scenario's rendezvous wait remain below the test's `@pytest.mark.timeout` marker, so a hang produces the harness verdict, not a bare `Failed: Timeout`. | Reliability | High | Open |
| NFR-003 | No leaked live work | A red run of the never-released-holder proof leaves no thread spinning or holding a lock into later tests of the same process. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-only diff | No product behaviour changes: `_LOCK_ACQUIRE_TIMEOUT_S` and the lock primitives under `src/` stay as they are; the change is confined to the test file and the testing docs. | Technical | High | Open |
| C-002 | No silencing | No skip, xfail, `quarantine` marker, retry, weakened assertion or widened tolerance; `docs/development/testing/testing-flakiness.md` Tier-2 policy is the authority. | Technical | High | Open |
| C-003 | In-process isolation | The fix must not depend on xdist internals, worker count, `--dist` mode or `-p` plugins; it must hold at `-n0` and `-n 4` alike. | Technical | Medium | Open |

### Key Entities

- **Coexistence scenario**: the four-participant rendezvous (terminal calls, an `open`, the
  doctor repair, a status-lock writer) that the ratchet runs.
- **Deadlock budget**: the single wall clock after which an unfinished participant is
  declared stuck.
- **Deadlock report**: the thread dump plus the decisions-lock holder record attached to a
  failed join.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 30 consecutive `-n 4 --dist loadfile` runs of the fixed file are green. —
  [ratchet] · no-op passable: no
- **SC-002**: With a participant that never finishes, the ratchet fails inside its budget
  and the failure text names the stuck thread state and the decisions lock. — [build] · no-op passable: no
- **SC-003**: With every holder finite, the ratchet is green even when the ambient acquire
  bound is tighter than a legitimate hold. — [build] · no-op passable: no
- **SC-004**: The flakiness audit table has a row for this surface (tier, root cause,
  disposition, evidence), and `check_docs_freshness --ci` reports errors=0. — [build] · no-op passable: no
