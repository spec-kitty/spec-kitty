# Tooling friction — move-task-executor-seam

Tooling touched: `spec-kitty agent mission create/setup-plan/finalize-tasks`, `spec-kitty implement`, ruff/mypy, pytest-xdist, architectural gate battery.

- 2026-10-04: slice 1 showed that ~70 test patch sites target private `_mt_*` names on `tasks_move_task`; any move needs mechanical repointing. Tracked as FR-008 / #2561.
- 2026-10-04: `tests/architectural/untrusted_path_audit/inventory.md` pins `file:line` rows; moving a sink requires a hand edit of the row (slice 1 did this for two baseline-read sinks).
- 2026-10-04: `spec-kitty implement WP01` on a single_branch mission refused with WRITE_CHECKOUT_OCCUPIED because an UNRELATED mission merged on main (`reconcile-flake-family-01M34HR7`, target branch `fix/reconcile-flake-family-4882`) carries WP04 `in_progress` in its committed event log. `in_progress_wps_in_write_checkout` (lanes/checkout_occupancy.py) does not scope occupants by target branch, so one stale merged mission blocks every single_branch mission in the repo. Workaround: re-created the mission as `lanes` topology (`move-task-executor-seam-lanes-01M43FAG`); the single_branch shell `move-task-executor-seam-01M43EK1` was retired unstarted. Upstream gap to file at closeout.
