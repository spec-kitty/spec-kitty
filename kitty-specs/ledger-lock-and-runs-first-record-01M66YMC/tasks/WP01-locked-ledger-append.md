---
work_package_id: WP01
title: Locked ledger append
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6613-ledger-lock-and-runs-first-record
merge_target_branch: issue-6613-ledger-lock-and-runs-first-record
branch_strategy: Planning artifacts for this mission were generated on issue-6613-ledger-lock-and-runs-first-record. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6613-ledger-lock-and-runs-first-record unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ledger-lock-and-runs-first-record-01M66YMC
base_commit: 9505ad35e8c531a72a41b90360bec2834348df7d
created_at: '2026-10-30T17:49:14.571209+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - The seam
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_ledger_append_lock.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/ledger.py
- tests/upgrade/test_ledger_append_lock.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Locked ledger append

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and behave according to its
guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status`) for feedback and address every
item before marking the work done.

---

## Objectives & Success Criteria

`MigrationLedger.append` and `MigrationLedger.append_many` hold a dedicated per-partition lock across
their read-modify-write, so two processes appending to one ledger file in one checkout cannot each
build a file from the same pre-append read (the lost-update the issue names). A contended lock waits
a bounded time and then fails with a typed error that appends nothing.

Done means:

- The lost-update repro in `tests/upgrade/test_ledger_append_lock.py` fails on the pre-fix code and
  passes with the lock (SC-001, SC-002).
- A second appender blocks while an external holder holds the lock, then writes on top of what the
  holder recorded (never on top of a stale read).
- A lock that is never released produces `MigrationLedgerLockTimeoutError` inside the bound, and the
  ledger file is byte-identical afterwards.
- `tests/upgrade/` and `tests/specify_cli/upgrade/` stay green; ruff and mypy are clean on the module.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6613. ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
  §1 "Atomic write, single-writer" names `kernel.locks` as the extension point this WP builds.
- `kitty-specs/ledger-lock-and-runs-first-record-01M66YMC/spec.md` (FR-001…FR-004, NFR-001…004,
  C-001…003) and `plan.md` IC-01, plus `research.md` §2–§6 which justify the chosen helper.
- **C-001**: do not add a kernel-level anchored-lock-path helper. #6727 owns that consolidation. The
  ledger derives a sidecar from a path it already has.
- **C-002**: `upgrade/ledger.py` must not import `upgrade/migrations/base.py`.
- **C-003**: record format, key order, partition routing and `clone_local`/`superseded_by`
  serialization are unchanged.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-6613-ledger-lock-and-runs-first-record`; completed changes must merge back into `issue-6613-ledger-lock-and-runs-first-record`.
- **Planning base branch**: `issue-6613-ledger-lock-and-runs-first-record`
- **Merge target branch**: `issue-6613-ledger-lock-and-runs-first-record`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first lock tests

- **Purpose**: Pin the behaviour before it exists, and prove the repro is not vacuous.
- **Steps**: Create `tests/upgrade/test_ledger_append_lock.py`. Cover, at minimum:
  1. `test_concurrent_appends_keep_both_records` — two threads, one `MigrationLedger`, one record
     each, started from one `threading.Event`; monkeypatch `MigrationLedger._read_raw_lines` (wrapped
     around the original) to `time.sleep(0.15)` *after* reading, so on the pre-fix code both threads
     read the pre-append file and the second write drops the first record. Assert both ids are in
     `ledger.read_tracked()`.
  2. `test_append_many_keeps_both_partitions_concurrent` — same shape for `append_many` with one
     tracked and one clone-local record.
  3. `test_append_waits_for_the_ledger_lock` — hold `machine_file_lock(ledger_lock_path(tracked))` in
     the main thread, run `append` in a worker, assert it has not completed after ~0.3 s, release,
     join, assert the record landed. (Pre-fix: completes immediately → red.)
  4. `test_append_raises_typed_error_when_the_lock_never_frees` — hold the lock, monkeypatch
     `ledger.LEDGER_LOCK_TIMEOUT_S` to a small value, assert `MigrationLedgerLockTimeoutError`, and
     assert the ledger file bytes are unchanged.
  5. `test_lock_path_is_a_sidecar_beside_the_payload` — `ledger_lock_path(p) == p.with_name(p.name +
     ".lock")`, and two different partitions give two different lock paths.
  6. `test_append_outside_a_git_repository` — a `tmp_path` project with no `.git`: the append
     succeeds (the lock path needs no git).
  7. `test_nested_append_does_not_self_deadlock` — take the lock in the calling thread via
     `ledger_lock_path`, then call `append` in that same thread with a short timeout; it must not
     raise.
  8. `test_ledger_record_bytes_unchanged` — the appended JSONL line equals the pre-fix serialization
     of the same record (positive control for C-003).
