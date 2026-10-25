# WP01 review feedback (cycle 1) -- reviewer-renata / claude-reviewer

The production code in `src/kernel/event_log_append.py` is sound. The lock is held across open, read, check and write. A torn tail is refused with the file byte-identical. A missing parent raises before any lock path is resolved. `NotAGitRepositoryError` and `GitTopologyUnavailableError` are handled as the contract says. The lock path is `sha256(normcase(str(resolved)))[:32]` under `<common>/spec-kitty-locks/event-logs/`, checked by hand against the contract. The code uses `lseek`+`read` (no `pread`) and `O_BINARY` through `getattr`. Every error is an `OSError`. Ruff, format, mypy and mypy --strict are clean, and complexity is at most 10.

Two tests do not fail when the behaviour they cover is broken. I confirmed both by mutation, in a scratch copy of the test file with the lane `src` on the path.

**Issue 1 (blocking, FR-007): `test_fsyncs_the_log` passes when the log's fsync is deleted.**
`tests/kernel/test_event_log_append.py:169-179` records every `os.fsync` and asserts `synced` is non-empty. `kernel.locks` fsyncs the lock record on every acquire (`src/kernel/locks.py` ~line 270), so the assertion holds without the log fsync. Mutant: `_write_unit` with no `os.fsync(fd)`. Result: all 25 tests pass.
Fix: assert that the log's own descriptor was fsynced. For example, record `(fd, os.fstat(fd).st_ino)` in the fake and assert that `log.stat().st_ino` is among the recorded inodes. Or wrap `event_log_append._write_unit`/`os.fsync` so that you assert the fsync came after the unit write on the log's fd. The test must go red when line 272 (`os.fsync(fd)`) is removed.

**Issue 2 (blocking, C-003 / contract rule 1): the digest rule is not pinned.**
The Java writer must compute the same lock file byte for byte (ADR 2026-10-22-1 D-4). No test checks the digest. `test_lock_path_lives_under_the_git_common_dir` (line 205) checks only `len(lock.stem) == 32`. Mutant: take the last 32 hex characters instead of the first 32. Result: all 25 tests pass. Hashing a different input (for example the unresolved path) would also pass.
Fix: add a pin test that recomputes the contract formula independently, without calling the module's helper:
`hashlib.sha256(os.path.normcase(str(log.resolve())).encode("utf-8")).hexdigest()[:32] + ".lock"`. Assert that it equals `event_log_lock_path(log).name`. Also add one literal golden value for a fixed string, so a later shared change to `sha256_digest` cannot drift without notice.

**Non-blocking (recommended in the same pass):**
- `test_lock_path_is_shared_by_every_worktree_of_one_repository` (line 211) proves the shared lock *directory*, which kills the `git_dir`-vs-`git_common_dir` mutant. It does not show that the *same* log gets the *same* lock file when a process runs from the lane worktree as when it runs from the main checkout. Add `monkeypatch.chdir(worktree)` and `chdir(repo)` and compute `event_log_lock_path(main_log)` from each; assert equality.
- `_encode_unit` does not type-check its elements. A `bytes` element raises `TypeError` from `in`, not `ValueError`. That is acceptable, but a one-line `isinstance(line, str)` check would match the documented framing contract.

Everything else on the checklist passes. Dead code: N/A, because callers arrive in WP02/WP03. Synthetic fixture: no. Silent empty return: none. Frozen surface: untouched. MUST-NOT clauses: none violated (no row validation, C-002). Shared files: none overlap other WPs. Fragility: every raise carries a remedy.
