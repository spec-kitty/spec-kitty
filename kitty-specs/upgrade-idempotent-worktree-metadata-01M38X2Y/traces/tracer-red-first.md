# Tracer: red-first regression proof (#4972)

Per ADR 2026-07-17-1 (red-first discipline). The regression test drives the
real `MigrationRunner._upgrade_worktrees` entry point (the shared mint site,
`src/specify_cli/upgrade/runner.py`) with a fixture that reproduces the
issue's trigger shape: main is already at `target_version` with a
long-standing `last_upgraded_at`, and a live worktree is lagging on
`version` only (the "teammate/coord worktree lagging main" scenario from
`tracer-root-cause.md`). A lighter, direct-call fixture was chosen over a
full `implement`/`merge` coord-mission harness per the WP's "prefer the
lightest fixture that still exercises `_upgrade_worktrees` → autocommit
through the real code" guidance — it exercises the exact mint site, the real
`ProjectMetadata` load/save round-trip, and the real git auto-commit path,
without needing to stand up a second coordination layer the fix does not
touch.

Test: `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py::test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now`

## Baseline (RED) — before the fix

Fix temporarily reverted (`git stash push -- src/specify_cli/upgrade/runner.py`),
test file already in place:

```
cd .worktrees/upgrade-idempotent-worktree-metadata-01M38X2Y-lane-a
PYTHONPATH="$PWD/src" <repo-root>/.venv/bin/python -m pytest \
  tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py -q
```

Output (failure on the primary regression assertion; the no-op-repeat test
in the same file passed vacuously pre-fix since it never asserts alignment):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
____ test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now ____
tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py:140: in test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now
    assert wt_stamp == _MAIN_STAMP, (
E   AssertionError: worktree last_upgraded_at ('2026-09-24T06:10:17.955345+00:00') must align to the main checkout's already-stored stamp ('2026-01-01T00:00:00+00:00'), not mint a fresh now_utc() (#4972)
E   assert '2026-09-24T0....955345+00:00' == '2026-01-01T00:00:00+00:00'

    - 2026-01-01T00:00:00+00:00
    + 2026-09-24T06:10:17.955345+00:00
=========================== short test summary info ============================
FAILED tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py::test_bookkeeping_only_worktree_bump_aligns_to_main_stamp_not_fresh_now
1 failed, 1 passed in 0.52s
```

This is the exact divergence the issue describes: the worktree mints a fresh
`now_utc()` even though main's own `last_upgraded_at` never moved.

## Post-fix (GREEN)

Fix restored (`git stash pop`):

```
cd .worktrees/upgrade-idempotent-worktree-metadata-01M38X2Y-lane-a
PYTHONPATH="$PWD/src" <repo-root>/.venv/bin/python -m pytest \
  tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py -q
```

Output:

```
..                                                                       [100%]
============================== slowest durations ===============================
(6 durations < 1s hidden.)
2 passed in 28.74s
```

(Second run, cached environment: `2 passed in 0.5x s`.)

## Final home of the regression test

Kept as a focused unit-style test in
`tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py`
(`@pytest.mark.regression`, `# Issue: #4972` pinned), calling
`MigrationRunner._upgrade_worktrees` directly — not promoted to a
functional/CLI-level test, since the fix is fully exercised at the shared
mint site and the WP's T005 caller-coverage step (below) confirms by
reading the code that all three `_upgrade_worktrees` callers share this one
fix. `test_repeat_upgrade_is_a_true_no_op_once_worktree_has_caught_up` was
added alongside it to pin that a second call over an already-reconciled
worktree produces no second commit.

## T005 — caller coverage (read, not re-tested per caller)

All three call sites in `src/specify_cli/upgrade/runner.py` route through
the one shared `_upgrade_worktrees` implementation, so the fix inherits to
all of them:

- `runner.py:159` — `MigrationRunner.upgrade()`'s no-migrations,
  `from_version == target_version` sub-branch.
- `runner.py:219` — `MigrationRunner.upgrade()`'s migrations-pending branch.
- `runner.py:260` — `upgrade_worktrees_only()` (the CLI's no-migrations,
  already-current path via `cli/commands/upgrade.py`'s
  `_run_no_migrations_worktree_stamp`).

No caller reimplements the version-bump/timestamp logic locally; the fix
sits entirely inside `_upgrade_worktrees` / `_reconcile_worktree_bookkeeping`
/ `_aligned_worktree_timestamp`.
