---
work_package_id: WP01
title: Interim locked append primitive
dependencies: []
requirement_refs:
- FR-007
- FR-011
- NFR-002
- NFR-003
- C-002
- C-003
planning_base_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
merge_target_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
branch_strategy: Planning artifacts for this mission were generated on issue-6603-6606-eventbridge-gate-and-locked-appends. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6603-6606-eventbridge-gate-and-locked-appends unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-10-25T17:30:00Z'
  actor: claude
  note: Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/ledger_append.py
- tests/kernel/test_ledger_append.py
execution_mode: code_change
owned_files:
- src/kernel/ledger_append.py
- src/kernel/locks.py
- src/specify_cli/core/checkout_file_lock.py
- tests/kernel/test_ledger_append.py
role: implementer
tags: []
tracker_refs: []
---

# WP01: Interim locked append primitive

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`) before reading anything else, then run `spec-kitty charter context --action implement`.

## Branch Strategy

Planning base and merge target: `issue-6603-6606-eventbridge-gate-and-locked-appends`. Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP01 --agent claude --mission eventbridge-gate-and-locked-appends-01M5T0TN`. Never choose a base branch by hand.

## Objective

Ship the one interim lock contract and single-write append (contract `contracts/interim-ledger-lock.md`). FR-007, FR-011, NFR-002, NFR-003, C-002, C-003.

## Subtasks

### T001 — `LOCK_DIRECTORY` lives in `kernel.locks`

- Define `LOCK_DIRECTORY = "spec-kitty-locks"` in `src/kernel/locks.py` with its docstring.
- `src/specify_cli/core/checkout_file_lock.py` imports and re-exports it (`__all__` unchanged), so `status/locking.py` and `review/verdict_commit_queue.py` keep working untouched.
- Validation: `tests/kernel`, `tests/status` and `tests/review` locking tests still pass.

### T002 — `src/kernel/ledger_append.py`

Public API:
- `ledger_lock_path(ledger: Path) -> Path`. Rule: `git_common_dir(parent) / LOCK_DIRECTORY / "event-ledgers" / f"{digest}.lock"`, where the digest is `sha256(os.path.normcase(str(resolved_abs_path)))[:32]`. On a `GitTopologyError`, use the sibling `ledger.with_name(ledger.name + ".lock")`. Resolve with `Path.resolve()` (strict=False) after the parent exists.
- `ledger_lock(ledger, *, timeout_s=LEDGER_LOCK_TIMEOUT_S)`: a context manager that holds `machine_file_lock(path, blocking=True, timeout_s=...)` and translates `LockAcquireTimeout` into `LedgerLockTimeoutError`.
- `append_ledger_lines(ledger, lines, *, create=True, create_parents=False, no_follow=False, mode=0o644, precondition=None, timeout_s=...)`:
  1. Validate framing: non-empty, each a `str` without `\n` or `\r` → `ValueError`.
  2. `create_parents` → `mkdir(parents=True, exist_ok=True)`.
  3. Under the lock, `os.open(O_RDWR | O_APPEND | O_BINARY | (O_CREAT if create) | (O_NOFOLLOW if no_follow))`. Without `O_NOFOLLOW` support, `is_symlink` refuses.
  4. Read the existing bytes when a precondition is given (call it with them), otherwise the last byte only (`os.pread`/seek).
  5. Refuse a torn tail.
  6. One `os.write` of the UTF-8 joined unit, `os.fsync`, close; a short write raises.
- Errors (subclass `OSError`, each with `.code`): `LedgerAppendError`, `LedgerTornTailError` (`LEDGER_TORN_TAIL`, message names the file and the remedy: "inspect the last line; cut the partial bytes after the last newline, then retry"), `LedgerLockTimeoutError` (`LEDGER_LOCK_TIMEOUT`), `LedgerShortWriteError` (`LEDGER_SHORT_WRITE`).
- The module docstring states: interim, retires at the #6193 handover (ADR 2026-10-22-1 D-4), the Java writer takes the same lock file, and there is no row validation (operator ruling 2026-10-25).
- Complexity is 15 or below; split the open/read/write steps into helpers.

### T003 — Unit tests (`tests/kernel/test_ledger_append.py`)

- One row, a multi-row unit, and the exact bytes.
- Framing refusals.
- A torn tail refuses and leaves the file byte-identical.
- An empty file and a missing file (`create=False` → `FileNotFoundError`).
- `create_parents`.
- A precondition raise writes nothing.
- No-follow refuses a symlink.
- The lock path is the same from a worktree and from the main checkout (`git worktree add` in `tmp_path`), and uses the sibling outside git.
- `fsync` is called (monkeypatch).
- The errors are `OSError`s.

### T004 — Concurrency and timeout

- 8 `multiprocessing` processes × 50 rows → 400 parseable lines (NFR-002). Mark `slow` only if it exceeds 2 s.
- Lock timeout: hold `ledger_lock` in the test, then append with `timeout_s=0.2` → `LedgerLockTimeoutError`, and nothing is written.

## Definition of Done

All tests pass; ruff, ruff format and mypy are clean on the new files; complexity is 15 or below; no suppressions.

## Reviewer guidance

Check the lock-path rule against the contract byte for byte. The lock must be held across the read-check-write. Errors must be `OSError` so existing swallowing callers are unchanged.