- **Files**: `tests/upgrade/test_ledger_append_lock.py`
- **Parallel?**: No — T002–T004 follow it.
- **Notes**: Run the new module against the pre-fix tree (stash the source change or run before
  editing) and record the red output in the WP history. Keep every test on the production entry
  points (`MigrationLedger.append`, `append_many`), not on the private seam alone.

### Subtask T002 – Lock seam and typed error

- **Purpose**: Give the module one named lock path and one named failure.
- **Steps**: In `src/specify_cli/upgrade/ledger.py` add:
  - `_LOCK_SUFFIX = ".lock"`, `LEDGER_LOCK_TIMEOUT_S: float = 30.0`
  - `def ledger_lock_path(path: Path) -> Path` returning the sidecar (docstring: dedicated lock-only
    sidecar, never the payload — the primitive truncates the file it locks)
  - `class MigrationLedgerLockTimeoutError(RuntimeError)` documenting that nothing was appended
  - a private `_ledger_lock(path)` context manager wrapping
    `machine_file_lock(ledger_lock_path(path), blocking=True, timeout_s=LEDGER_LOCK_TIMEOUT_S,
    reentrant=True)` and translating `LockAcquireTimeout` into the typed error naming the lock file.
- **Files**: `src/specify_cli/upgrade/ledger.py`
- **Parallel?**: No.

### Subtask T003 – Locked append / append_many

- **Purpose**: Put the read-modify-write inside the lock, once.
- **Steps**: Add `def _append_lines(self, path: Path, new_lines: list[str]) -> None` that holds
  `_ledger_lock(path)` across `_read_raw_lines(path)` → extend → `atomic_write(...)`, then make
  `append` and `append_many` both delegate to it. `append_many` keeps its per-partition loop so it
  never holds one partition's lock while writing the other. `atomic_write` stays the write (NFR-001).
- **Files**: `src/specify_cli/upgrade/ledger.py`
- **Parallel?**: No.
- **Notes**: Preserve the trailing-newline framing exactly (`"\n".join(lines) + "\n"`).

### Subtask T004 – Module docstring truth

- **Purpose**: The module docstring currently says the subsystem is single-writer and that
  `kernel.locks` is "deliberately not built here". That stops being true.
- **Steps**: Rewrite that paragraph to describe the sidecar lock, the bounded wait and why the lock
  is per-file (a checkout's copy of a partition is the thing that can lose a record).
- **Files**: `src/specify_cli/upgrade/ledger.py`
- **Parallel?**: Yes — independent of T002/T003's code once T001 exists.

### Subtask T005 – Package-scoped gates

- **Purpose**: Prove the change is green where it can break.
- **Steps**:
  ```
  uv run pytest tests/upgrade/ -q
  uv run pytest tests/specify_cli/upgrade/ -q
  uv run --extra lint ruff check src/specify_cli/upgrade/ledger.py tests/upgrade/test_ledger_append_lock.py
  uv run --extra lint mypy src/specify_cli/upgrade/ledger.py
  ```
  Do not run the full heavy suite.
- **Files**: n/a
- **Parallel?**: No.

## Test Strategy

- Every assertion goes through `MigrationLedger.append` / `append_many` (production path); the
  helper-only variants are additional, never the only coverage.
- The lost-update test must fail because a record is *missing*, not because of a timeout: assert the
  count/ids, and keep the artificial read delay well under the lock timeout.
- The give-up test is the pairwise positive control for the wait test: one proves the append waits,
  the other proves it does not wait forever.
- Typecheck: `uv run --extra lint mypy src/specify_cli/upgrade/ledger.py` must report no issues
  (the repo runs mypy in CI; a passing pytest run is not a substitute).

## Risks & Mitigations

- **Flaky concurrency test** → drive both threads from one `threading.Event` and patch the read, not
  the write; keep the delay generous relative to thread start jitter.
- **Deadlock between partitions** → never hold one partition's lock while acquiring the other.
- **Accidentally locking the payload** → `ledger_lock_path` is the only place a lock path is built;
  the sidecar-suffix test pins it.
- **Windows** → the primitive is OS-file-lock based and portable; no `fcntl` use here.

## Review Guidance

- Confirm the red-first evidence exists (test run against the pre-fix tree) and that the test would
  fail if the lock were removed — i.e. revert `_append_lines` to the unlocked body and see T001's
  first two tests go red.
- Confirm no `kernel/` file changed (C-001) and no `base.py` import (C-002).
- Confirm the record bytes are unchanged and `atomic_write` is still the write.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
