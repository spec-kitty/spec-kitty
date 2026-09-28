---
affected_files: []
cycle_number: 1
mission_slug: honest-consolidation-txn-start-01M3M0YW
reproduction_command:
reviewed_at: '2026-09-28T13:37:11Z'
reviewer_agent: user
wp_id: WP01
---

# WP01 review (#5111) — changes requested

Overall the design is right. The marker is created with a fresh state, loaded and legacy states are never stamped, and the pre-mutation wrapper clears only a fresh run's record. I checked the wrapped window and nothing in it mutates anything: `_phase_gates_and_state`, the checkpoint capture and the claim capture only read git and write `state.json`. Clearing on BaseException is correct: `typer.Abort` from the declined confirmation and KeyboardInterrupt are covered, and nothing has been mutated at that point. The tests are not vacuous. At base 337213d9, 8 of 9 fail, and each half of the fix (marker-first ordering, wrapper) is pinned by its own test. Ruff, C901 and mypy are clean (the 4 no-any-return errors are baseline). The 13 integration reds are identical at base (#5044).

## Blocker

### B1 — the clear path breaks the invariant this WP establishes (FR-001, "state on disk implies marker")

`src/specify_cli/consolidation/state.py:353-356` (and `:366-367` in the `mission_id=None` branch) unlinks the **marker first, then `state.json`**. A hard kill between the two unlinks leaves a marker-less `state.json`. The next plain `consolidate` loads it as a resume and refuses it as "pre-fix in-flight". That is the #5111 wedge again, now reachable from `--abort`, from the new pre-mutation wrapper and from finalize. The squad asked for the marker-with-state rule to be crash-proof. Creation already gets this right (marker, then state), so deletion has to mirror it (state, then marker).

Fix:
- In `clear_state`, unlink `state.json` first and the marker after it, in both branches. Keep the return value semantics as they are.
- `executor.py:2977-2981` (`_phase_finalize_and_summary`) still calls `clear_post_fix_marker(...)` **before** `clear_state(...)`. That is the same inversion, and it is now a duplicate owner of the marker clear. Delete the call, because `clear_state` owns it now. `reconciliation.clear_post_fix_marker` then has no product caller. Remove it and its `__all__` entry, or state why it stays. Update `tests/consolidation/test_reconciliation.py`, which references it.
- Add a unit test that pins the order. For example, patch `Path.unlink` to record call order, or make the marker unlink raise and assert that `state.json` is already gone.

## Should-fix

- **S1** Only the "Merge gates failed" exit is tested for the wrapper. Add one CLI test for a non-gate exit, such as a declined hollow-review prompt (`typer.Abort`) or a `KeyboardInterrupt` raised from a patched phase. It should assert the fresh record is cleared. Also add a check that a `--resume` record is **not** cleared by a failing gate. It may already exist in `test_issue_4764_terminus_safety.py`; if so, name it in the PR.

## Nits

- **N1** `state.py:353` builds `runtime_dir / POST_FIX_MARKER_FILENAME` by hand. Use `post_fix_marker_path(...)` so the path is composed in one place.
- **N2** `reconciliation._post_fix_marker_path` is now a pure pass-through with swapped argument order. Consider calling `post_fix_marker_path` directly.
- **N3** The test redefines `_MARKER_FILENAME = "reconciliation.post-fix"`. Pinning the on-disk literal is defensible. If that is the intent, say so in a one-line comment; otherwise import `POST_FIX_MARKER_FILENAME`.
