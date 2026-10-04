# Implementation Plan: Root-vacuous chmod tests + TestOrdering isolation

**Branch**: `claude/happy-rubin-aq1qc6` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

This is a test-quality mission with one dead-code deletion. Every test change is red-first. It is proven against a planted break in product code, and the break is reverted and never committed (C-002).

## Technical Context

**Language/Version**: Python 3.11
**Testing**: pytest; `tests/_support/eacces.py` (`deny_open_in`, `deny_path_method`) from PR #5656
**Constraints**: Run as root (uid 0) so the root verdict is the one observed. No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Charter Check

- Standing Order #4 (test remediation): judge the test, not the blame. Each site is classified as follows.
  - The three read-only `.gitignore` tests are valid; they are proven with no change.
  - The two seam-injected sites are already valid; they are proven with no change.
  - `TestStoreUnreachable` is vacuous; it is fixed by seam injection.
  - `TestOrdering` is stale (it depends on a hidden import); it is re-pinned.
- Standing Order #2 (campsite): `GitignoreManager._atomic_write` is dead in `src/`. It is deleted inside the file set this mission already touches.
- Smallest viable diff: there are no product behaviour changes. The only `src/` edit is deleting the dead method and its two now-unused imports.

## Design decisions

1. **History-db seam.** `UpgradeAttemptStore` opens SQLite through `sqlite3.connect`, a C-level open that neither eacces helper reaches. `_connect`'s first filesystem call is `self._db_path.parent.mkdir(...)`, so `deny_path_method(monkeypatch, "mkdir", db_dir)` denies the open with the shared helper (C-001). That is the real failure for an unwritable, not-yet-created history dir. A recording wrapper around `_connect` proves the denial reached the store. Without it, a runner that skipped recording would also "return normally", which is exactly why the old test was vacuous.
2. **Retarget, don't delete, the `_atomic_write` tests.** The symlink-race intent still applies to the live writer `write_gitignore_text`.
   - The mkstemp-hooked race test never fired against the live writer, which uses `NamedTemporaryFile` and so never calls `tempfile.mkstemp`. It is re-hooked on `NamedTemporaryFile`.
   - The probe test now pins the writer's own symlink refusal.
3. **#5186 fixture.** A class-scoped autouse fixture calls `auto_discover_migrations()`. It is not a module-level import, because other tests call `MigrationRegistry.clear()` (C-003). The count==1 asserts stay (C-004).

## Project Structure

```
src/specify_cli/gitignore_manager.py                         # delete _atomic_write (+2 unused imports)
tests/cross_cutting/test_gitignore_manager_unit.py           # retarget 2 tests, fix 1 docstring
tests/specify_cli/readiness/test_upgrade_ux_migration.py     # seam-inject TestStoreUnreachable
tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py  # TestOrdering fixture
```

## Implementation Concern Map

### IC-01 — Root-vacuous denied-write tests (#5654)

FR-001, FR-002, FR-003, FR-004, FR-006. WP01.

### IC-02 — TestOrdering isolation (#5186)

FR-005. WP01.
