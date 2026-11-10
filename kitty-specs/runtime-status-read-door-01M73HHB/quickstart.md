# Quickstart: Runtime status readers through the read door

## See the #7507 fix

1. Take a coordination Mission whose lanes are committed on its coordination branch, with WP01 planned and WP02 waiting for review.
2. Empty its coordination worktree: keep the worktree, remove the Mission directory inside it.
3. Run `spec-kitty next --mission <handle> --json` (query mode).
   - Before this Mission: `blocked`, "no actionable wp", all counts 0, weighted 0.0.
   - After: WP01 is next, 1 planned and 1 for review, weighted 30.0, the same as with a materialized worktree.

The scripted version is `research/repro/repro_cells.py MATERIALIZED EMPTY UNMATERIALIZED`, run from the repository root with `PYTHONPATH=.`.

## Use `--auto-remediate`

1. On a coordination Mission whose coordination worktree is not checked out, run `spec-kitty next --agent <name> --mission <handle> --result success`. It blocks with "materialize it" and the doctor command, as before.
2. Run it again with `--auto-remediate`. One line reports the materialized worktree, and the normal decision follows.

## Check the debt

Run `pytest tests/architectural/test_status_read_single_door.py tests/architectural/test_ratchet_baselines.py`. Both pass with 33 allowlist entries and no `src/runtime/next/` entry.
