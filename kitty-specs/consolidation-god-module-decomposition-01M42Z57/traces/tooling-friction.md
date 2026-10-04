# Tooling friction

Tooling touched: `spec-kitty` mission CLI (create/spec-commit/setup-plan/tasks/implement/review/accept/consolidate), pytest + xdist, ruff, mypy, git worktrees.

- 2026-10-04: `spec-kitty agent mission create` made its own scaffold commit without the co-author trailers the operator requires on every commit; history will be compacted before the PR.
- 2026-10-04: `spec-kitty spec-commit` refuses a directory argument (`decisions/`); pass the files.
- 2026-10-04: the baseline run from a linked worktree trips the charter-write guard in `test_profile_charter_e2e.py` (environmental red).
- 2026-10-04 (WP01): `spec-kitty safe-commit` committed the new path of a staged `git mv` but left the old path's deletion staged; had to amend.
- 2026-10-04 (WP01): every pytest invocation pays ~60 s of collection/conftest start-up, so validation is batched into few large runs.
- 2026-10-04 (WP01): `spec-kitty agent action implement` on a single_branch (repo-root lane) WP never records `refs/spec-kitty/wp-base/<slug>/<wp>`: the repo root "workspace" already exists, so `ensure_workspace_materialized` skips `create_lane_workspace`, the only caller of `record_claim_base` on that path (`workflow.py:1636`, `implement_support.py:313`). `move-task --to for_review` then refuses with "no recorded claim base". Worked around with `--force` + note naming the real claim commit (e1813e51); already tracked upstream as #5459.
- 2026-10-04 (WP02): `spec-kitty implement WP02` (which would record the claim base) refuses WRITE_CHECKOUT_OCCUPIED because mission `reconcile-flake-family-01M34HR7` (committed on main) still has WP04 `in_progress`; `spec-kitty agent action implement` does not run that occupancy refusal for the same checkout. Two entry points disagree about occupancy; the other mission's stale state is not this mission's to change.
- 2026-10-04 (WP01/WP02): `ruff check --select I --fix` on an existing file re-sorts its whole (deliberately grouped, commented) import block; never run the isort fixer on pre-existing files in a move-only change. Reverted in a follow-up commit.
- 2026-10-04 (WP03): `tests/integration/test_merge_lane_planning_data_loss.py::TestRetentionConstraintSurvivesCleanup::test_explicit_delete_override_still_reachable` is red on origin/main (reproduced in a plain clone); filed #5645.
