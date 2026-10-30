# Implementation Plan: Lock the migration ledger append; record the structural reselection

**Branch**: `issue-6613-ledger-lock-and-runs-first-record` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/ledger-lock-and-runs-first-record-01M66YMC/spec.md`

## Summary

Two independent edits with one shared subject — the migration ledger's honesty about itself.

1. **Code**: `MigrationLedger.append` / `append_many` keep their full-file atomic rewrite but run it
   inside the canonical `kernel.locks.machine_file_lock` primitive, taken on a dedicated
   `<ledger>.lock` sidecar. Bounded wait, typed failure, nothing appended on give-up.
2. **Doctrine/docs**: ADR `2026-10-17-1` gains an amendment recording the `runs_first`
   `structural_detect` reselection that `base.py` performs, and the developer reference's
   state-ledger rule (`docs/development/reference/events-in-core.md`) records both the append lock
   and the reselection.

**Deferred, not dropped silently**: the issue's second half also asks for the *gap table* to stop
saying "No lock" (row G-15 and the migration-ledger writer row in
`docs/architecture/event-ledger-writers-and-readers.md`). That page is **frozen** by
`tests/architectural/test_events_import_frozen.py` (ADR `2026-10-29-1` D-9, blob
`c2943d49…`); editing it fails an always-on gate, and re-pinning `_FROZEN_OBJECTS` is an
operator-approved change this mission does not make (the #6611 precedent). G-15's closure
wording is authored in the Mission record and cited in the PR's `## Deferred`.

Both are pinned red-first: a lost-update repro that fails against today's unlocked append, and a doc
guard that fails against today's ADR and gap table.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; `from __future__ import annotations` in use)
**Primary Dependencies**: stdlib only for the fix; `kernel.locks` (`machine_file_lock`,
`LockAcquireTimeout`) and `specify_cli.core.atomic.atomic_write` already imported by the module
**Storage**: JSONL files under `.kittify/` (tracked + per-clone partitions); lock is a sidecar file
**Testing**: pytest; package-scoped runs (`tests/upgrade/`, `tests/docs/`, `tests/architectural/`)
**Target Platform**: CLI, POSIX + Windows (the lock primitive is OS-file-lock based)
**Project Type**: single Python package (`src/specify_cli`, `src/kernel`, `src/runtime`)
**Performance Goals**: the lock adds one open/lock/truncate/unlock of a small sidecar per append;
no measurable change to an upgrade run
**Constraints**: no new kernel lock-path helper (C-001, #6727 owns it); no `base.py` import
(C-002); no record-format change (C-003); no selection behaviour change (C-004)
**Scale/Scope**: 1 module changed (~25 lines), 1 ADR amended, 1 architecture page corrected,
2 new test modules

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The lock implementation stays in `kernel.locks`; the ledger only *uses* it. No second lock mechanism, no copied digest/common-dir rule (C-001). |
| ATDD-first / red-first | Both deliverables get a failing-first test through the production entry point (`MigrationLedger.append`, the ADR page itself) before the fix. |
| Locality of change (DIRECTIVE_024) | Edits land in `upgrade/ledger.py`, the ADR, the one architecture page and two test modules. No refactor of `base.py`, `registry.py` or `runner.py`. |
| Canonical sources (DIRECTIVE_044) | The ADR amendment is an amendment to the existing ADR, not a new competing document; the gap table is the canonical gap record. |
| Terminology canon | "ledger" here is the migration *state* ledger; the amendment says so explicitly. "Mission" throughout; no `feature` aliases introduced. |
| No full heavy suites | Test surface is `tests/upgrade/`, `tests/docs/`, `tests/architectural/` only. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/ledger-lock-and-runs-first-record-01M66YMC/
├── plan.md              # This file
├── research.md          # Phase 0 output (survey of the lock helper landscape)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/kernel/locks.py                       # consumed, NOT modified: machine_file_lock + LockAcquireTimeout
src/specify_cli/upgrade/ledger.py         # the seam: lock around append / append_many
src/specify_cli/core/atomic.py            # consumed unchanged: atomic_write
tests/upgrade/test_ledger_append_lock.py  # new: red-first lost-update + bounded-wait + give-up
tests/docs/test_migration_ledger_adr_records_reselection.py  # new: doc guard
docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md       # amended
docs/development/reference/events-in-core.md                 # state-ledger rule: lock + reselection
docs/changelog/CHANGELOG.md                                  # [Unreleased] entry
docs/architecture/event-ledger-writers-and-readers.md        # FROZEN: not edited (see Deferred)
```

**Structure Decision**: single package; the change is a seam edit in one existing module plus
doctrine, so no new module is introduced in `src/`.

## Implementation Concern Map

### IC-01 — The locked ledger seam

- **Purpose**: Make the ledger's read-modify-write exclusive so a concurrent run cannot lose a
  record, using the canonical primitive and nothing new.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003,
  NFR-004, C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/upgrade/ledger.py` (`MigrationLedger.append`,
  `append_many`, a new private `_append_lines` seam plus `ledger_lock_path` /
  `MigrationLedgerLockTimeoutError`); `tests/upgrade/test_ledger_append_lock.py`
- **Sequencing/depends-on**: none
- **Risks**:
  - The lock must not be taken on the payload path (primitive truncates what it locks).
  - `reentrant=True` is required so a future nested append cannot self-deadlock; the primitive's
    thread-local holdings already give the right per-thread semantics.
  - The sidecar must not land in a git-ignored-or-not question: it sits beside the ledger in
    `.kittify/`, which is either tracked (tracked ledger) or already ignored (`.kittify/migrations/`).
    Add the tracked sidecar to gitignore status only if the tracked ledger's directory would
    otherwise record the lock file — checked in WP01 as an explicit assertion.

### IC-02 — Recording the reselection and documenting the lock

- **Purpose**: Close gap G-15 factually in the editable doctrine: an ADR amendment for the
  `runs_first` structural reselection, plus the developer reference's state-ledger rule carrying
  both facts (lock and reselection).
- **Relevant requirements**: FR-005, FR-006, FR-007, C-004, C-005
- **Affected surfaces**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` (new amendment
  section, appended after the last amendment), `docs/development/reference/events-in-core.md`
  (state-ledger rule bullets), `tests/docs/test_migration_ledger_adr_records_reselection.py`
- **Sequencing/depends-on**: after IC-01 for the lock wording (the rule must name the lock IC-01
  built); the ADR amendment itself is independent.
- **Risks**:
  - The amendment must be *factual*: it records what `reselect_when_recorded` does, including that
    `detect()` remains the idempotency guard and that at most one migration may set `runs_first`.
    It must not read as an operator decision to keep or remove the behaviour (C-004).
  - `docs/architecture/event-ledger-writers-and-readers.md` is frozen (see Summary): the gap-table
    half of the issue is deferred with the pin named, never silently edited.

## Complexity Tracking

No charter violations. The only "new surface" is a `ledger_lock_path` helper inside
`specify_cli.upgrade.ledger`, which derives a sidecar from a path the module already owns — it adds
no lock-path *rule* and does not duplicate `#6727`'s anchored-lock-path helper.
