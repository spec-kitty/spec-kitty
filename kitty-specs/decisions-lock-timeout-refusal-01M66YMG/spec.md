# Mission Specification: Decisions Lock Timeout Refusal

**Mission Branch**: `issue-6763-decisions-lock-timeout-refusal`
**Created**: 2026-10-30
**Status**: Draft
**Input**: "Decisions lock timeouts in doctor --repair, next and decision repair-runtime-lock escape as a raw LockAcquireTimeout traceback" (spec-kitty/spec-kitty#6763)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `doctor decisions --repair` refuses a busy ledger cleanly (Priority: P1)

An operator runs `spec-kitty doctor decisions --mission <m> --repair` (with or without
`--json`) while another decision command holds `decisions/index.json.lock`. Instead of a
Python traceback, the command reports a lock-timeout refusal naming the lock and the wait,
says nothing was written and to retry, and exits 1.

**Why this priority**: `--repair` is the maintenance command operators run exactly when the
ledger is in a bad state — the moment a second writer is most likely. A traceback there is
unactionable and `--json` callers get no document at all.

**Independent Test**: Hold the lock, run `doctor decisions --repair --json`, assert one JSON
document carrying the timeout code, exit 1, and an unchanged ledger directory.

**Acceptance Scenarios**:

1. **Given** another writer holds the decisions lock for longer than the bounded wait, **When** the operator runs `doctor decisions --mission <m> --repair`, **Then** the command prints a lock-timeout refusal naming the lock path and the wait, says nothing was written, and exits 1 — no traceback.
2. **Given** the same held lock, **When** the operator runs the same command with `--json`, **Then** stdout carries exactly one structured error document with the timeout code and the same remedy, and the command exits 1.

---

### User Story 2 - An owned `next` refuses a busy decisions lock cleanly (Priority: P2)

An agent drives `spec-kitty next --owned-checkout <path>` and the lock it must take to
commit the advancement is held. `next` reports the lock-timeout refusal in its own error
contract (human and `--json`) and exits 1, so the control loop can retry instead of
crashing.

**Why this priority**: an owned `next` is the hot path of every governed mission; a
traceback there breaks an agent loop rather than informing it.

**Independent Test**: Hold the lock, drive the advancing dispatch for an owned checkout,
assert exit 1 and a JSON body carrying the timeout code and a retry instruction.

**Acceptance Scenarios**:

1. **Given** the decisions lock is held past the bounded wait, **When** an owned `next` reaches its commit step, **Then** the command reports a lock-timeout refusal with a retry instruction and exits 1, in both human and `--json` mode.

---

### User Story 3 - `agent decision repair-runtime-lock` refuses a busy lock cleanly (Priority: P2)

An operator repairs a mistakenly tracked decision runtime lock while another decision
command holds that lock. The command reports the refusal in its own JSON shape with the
lock-timeout code and exits 1, having changed nothing.

**Why this priority**: the repair verb's whole purpose is to touch that exact lock, so it is
the one command guaranteed to meet contention; it also commits, so a half-run is worse than
a refusal.

**Independent Test**: With an owned checkout in place, hold the lock, run
`agent decision repair-runtime-lock`, assert exit 1, one JSON document carrying the timeout
code, and an unchanged checkout.

**Acceptance Scenarios**:

1. **Given** the decisions lock is held past the bounded wait, **When** the operator runs `agent decision repair-runtime-lock --mission <m> --owned-checkout <path>`, **Then** the command prints one JSON document with the timeout code and the retry remedy, exits 1, and leaves the checkout unchanged.

---

### Edge Cases

- **Non-repair paths are unaffected.** `doctor decisions` without `--repair` never takes the
  lock; it stays report-only and exit 0.
- **`--dry-run`** on `repair-runtime-lock` returns before the acquire, so it never reports a
  timeout.
- **The lock is free by the time the command runs.** Nothing changes: the command behaves
  exactly as today.
- **The wait is bounded, not infinite.** The refusal appears after the existing bounded wait
  (10 s by default); the mission adds no new wait and no new lock.
- **A non-lock failure keeps its current rendering.** Only the timeout is translated; an
  in-lock failure such as a fold error or a refused commit propagates as it does today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One lock-timeout translation | As a maintainer, I want every decisions-lock acquisition in the doctor, `next` and the runtime-lock repair to go through the existing `_decisions_lock` seam so that a timeout has exactly one owner and the commands cannot drift apart. | High | Open | [build] | no — four acquisition sites exist today and each is pinned by its own row below |
| FR-002 | Doctor `--repair` refusal | As an operator, I want `doctor decisions --repair` to report a lock timeout as a structured refusal (human and `--json`) and exit 1 so that I know to retry instead of reading a traceback. | High | Open | [build] | no — paired with a control row on the same fixture: a free lock still repairs and exits 0 |
| FR-003 | Doctor coordination-only copy refusal | As an operator repairing a coordination-only ledger, I want the additive copy to refuse the same way so that a busy ledger never half-copies. | Medium | Open | [build] | no — the copy site is a separate acquisition from FR-002 |
| FR-004 | Owned `next` refusal | As an agent driving `next`, I want its commit step to report a lock timeout in `next`'s own error contract and exit 1 so that my control loop can retry. | High | Open | [build] | no — paired with a control row on the same fixture: a free lock still commits and exits 0 |
| FR-005 | Runtime-lock repair refusal | As an operator, I want `agent decision repair-runtime-lock` to report a lock timeout with the `DECISION_LOCK_TIMEOUT` code, exit 1, and leave the checkout untouched so that a retry is safe. | High | Open | [build] | no — paired with a control row on the same fixture: a free lock still repairs |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded refusal latency | Every refusal appears within the existing bounded wait plus 2 s of test overhead; no path waits past it or hangs. | Reliability | High | Open |
| NFR-002 | No partial writes on refusal | In all three commands, a timeout leaves every artifact the command would have written byte-identical to its pre-run state (asserted per site). | Data integrity | High | Open |
| NFR-003 | Machine-matchable code | All three commands emit the single stable code `DECISION_LOCK_TIMEOUT`; no new error code is introduced. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the one seam | The translation is `decisions/service.py::_decisions_lock`; no command adds a local `try/except LockAcquireTimeout` copy. | Technical | High | Open |
| C-002 | Keep each command's error contract | The doctor emits its C2 envelope, `next` its `error_code`/`next_step` payload, and `repair-runtime-lock` its `{status, code, message}` payload; no command's error shape changes for other failures (ADR `2026-10-27-2`). | Technical | High | Open |
| C-003 | Scope stays on the lock surface | `doctor decisions` finding semantics (#6764) and every non-timeout behaviour are out of scope. | Technical | High | Open |

### Key Entities *(include if this mission involves data)*

- **Decisions lock**: the sidecar `decisions/index.json.lock` guarding the decision index read-modify-write; held by the service write path, the doctor, owned `next` and the runtime-lock repair.
- **Lock-timeout refusal**: the structured error a caller receives when the bounded acquire fails — code `DECISION_LOCK_TIMEOUT`, the lock path, the wait, "nothing was written", and a retry instruction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the four acquisition sites has a test that fails on the pre-fix tree with an escaping `LockAcquireTimeout` and passes on the fix with a structured refusal. — [build] · no-op passable: no
- **SC-002**: All three commands exit 1 with `DECISION_LOCK_TIMEOUT` present in their emitted document when the lock is held, in every output mode the command supports. — [build] · no-op passable: no
- **SC-003**: Zero tracebacks reach the caller in those cases, and every artifact the command would have written is unchanged after the refusal — for the doctor and the runtime-lock repair, the whole asserted tree; for owned `next`, whose advancement is already durable, no decision is printed and the ordered commit did not happen. — [build] · no-op passable: no
