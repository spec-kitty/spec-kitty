---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T12:03:36Z'
reviewer_agent: claude
wp_id: WP15
---

# WP15 review cycle 1: rejected on one test-pinning gap (source conversion is correct)

## [MEDIUM] tests/acceptance/test_gate_execution_context.py (owned section) -- the gates_core owned forwards are unpinned -- add a focused test

Mutation spot-check: delete the `owned=owned,` line in `gates_core._check_lane_gates` (the forward into
`_evaluate_acceptance_matrix`). All 7 `test_owned_*` tests stay GREEN (7 passed). The same applies to
the forwards `_evaluate_acceptance_matrix -> _acceptance_gate_context`,
`_evaluate_acceptance_matrix -> _matrix_surface_cannot_hold` and
`_matrix_surface_cannot_hold -> declared_home_surface`.

If any of these forwards is dropped, the accept gate silently judges the acceptance matrix on the
non-owned surface. That is the exact C1 / GEC-1 regression this WP exists to prevent.
WP15 DoD item 3 says the owned arm of EACH converted function is covered by a focused test.
`_acceptance_gate_context`, `_matrix_surface_cannot_hold`, `_evaluate_acceptance_matrix` and
`_check_lane_gates` have no owned-arm test that would fail on a dropped forward.

Required fix (test commit only, red-first not applicable to a pure pin, but prove non-vacuity by mutation):
- Add a test that calls `_check_lane_gates` (or `collect_feature_summary` with a mutate_matrix=False fixture that
  reaches the matrix branch) with `owned=fact`. Assert that the fact is received by
  `build_gate_execution_context` / `declared_home_surface`. Use function-scoped spies that forward to the
  real function, in the style of `test_declared_home_surface_delegates_not_reimplements`. Also assert the
  resulting `matrix_dir` is under `fact.mission_dir` while `stale_root_copy` holds a differing matrix in R.
- Re-run the mutation (drop `owned=owned` at gates_core.py `_check_lane_gates`, `_evaluate_acceptance_matrix`,
  `_matrix_surface_cannot_hold`): each must turn the new test(s) red. Restore with `git checkout`, do not commit the mutation.

## [LOW] src/specify_cli/acceptance/execution_context.py -- `ruff format --check` reports the file
Pre-existing drift: the same 6 hunks are reported on base 8a21949c5. The WP15 lines are not among the changed
hunks. Not required here, noted only. Do not reformat unrelated lines in this WP.

Everything else passed review: grep clean, signatures, no conditional kwargs, WP13 fold intact, out-of-map edits minimal and declared, red-first order verified, mypy identical (7 pre-existing errors on base and head), ruff check clean.
