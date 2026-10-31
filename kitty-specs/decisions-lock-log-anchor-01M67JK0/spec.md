# Mission Specification: Decisions lock is keyed on the event log, not the ledger directory

**Mission Branch**: `issue-6765-decisions-lock-log-anchor`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6765 — "Decisions lock is per ledger directory, not per event log: opens from two checkouts with the same explicit decision_id are not serialized".

## Context

PR #6762 (#4848) made `open_decision` hold a decisions lock across the dedup lookup
and the `DecisionPointOpened` append, so one checkout writes exactly one opening per
decision. That lock is `_decisions_lock_path(ledger_dir)` →
`kitty-specs/<mission>/decisions/index.json.lock`, i.e. it is keyed on the **ledger
directory** of the checkout that happens to be running.

The row it protects does not live in the ledger directory. It is appended to the
Mission's **event log** (`status.events.jsonl`), whose write location is resolved
separately (`_write_events_path` → `placement_seam(...).write_dir(STATUS_STATE)`).
On a coordination topology the log is the shared coordination leg; the ledger is the
PRIMARY leg. Whenever those two anchors diverge across checkouts — the shape issue
#6765 names, and the shape the #6196 write-service handover will make common — two
opens of the same explicit `decision_id` take two different locks, so neither waits
for the other, and both can append an opening for one decision. The log then folds
into a decision with two conflicting openings and the fold refuses it.

The lock must be keyed on the anchor that is actually shared by every writer of the
row: the event log the opening goes to. That is exactly what
`kernel.event_log_append` already does for its own appends (digest of the resolved
anchor, lock file under `<git-common-dir>/spec-kitty-locks/`, which every worktree of
a repository shares).

Scope boundary (operator brief for this batch): the sibling PR #6841 reshapes the
decisions lock-**timeout** refusal. This mission changes lock **keying** only. It adds
no new refusal code, no new timeout, and no new error envelope: both locks are taken
through the existing `_decisions_lock` helper, so whatever #6841 decides about a
timed-out decisions lock applies to both uniformly. The `decisions/index.json.lock`
sidecar and the ignore/repair machinery built on it (#5925, #6628,
`repair-runtime-lock`, the coherence screen) stay exactly as they are; this mission
does not retire them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two checkouts opening one decision are serialized (Priority: P1)

An orchestrator runs `decision open` with the same explicit `decision_id` from two
checkouts of one repository (the repository root checkout and an
`--owned-checkout`, or two owned checkouts) whose openings land in the same
`status.events.jsonl`. Today both enter the open critical section at once and both
append an opening. After this mission the second waits for the first: the opening
critical section of one checkout never overlaps the other's.

**Why this priority**: it is the defect. Everything else is supporting detail.

**Independent Test**: drive `open_decision` concurrently from two repo roots that
resolve to one shared event log and different ledger directories, with the two calls'
critical sections instrumented; assert the sections do not overlap. Pre-fix they
overlap and the test fails.

**Acceptance Scenarios**:

1. **Given** two checkouts whose decision writes resolve to one shared
   `status.events.jsonl` but to different `decisions/` ledger directories, **When**
   both open a decision at the same time, **Then** their open critical sections are
   serialized (no overlap), and the log carries exactly one opening row per attempt.
2. **Given** the same two checkouts, **When** the second open runs after the first has
   released, **Then** it still completes and appends normally — serialization must not
   turn the second writer into a refusal or a no-op.

---

### User Story 2 - Writers of *different* logs are not serialized against each other (Priority: P2)

Two checkouts that genuinely write different event logs (for example two independent
owned single-branch checkouts, each with its own log) must keep making progress
independently: the fix keys the lock on the log, so distinct logs must yield distinct
locks and no added blocking.

**Why this priority**: the cheap wrong fix is a single global lock. It would pass
User Story 1 by over-serializing every decision write in the repository.

**Independent Test**: compute the anchor lock path for two distinct event-log paths
and assert the paths differ; assert no lock file is created for a log nobody writes.

**Acceptance Scenarios**:

1. **Given** two distinct event-log paths, **When** the anchor lock path is computed
   for each, **Then** the two lock paths differ.
2. **Given** a decision write, **When** it takes its locks, **Then** the anchor lock
   file lives outside the working tree (under the git common dir), so it never appears
   in `git status` and needs no ignore rule.

---

### User Story 3 - The existing ledger-dir lock contract is unchanged (Priority: P3)

The `decisions/index.json.lock` sidecar keeps guarding what it guards today: the
reconciler (`doctor --repair`), the runtime-lock repair command and `next`'s owned
commit guard all take it, and a forward write must still exclude a concurrent repair
in the same ledger directory.

