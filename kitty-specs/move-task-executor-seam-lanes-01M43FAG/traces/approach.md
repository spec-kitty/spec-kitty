# Approach — move-task-executor-seam

- 2026-10-04: Start from the slice-1 pattern (verbatim move to a sibling seam module + identity re-export from `tasks_move_task`, lazy `_tasks.` bridge preserved). Do the test-friction pre-work first (derived compat keysets, generalised no-shadow guard) so the code moves do not churn symbol lists.
- 2026-10-04: SC-003 baseline (before WP01) — `pytest -n 8 --dist loadfile tests/specify_cli/cli/commands/agent tests/review tests/status tests/cli tests/tasks`: 5633 passed, 27 skipped, 2 xfailed, 1 failed (`test_charter_io::test_resolve_charter_path_raises_when_directory_not_readable`, red on base — root container permission check).
- 2026-10-04: post-tasks squad folded: WP02 helper signature (`operation`, the lazy plain emitter import), owned_files gaps, a non-vacuous WP04 liveness rule plus a negative control, US2 named tests.
