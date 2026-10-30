# Work Packages: Lock the migration ledger append; record the structural reselection

**Inputs**: Design documents from `/kitty-specs/ledger-lock-and-runs-first-record-01M66YMC/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required. Both work packages are red-first: the failing test exists before the change and
is run against the pre-fix tree to prove it fails.

**Organization**: Two work packages — the code seam (WP01) and the doctrine/docs record (WP02).
WP02's lock wording depends on WP01 having built the lock, so WP02 follows WP01.

**Prompt Files**: `tasks/WP01-*.md`, `tasks/WP02-*.md`.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/`

---

## Work Package WP01: The locked ledger append (Priority: P0)

**Goal**: `MigrationLedger.append` and `append_many` hold a dedicated per-partition lock across
their read-modify-write, so two processes on one checkout cannot lose a record, and a contended
lock fails loudly after a bounded wait instead of silently dropping the record.
**Independent Test**: A lost-update repro drives two appends to one ledger through the public
`MigrationLedger` API with the read step slowed so both read the pre-append file; both records must
be on disk. Also: an external holder of the lock makes a second append wait, and a never-released
holder produces the typed timeout error with nothing written.
**Prompt**: `/tasks/WP01-locked-ledger-append.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-002, C-003, SC-001, SC-002

### Included Subtasks

T001 Write the red-first lock tests in `tests/upgrade/test_ledger_append_lock.py` (lost update, wait-for-holder, bounded give-up, sidecar path, re-entrancy, no-git, absent directory) and confirm they fail on the pre-fix code
T002 Add the `MigrationLedgerLockTimeoutError`, `LEDGER_LOCK_TIMEOUT_S` and `ledger_lock_path` seam to `src/specify_cli/upgrade/ledger.py`
T003 Route `append` and `append_many` through one private `_append_lines` that takes `kernel.locks.machine_file_lock` on the sidecar, keeping `atomic_write` as the write
T004 Update the module docstring's "single-writer, `kernel.locks` deliberately not built" paragraph to describe the lock that now exists
T005 Run the package-scoped gates: `tests/upgrade/`, `tests/specify_cli/upgrade/`, ruff, mypy on the changed module

### Implementation Notes

- The lock is `machine_file_lock(ledger_lock_path(path), blocking=True, timeout_s=30.0, reentrant=True)`; do **not** invent a digest/common-dir path rule (C-001) and do **not** touch `kernel/` (#6727 owns that consolidation).
- The lock path is `<partition file name>.lock` beside the partition — never the partition file itself (the primitive writes its own record into the file it locks and truncates on release).
- `append_many` locks each partition for its own rewrite; it must not hold one partition's lock while writing the other.
- On `LockAcquireTimeout`, raise the typed error naming the lock path and stating that nothing was appended.
- No record-format change (C-003): the JSONL bytes an append produces must be identical to today's.
- `ledger.py` must not import `upgrade.migrations.base` (C-002).

### Parallel Opportunities

- T001 must precede T002–T004 (red-first). T004 is independent of T002/T003 once T001 is written.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Over-serialization: a per-file sidecar keeps unrelated ledgers independent; assert two different ledger paths get two different lock paths.
- Test flakiness: the lost-update repro must not depend on wall-clock luck — slow the *read* with a patch and start both threads from one barrier event, so the pre-fix failure is deterministic.

---

## Work Package WP02: Record the reselection, document the lock (Priority: P0)

**Goal**: ADR `2026-10-17-1` states the `runs_first` / `structural_detect` reselection the code
performs, the developer reference's state-ledger rule names the append lock and the reselection,
and a doc guard keeps both true. User-facing changelog entry added.
**Independent Test**: The doc guard fails against `main` (no amendment, no lock sentence) and
passes after the edits; the ADR still carries valid MADR frontmatter and the docs freshness gate
reports `errors=0`.
**Prompt**: `/tasks/WP02-record-reselection-and-document-lock.md`
**Requirement Refs**: FR-005, FR-006, FR-007, C-004, C-005, SC-003, SC-004

### Included Subtasks

T006 Write the red-first doc guard in `tests/docs/test_migration_ledger_adr_records_reselection.py` (ADR names `structural_detect`/`reselect_when_recorded` and the recorded-but-structurally-present case; the developer reference names the append lock) and confirm it fails
T007 Append an amendment to `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` recording the reselection factually (no behaviour change)
T008 Add the state-ledger rule to `docs/development/reference/events-in-core.md` naming the lock and the reselection
T009 Add the `[Unreleased]` changelog entry to `docs/changelog/CHANGELOG.md`
T010 Run the docs freshness / ADR inventory / architectural gates and `tests/architectural/test_events_import_frozen.py`

### Implementation Notes

- The amendment is **factual**: record what `reselect_when_recorded` does, that `detect()` stays the idempotency guard, that at most one registered migration may set `runs_first`, and that removing the behaviour is an open operator decision. Do not phrase it as a decision this mission took (C-004).
- Do **not** edit `docs/architecture/event-ledger-writers-and-readers.md`: it is frozen by `tests/architectural/test_events_import_frozen.py` (ADR 2026-10-29-1 D-9). G-15's closure wording lives in the mission record and the PR's `## Deferred`.
- Changelog: `[Unreleased]`, bold impact-first lead with `(#6613)`, before/after, under 1,200 characters.

### Parallel Opportunities

- T007 and T008 are independent files; T009 depends on the final shape of both.

### Dependencies

- Depends on WP01 (the lock sentence must describe the lock WP01 built).

### Risks & Mitigations

- Docs freshness drift: adding an amendment can stale the ADR inventory; run `freshen_adr_inventory` + `docs_index --write` and commit the regenerated artifacts.
- Terminology: "ledger" here is the migration state ledger; the amendment says so to keep it apart from the event ledger.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none worth it at this size; WP01's T004 and WP02's T001 can overlap.
- **MVP Scope**: WP01 alone closes the correctness defect; WP02 closes the documentation gap. Both are in scope.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| NFR-004 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| C-004 | WP02 |
| C-005 | WP02 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP02 |
| SC-004 | WP02 |
| SC-005 | WP01, WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first lock tests | WP01 | P0 | No |
| T002 | Lock seam + typed error | WP01 | P0 | No |
| T003 | Locked append / append_many | WP01 | P0 | No |
| T004 | Module docstring truth | WP01 | P1 | Yes |
| T005 | Package gates | WP01 | P0 | No |
| T006 | Red-first doc guard | WP02 | P0 | Yes |
| T007 | ADR amendment | WP02 | P0 | Yes |
| T008 | Developer reference rule | WP02 | P0 | Yes |
| T009 | Changelog entry | WP02 | P1 | No |
| T010 | Docs gates | WP02 | P0 | No |
