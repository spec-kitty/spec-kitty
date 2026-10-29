# Mission Specification: Decision log integrity

**Mission Branch**: `issue-4848-decision-open-lock`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Remediation mission M4. Issues #4848 (open half) and #6412 (reader half, reopen rule only).

## Intent Summary (confirmed)

Someone who opens a Decision Moment (the `agent decision` CLI, a planning interview, or an
orchestrator retry) gets exactly one opening record per decision in the Mission's event log.
That holds for a double submit and for concurrent retries after an interrupted open. Event logs
that already hold two identical opening records for one decision become readable again, without
rewriting the log. The deferred → resolved reopen rule comes from the shared events package
instead of a local copy.

Operator rulings (recorded 2026-10-27):

1. Existing duplicated logs are healed by reader tolerance, not by a `doctor --repair` rewrite.
2. The #6412 reader half is limited to the reopen rule. Folding through the events package's
   ledger reducer needs full event envelopes, which belong to the envelope half
   (spec-kitty-events #92, #6194) and are out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent identical opens record one opening (Priority: P1)

An operator (or an agent retrying for them) submits the same `decision open` twice at once, for
example a double submit or an impatient retry. Today both calls can record an opening, and the
decision can no longer be read by `doctor decisions`.

**Why this priority**: The duplicate cannot be repaired by any command and keeps `doctor` red.

**Independent Test**: Pause the first open while it records its opening, start an identical
second open, release; the log holds exactly one opening for the decision and the second call
reports an idempotent open.

**Acceptance Scenarios**:

1. **Given** a first open that has saved its index entry and is recording its opening, **When**
   an identical open starts, **Then** the second open waits until the first finishes and returns
   the same decision id as idempotent, and the log holds one opening.
2. **Given** an identical open run twice one after the other, **When** both finish, **Then** the
   log holds one opening (control: unchanged behaviour).

### User Story 2 - Concurrent retries after an interrupted open record one opening (Priority: P1)

An open was interrupted after its index entry was saved but before its opening was recorded.
Two retries then run at once. Each retry checks whether the opening is missing and records it.

**Why this priority**: Same unrepairable outcome as story 1, reached through the documented
recovery path ("rerun the same logical open").

**Independent Test**: Interrupt an open, pause the first retry while it records the missing
opening, start a second retry, release; the log holds exactly one opening.

**Acceptance Scenarios**:

1. **Given** an interrupted open and a first retry recording the missing opening, **When** a
   second retry starts, **Then** it waits, finds the opening present and records nothing.
2. **Given** an interrupted open and one retry, **When** a second retry follows serially,
   **Then** the log holds one opening (control: unchanged behaviour).

### User Story 3 - Already-duplicated logs read again (Priority: P2)

A Mission whose log already holds two opening records for one decision, written by the race
above before this fix, is reported as "could not fold" on every `doctor decisions` run.

**Why this priority**: Existing ledgers in the field stay red until someone edits the log.

**Independent Test**: Seed a log with two openings for one decision whose content is the same
apart from their recording time; `doctor decisions` reports no unfoldable decision and
`--repair` rebuilds that decision's index entry from the earliest opening.

**Acceptance Scenarios**:

1. **Given** two openings with the same content apart from recording time, **When** the
   decision is folded, **Then** the result equals the fold of the earliest opening alone.
2. **Given** two openings whose content differs in any other field, **When** the decision is
   folded, **Then** the fold still refuses, as today.

### User Story 4 - The reopen rule has one owner (Priority: P3)

The rule that a deferred decision may later be resolved is defined in the shared events
package. The CLI keeps its own copy.

**Independent Test**: Defer then resolve a decision; the write path accepts it and the fold
returns the resolved state, with the rule read from the package.

**Acceptance Scenarios**:

1. **Given** an open decision, **When** it is deferred and then resolved, **Then** the resolve is
   accepted and the folded state is resolved (unchanged behaviour).
2. **Given** a resolved decision, **When** a defer or cancel is requested, **Then** it is refused
   as a terminal conflict (unchanged behaviour).

### Edge Cases

- A waiting second open waits for the decisions lock without a time bound (amended, NFR-002); a resolve, defer or cancel whose bounded wait times out reports `LOCK_TIMEOUT` and writes nothing.
- A resolve, defer or cancel of a decision whose open was interrupted records the missing opening first (pre-PR squad fold S3).
- An interrupted open whose opening actor was not persisted still refuses repair, as today.
- An unreadable event log on the retry path still fails closed, as today.
- Two openings for one decision where one carries different question text or options: refused.
- Three or more identical openings for one decision: folded from the earliest.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fresh open records its opening under the decisions lock | As an operator, I want a fresh open to record its opening while it still holds the decisions lock, so that an identical concurrent open waits and returns idempotently without recording a second opening. | High | Open | [build] | no — the paused-interleaving test is red on the base (two openings) and the serial control stays at one |
| FR-002 | Retry repair checks and records under the decisions lock | As an operator, I want the retry of an interrupted open to check for and record the missing opening while holding the decisions lock, so that two concurrent retries record exactly one opening. | High | Open | [build] | no — the paused-retry test is red on the base (two openings) and the serial retry control stays at one |
| FR-003 | Fold tolerates identical duplicate openings | As an operator with an already-duplicated log, I want the fold to accept several openings for one decision whose content matches apart from recording time, folding the earliest, so that `doctor decisions` reports clean and `--repair` rebuilds the entry without rewriting the log. | High | Open | [build] | no — paired with the differing-content case on the same fixture, which must still refuse |
| FR-004 | Reopen rule comes from the events package | As a maintainer, I want the deferred → resolved reopen rule read from the shared events package and the local table removed, so that the rule has one owner. | Medium | Open | [build] | no — the defer-then-resolve and resolved-then-defer cases must keep their current verdicts, and the local table must be absent |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic, bounded interleaving tests | Each new interleaving test decides its interleaving by pausing a real write (no timing luck), joins every worker within 60 s, and is red on the base commit and green after the fix. | Reliability | High | Open |
| NFR-002 | No added hold beyond one append | The decisions lock is held across at most one opening append per call. Amended 2026-10-27 (operator ruling on squad finding S1): an open waits on the decisions lock without a time bound, as it already waits on the Mission status lock, so a concurrent open of another decision waits and succeeds; resolve, defer and cancel keep the bounded wait and report a timeout as `LOCK_TIMEOUT`, writing nothing. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Lock order and writers unchanged | Lock order stays decisions lock first, then the Mission status lock. No new event-log writer, no log rewrite, and the ledgers of the event-log and status-events writes gates stay unchanged. | Technical | High | Open |
| C-002 | Envelope half out of scope | Full event envelopes and folding through the events package's ledger reducer stay with spec-kitty-events #92 and #6194; changes stay reader-side or lock-scope-only so they survive the move to the canonical writer (ADR 2026-10-22-1). | Technical | High | Open |
| C-003 | Doctor behaviour otherwise unchanged | `doctor decisions` and `--repair` keep their current behaviour for every log that is not an identical-duplicate-opening case. | Technical | Medium | Open |

### Key Entities

- **Decision Moment**: one question raised during planning, identified by its decision id.
- **Opening record**: the event in the Mission's event log that says a decision was opened.
- **Decisions index**: the per-Mission list of decisions, rebuilt from the log by `--repair`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under every tested interleaving of two identical opens, and of two retries after an interrupted open, the log holds exactly 1 opening record per decision — [build] · no-op passable: no
- **SC-002**: A log already holding identical duplicate openings is reported with 0 unfoldable decisions — [build] · no-op passable: no
- **SC-003**: A log whose duplicate openings differ in content is still reported as unfoldable (1 of 1) — [ratchet] · no-op passable: yes — paired with SC-002 on the same fixture
- **SC-004**: The CLI defines 0 local copies of the reopen rule — [build] · no-op passable: no

## Assumptions

- Two openings written by the race carry the same content apart from their recording time and
  event identity, because both are built from the same saved index entry.
- The earliest opening is the canonical one; later identical openings carry no extra meaning.
