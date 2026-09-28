# Tooling friction — honest-consolidation-txn-start

Tooling in play: `spec-kitty agent mission create`, the `consolidate` CLI under CliRunner, pytest over slow real-git integration fixtures (~90s setup each on this container).

- 2026-09-28 — `agent mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`, and the remediation only names that flag. Easy to follow, but a first-time agent has to retry.
- 2026-09-28 — `tests/integration` merge fixtures take ~90s of setup per file. With `-n 8`, a 12-file red-set run takes ~4 min. Red-first loops on these are expensive.
- 2026-09-28 — Lane worktrees have no `.venv`, and the repo conftest puts the lane's `src` first on `sys.path`. So `PYTHONPATH=<main>/src` does **not** give a base run from inside a lane: the first "base red" proof silently ran the fixed code (9/9 green). A true base run has to happen from the repo-root checkout.
- 2026-09-28 — `tests/consolidation/test_profile_charter_e2e.py::test_local_support_declarations_end_to_end` fails from any linked worktree, because the charter-write guard refuses writes from a linked worktree. It is green from the repo root. It looks like a regression in lane-local blast-radius runs.
- 2026-09-28 — `move-task` reports an illegal `for_review -> for_review` when a previous call already succeeded but its output was truncated by `tail`. Read the full output before retrying.
- 2026-09-28 — `ruff format` rewrites whole files that are on the formatter-debt exclude list (`forecast.py`, `executor.py`, `workspace.py`) when you name them explicitly. Use `--force-exclude`, or format only non-excluded files.