**Why this priority**: a change to lock keying must not silently drop an existing
mutual-exclusion guarantee (#4848, #5925, #6628).

**Independent Test**: the existing suites that pin the sidecar location, the ignore
provisioning and the doctor/repair serialization stay green unchanged.

**Acceptance Scenarios**:

1. **Given** a forward write, **When** it holds its locks, **Then** it holds the
   ledger-dir sidecar lock as well as the log anchor lock.
2. **Given** the reconciler or the repair command, **When** it takes the ledger-dir
   lock, **Then** it still excludes an in-flight forward write in that ledger dir.

---

### Edge Cases

- **Non-git checkout**: `kernel.event_log_append.event_log_lock_path` falls back to a
  sibling `<log>.event-log.lock` when the anchor is not in a git repository. A decision
  write in a non-git tree must keep working (the sibling file is outside version
  control there by definition).
- **Git not invocable**: `event_log_lock_path` raises
  `EventLogLockUnavailableError` rather than locking somewhere no other writer locks.
  It must propagate as-is (an `OSError` subclass) — never be swallowed into a silent
  unlocked write.
- **Lock order**: the anchor lock is taken before the ledger-dir sidecar, and both
  before the Mission status lock the event append takes. A single global order is what
  keeps the pair deadlock-free; no path may take the sidecar first and the anchor
  after.
- **`dry_run`**: a dry run resolves no lock at all (it writes nothing), exactly as
  today.
- **An owned checkout**: its event log and its ledger dir both resolve inside the owned
  checkout, so its anchor lock is its own — no cross-checkout blocking is introduced
  where no log is shared.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Anchor lock derived from the event log | As an operator running two checkouts, I want the decision write lock keyed on the event log the row is written to so that two writers of one log can never interleave. | High | Open | [build] | no — the anchor path did not exist before this mission |
| FR-002 | Forward writes hold anchor then sidecar | As a maintainer, I want `open_decision` and the terminal verbs to hold the log anchor lock and then the existing ledger-dir sidecar lock so that cross-checkout serialization and in-ledger repair exclusion both hold. | High | Open | [build] | no — a no-op still holds only the sidecar |
| FR-003 | Distinct logs, distinct locks | As an operator with two independent owned checkouts, I want their decision writes not to block each other, so that keying on the log does not become a global lock. | Medium | Open | [ratchet] | no — paired with the shared-log case on the same fixture |
| FR-004 | Sidecar contract unchanged | As a maintainer, I want the reconciler, the repair command and `next`'s owned commit guard to keep taking `decisions/index.json.lock` unchanged so that #4848/#5925/#6628 guarantees survive this change. | Medium | Open | [ratchet] | yes — pinned by the pre-existing suites for those surfaces |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Open wait stays unbounded | The anchor lock ahead of the ledger-dir lock must not introduce a bounded wait on the open path: a queued open waits without a time bound, as `_OPEN_LOCK_WAIT_S = None` already does for the sidecar. A concurrent open of a *different* decision must not fail with a timeout. | Reliability | High | Open |
| NFR-002 | One added lock acquisition per write | A decision write takes exactly one extra lock acquisition (the anchor) and no extra filesystem scan, git worktree creation, or subprocess beyond the git-common-dir probe the lock path already performs; no measurable change to single-checkout open latency beyond one `flock`. | Performance | Medium | Open |
| NFR-003 | No new refusal surface | The change adds no new error type, code or envelope: both locks are acquired through the existing `_decisions_lock` helper, so a timed-out decisions lock keeps its current single refusal shape (owned by #6841). | Usability | High | Open |
| NFR-004 | No lock file in the working tree | The anchor lock file must live outside every checkout's working tree (under the git common dir), verified by a test asserting `git status --porcelain` stays clean after a decision write. | Security | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Keying only, not timeout reporting | Do not change decisions lock-timeout reporting, retryability or the orchestrator-api refusal envelope; PR #6841 owns that surface. Any overlap is a conflict to avoid, not a merge to make. | Technical | High | Open |
| C-002 | The sidecar stays | Do not retire `decisions/index.json.lock`, its `.gitignore` provisioning, `repair-runtime-lock`, or the coherence screen for it. Removing that machinery is a separate change with user-facing surface. | Technical | High | Open |
| C-003 | Reuse the kernel lock contract | Use `kernel.event_log_append.event_log_lock_path` (the ONE existing anchor→lock-path contract) rather than deriving a second digest/lock-placement scheme in `specify_cli`. | Technical | High | Open |
| C-004 | Single global lock order | Anchor lock → ledger-dir sidecar → Mission status lock, with no path inverting it. | Technical | High | Open |

### Key Entities

- **Log anchor**: the resolved `status.events.jsonl` path a decision row is appended to
  (`_write_events_path`). Its identity — not the ledger directory's — is what every
  writer of that row shares.
- **Anchor lock**: `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock`, keyed on
  the resolved, normalised anchor path (owned by `kernel.event_log_append`).
- **Ledger-dir sidecar lock**: `kitty-specs/<mission>/decisions/index.json.lock`
  (unchanged; guards the index RMW against the reconciler and the repair command).
- **Decision index**: `kitty-specs/<mission>/decisions/index.json`, the per-checkout
  dedup source consulted inside the critical section.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A two-checkout concurrent open with one explicit `decision_id` enters its critical section serially: zero observed overlap across 20 repeated runs, versus observed overlap on the pre-fix code. — [build] · no-op passable: no
- **SC-002**: Two distinct event-log anchors produce two distinct lock paths, and the shared-anchor case produces one — asserted in a single parametrized test. — [ratchet] · no-op passable: no
- **SC-003**: `git status --porcelain` is empty after a decision open, so the new lock leaves no working-tree residue. — [ratchet] · no-op passable: yes
- **SC-004**: The pre-existing decision suites (`tests/specify_cli/decisions/`, `tests/integration/test_owned_decision_runtime_lock.py`, `tests/decisions/test_decisions_reconciler.py`, `tests/specify_cli/orchestrator_api/test_decision_verbs.py`) pass unchanged. — [ratchet] · no-op passable: yes

## Out of Scope

- Decisions lock-timeout refusal/retryability (PR #6841).
- Retiring the ledger-dir sidecar lock and its ignore/repair machinery (deferred; record
  as follow-up work for the #6196 write-service handover).
- Making `open` idempotent on `decision_id` across checkouts by folding the shared log
  (the issue's second option — that belongs to the decisions handover).
