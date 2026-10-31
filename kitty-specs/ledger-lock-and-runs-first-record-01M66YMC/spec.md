# Mission Specification: Lock the migration ledger append; record the structural reselection

**Mission Branch**: `issue-6613-ledger-lock-and-runs-first-record`
**Created**: 2026-10-30
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6613 — "Migration ledger: lock the read-modify-write append, and
record the runs_first structural resel…". Guidance from the operator brief: reuse the repository's
existing anchor-keyed lock helper rather than inventing one; a sibling mission (#6727) is
consolidating lock-path helpers in kernel, so do not duplicate that work.

## Context

Gap **G-15** in `docs/architecture/event-ledger-writers-and-readers.md` records two ways the
explicit migration ledger (ADR `2026-10-17-1`) diverges from the code that implements it:

1. `MigrationLedger.append` / `append_many` (`src/specify_cli/upgrade/ledger.py`) perform a
   read-modify-write — read every line, append, write a temp file, `os.replace` — and take **no
   lock**. The capture time table for this row reads "No lock". Two `spec-kitty upgrade` (or
   `spec-kitty migrate`) processes on one checkout can each read the same line set, and the second
   replace silently drops the first process's record.
2. `BaseMigration.reselect_when_recorded` (`src/specify_cli/upgrade/migrations/base.py`) still
   re-selects a `runs_first` migration whose `structural_detect` reports the old state present,
   while the ADR says only that selection "collapses to 'is this id in the applicable ledger'".
   `structural_detect` appears nowhere in the ADR or its amendments.

Term note: "ledger" in this mission always means the **migration ledger**, a *state* ledger
(`.kittify/migration-ledger.jsonl` plus `.kittify/migrations/clone-local.jsonl`), never the
event ledger and never the charter activation ledger. "Lock" never means the git VCS lock.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A concurrent second run cannot drop the first run's record (Priority: P1)

An operator (or a CI job and a human) has two `spec-kitty upgrade` invocations racing on one
checkout. Each one applies a migration and appends a record. Today the second append can replace
the file with only its own line, so the first run's `success` record is lost; the migration is
then selected again on the next run and `apply()` must save the day on its own.

**Why this priority**: A lost `success` record silently re-runs an already-applied migration and
is invisible in the run output. It is the correctness defect the issue names first.

**Independent Test**: Run two appends through the public `MigrationLedger` entry point against one
ledger file, with the read step interleaved so a lost update is forced when no lock is held;
assert both records are on disk. Today this test fails (one record), because the second append
replaced the file it read before the first append landed.

**Acceptance Scenarios**:

1. **Given** two concurrent appends to the same ledger file, **When** both complete, **Then**
   both records are present and the file is a well-formed JSONL document.
2. **Given** a second process holding the ledger lock, **When** an append is attempted, **Then**
   the append waits for the holder (bounded), then writes its record on top of what the holder
   recorded — it never writes a file built from a pre-holder read.
3. **Given** a lock that cannot be acquired within the bounded wait, **When** the append gives up,
   **Then** it raises a typed error naming the lock file and appends nothing — the old ledger is
   left byte-identical (no torn or truncated file).

### User Story 2 - The ADR describes the selection rule the code actually implements (Priority: P1)

A maintainer reading ADR `2026-10-17-1` to understand "will this migration run again?" currently
gets one answer ("is this id in the applicable ledger?") and the code gives another for the
single `runs_first` migration (`structural_detect` re-selects it even when recorded).

**Why this priority**: The gap is *why G-15 is filed*; the issue's scope explicitly offers
"record the structural reselection in an ADR amendment" as the remedy, and the ADR is the
declared architecture authority a future change is judged against.

**Independent Test**: A doc guard asserts the ADR names `structural_detect` and states that a
recorded `runs_first` migration is re-selected when it fires, and that the developer reference's
migration-ledger rule states the append takes a lock. Today both assertions fail.

**Acceptance Scenarios**:

1. **Given** ADR `2026-10-17-1`, **When** read on its own, **Then** an amendment states that
   selection is ledger-diff **plus** the `runs_first` structural reselection, what revives the old
   state, and that at most one registered migration may set `runs_first`.
2. **Given** the amendment, **When** I look for the recorded rule, **Then** it names
   `structural_detect`, `reselect_when_recorded` and the `detect()`-stays-as-idempotency-guard
   boundary, so a reader cannot conclude that "recorded" alone settles the migration.
3. **Given** `docs/development/reference/events-in-core.md`, **When** read after this mission,
   **Then** its state-ledger rule states that the migration ledger's append is lock-serialized
   and that a recorded `runs_first` migration is re-selected when `structural_detect` fires.

### Edge Cases

- **Clone-local partition.** `append_many` writes both partitions in one call. Each partition's
  read-modify-write must be locked; a lock held for one partition must not be held while writing
  the other (no lock ordering to get wrong, no deadlock against a writer of the other file).
- **No git repository.** The ledger is written by `spec-kitty init`-time and non-git flows too, so
  the lock must not require a git invocation or a git common dir.
- **The lock file must never be the payload.** Locking `.kittify/migration-ledger.jsonl` itself
  would truncate it on release (the primitive writes its own record into the file it locks).
- **Re-entrancy.** An append performed while the same thread already holds the ledger lock must
  not self-deadlock.
- **Ledger directory absent.** `.kittify/migrations/` may not exist on first append; the lock
  acquire creates its own parent directory and must not turn a successful append into an error.
- **A recorded `runs_first` migration whose `structural_detect` returns False** stays settled — the
  amendment must not read as "runs_first migrations always re-run".

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Locked `append` | As an operator, I want a ledger append to be exclusive so that a concurrent run cannot drop my record. | High | Open | [build] | no |
| FR-002 | Locked `append_many` | As an operator upgrading a project, I want the multi-record append to be exclusive per partition so that a crash-free concurrent run cannot drop a batch. | High | Open | [build] | no |
| FR-003 | Reuse the canonical lock primitive | As a maintainer, I want the ledger to take its lock through `kernel.locks.machine_file_lock` on a dedicated sidecar so that there is one lock implementation and the payload is never locked. | High | Open | [build] | no |
| FR-004 | Bounded wait, typed giving-up | As an operator, I want a contended ledger lock to wait a bounded time and then fail with a message that names the lock file, so that a stuck run is diagnosable instead of hanging or silently losing the record. | Medium | Open | [build] | no |
| FR-005 | ADR amendment records the reselection | As a maintainer, I want ADR `2026-10-17-1` to state the `runs_first` structural reselection so that the architecture document and the code agree. | High | Open | [build] | no |
| FR-006 | Developer reference records the two facts | As a maintainer, I want the state-ledger rule in `docs/development/reference/events-in-core.md` to name the append lock and the structural reselection, so that the live reference does not contradict the code. | Medium | Open | [build] | no |
| FR-007 | Reselection behaviour is unchanged | As a maintainer, I want the existing `runs_first` reselection behaviour pinned by a test so that recording it in the ADR cannot be mistaken for a licence to change it. | Medium | Open | [ratchet] | yes — paired with FR-005's doc guard on the same ADR, and with the existing `test_registry_runs_first.py` positive control |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Append stays a full-file atomic rewrite | The lock wraps the existing read-modify-write; the write path remains `specify_cli.core.atomic.atomic_write` (never `O_APPEND`), so a crash still leaves a valid old-or-new ledger. | Reliability | High | Open |
| NFR-002 | Bounded lock wait | The wait is bounded at 30 s by default; a test that holds the lock and releases it within that bound must observe the append complete, and a holder that never releases must produce the typed error inside 35 s. | Reliability | High | Open |
| NFR-003 | No lock under a second, unbounded writer | The ledger lock file is a dedicated `.lock` sidecar derived from the ledger path; no git subprocess is invoked to compute it (measurable: the append path invokes zero `git` processes when the ledger directory exists). | Performance | Medium | Open |
| NFR-004 | Changed-line coverage | The diff-cover gate's ≥ 90 % on changed lines is met by the new lock seam and its failure branch. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new lock-path helper | The mission must not add a kernel-level "anchored lock path" helper; #6727 owns that consolidation. Where the ledger needs a path it derives a sidecar from the ledger path it already has. | Technical | High | Open |
| C-002 | No `base.py` import | `upgrade/ledger.py` must keep its documented independence from `upgrade/migrations/base.py` (it reaches migration identity by defensive `getattr`). | Technical | High | Open |
| C-003 | No record-format change | Record keys, ordering, partition routing and `clone_local`/`superseded_by` serialization rules are unchanged; a ledger written before this mission reads back byte-identically. | Technical | High | Open |
| C-004 | No behaviour change to selection | The mission records the reselection in the ADR; it does not remove, widen or narrow it. Removing it needs an operator decision the issue leaves open. | Business | High | Open |
| C-005 | Doctrine is not edited in core | `packs/built-in` and `packs/internal` are fetched trees; no doctrine or pack file is edited by this mission. | Business | Medium | Open |

### Key Entities

- **Ledger record**: one append-only JSONL line, `{id, applied_at, result, identity, content_hash,
  cli_version}` plus the optional `clone_local` / `superseded_by` markers. Unchanged.
- **Ledger partition**: the tracked file or the clone-local file, selected by the migration's
  `clone_local_effect` routing key. Unchanged.
- **Ledger lock**: a dedicated sidecar file beside the partition file, held for exactly the
  read-modify-write of one append call. New.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two appends driven concurrently through `MigrationLedger.append` against one file both survive; the lost-update repro goes from 1 to 2 records on the write. — [build] · no-op passable: no
- **SC-002**: A red-first test that interleaves two reads of the same fixture fails on `main` and passes with the lock — proven by running the test against the pre-fix tree. — [build] · no-op passable: no
- **SC-003**: ADR `2026-10-17-1` names `structural_detect` and `reselect_when_recorded` and states the recorded-but-structurally-present case; the doc guard that asserts this is red before the amendment. — [build] · no-op passable: no
- **SC-004**: `docs/development/reference/events-in-core.md` states the append lock and the `runs_first` structural reselection; the doc guard asserting both is red before the edit. — [build] · no-op passable: no
- **SC-005**: The upgrade and migration test packages stay green, and `tests/architectural` stays green, on the PR head. — [ratchet] · no-op passable: yes — paired with the pre-fix red run of SC-002's test on the same fixture

## Issue Matrix

| Issue | Claimed | Verdict | Note |
|-------|---------|---------|------|
| #6613 | status:claimed, taken-by-human, assigned Ivan-Melck | pending | Scope: lock the append, record the reselection in the ADR and the developer reference. The gap-table row edits (G-15, the writer row on `docs/architecture/event-ledger-writers-and-readers.md`) are **deferred**: that page is frozen by `tests/architectural/test_events_import_frozen.py` (ADR 2026-10-29-1 D-9) and re-pinning needs an operator decision. |
