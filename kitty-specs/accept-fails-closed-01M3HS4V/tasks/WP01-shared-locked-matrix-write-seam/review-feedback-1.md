# WP01 review feedback (cycle 1) - reviewer-renata (claude)

Overall: the seam, guard, FR-002 wiring, #4858 spy re-pointing and the architectural census edit are correct; 305 passed / 2 skipped on the targeted set, ruff/mypy/C901 clean, format debt in acceptance_verdict.py / test_acceptance_verdict_command.py is pre-existing (reduced, not increased). One blocking non-vacuity gap:

**Issue 1 (blocking) - FR-003 condition 1 ("R was pending in accept's snapshot") is untested.**
Mutation: deleting the `if getattr(snapshot_row, spec.result_attr) != spec.pending_value: return False` guard in `_row_is_owned` (src/specify_cli/acceptance/matrix.py ~L668) leaves all 49 tests in test_matrix_write_seam.py + test_acceptance_verdict_command.py green. This condition is load-bearing: when a row was already terminal in the snapshot (e.g. `pass`) and a concurrent `acceptance-verdict --result pending` resets it to `pending` in fresh, accept must NOT stamp its stale `pass` back over it. Add a table case for BOTH criteria and negative invariants: snapshot=`pass`, judged=`pass` (or `fail`), fresh=`pending` -> fresh stays `pending`. Confirm it goes red with the guard removed.

**Issue 2 (non-blocking, fold while there) - `test_snapshot_only_row_not_readded` is partly masked.**
Both variants use an EMPTY fresh section, so `_splice_owned_rows_for_spec`'s `if not fresh_rows: return` short-circuits before the ownership check runs; an implementation that appended missing judged rows would still pass. Give fresh one unrelated row (e.g. FR-999 / NI-999 pending) and assert the snapshot-only id is still absent and the unrelated row untouched.

**Issue 3 (non-blocking, optional)** - `locked_acceptance_verdict_guard` uses a production `assert fresh_matrix is not None` for mypy narrowing (matrix.py ~L789). The invariant holds, but an explicit `if fresh_matrix is None: raise AcceptanceVerdictNotReadyError(...)` (or restructuring so the None branch raises directly) avoids relying on `assert` under `python -O`.

Anti-pattern checklist: 1 dead code - `splice_owned_rows` / `locked_acceptance_verdict_guard` / `AcceptanceVerdictNotReadyError` have no production caller yet; accepted as by-plan (WP02 wires them), not a blocker. 2 PASS. 3 PASS. 4 FAIL-ish via Issue 1 (spec'd condition unpinned). 5 PASS. 6 PASS. 7 PASS (test_status_events_writes_gate.py edit is pre-authorized by the squad fold). 8 PASS (ValueError/TypeError raises are documented contract guards).
