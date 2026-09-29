# WP04 review feedback (cycle 1) — reviewer-renata

Verified good: red->green (5 red + 1 green guard at 33b10729, 6/6 at tip; repro tests unchanged since the red commit); ordering lock -> merge-workspace abort/cleanup -> restore -> clear/teardown; `consolidate()`/`_run_real_merge` untouched; `_dispatch_abort` C901 = 12; SC-005 asserts CAS reason + expected == recorded post tip + observed == moved; FR-011 keeps landing + record; AST pin floor 2 with the exact abort helper allow-listed; dead-symbol allowlist removal legitimate (shrink-only, symbol now consumed by consolidate.py). All targeted suites, named gates, ruff and mypy (3 pre-existing errors at base and tip, none in WP lines) are green.

## 1. (BLOCKING) The live-lock refusal must not apply to a record with no snapshot — FR-005 "pre-fix record keeps today's behaviour"

`_abort_hold_global_lock_or_exit` refuses unconditionally when another mission's live merge holds `__global_merge__`. Refusing is the right safety behaviour when this abort will run the rollback (FR-005 says the restore runs *holding the lock*; A's CAS restore of the shared target could land between B's read and B's CAS advance). But when `state.pre_mutation_refs` is empty no ref is moved, so the lock is not needed, and FR-005 explicitly says such a record "keeps today's behaviour with a notice". Today's behaviour (the deliberate #4996 / WP09 C-2 design) is: clear A's record, leave B's live lock in place.

`tests/consolidation/test_merge_state_authority.py::test_abort_of_other_mission_leaves_live_global_lock` persists exactly such a no-snapshot record (`_persist_state` sets no `pre_mutation_refs`), so the test was rewritten to hide a spec deviation, not to reflect a required change.

Requested:
- In `_dispatch_abort` / `_abort_hold_global_lock_or_exit`: skip the lock acquire/refusal when `not state.pre_mutation_refs` (no restore to protect); keep the refusal for snapshot-bearing records.
- Revert `test_abort_of_other_mission_leaves_live_global_lock` to its original assertions (A's record cleared, B's lock kept, owner == B). The snapshot-bearing refusal is already pinned by `tests/terminus/test_repro_5318_abort.py::test_5318_abort_refuses_while_another_missions_merge_is_live` and the unit test; add one unit case "no snapshot + live foreign lock -> proceeds, lock left" in `test_consolidate_abort_rollback.py`.
- Do NOT implement the finer rule "refuse only when some branch would actually be restored" — that needs a pre-classification of ref states outside `rollback_to_snapshot`, i.e. a second classifier beside the single authority. The snapshot-present predicate is the right granularity.

## 2. (BLOCKING, small) Lock taken by the abort leaks on an exception

Between `_abort_hold_global_lock_or_exit` (which may now create the lock owned by A) and the trailing `release_merge_lock_if_owned`, an exception (`_cleanup_merge_workspaces_for_state`, `abort_git_merge`, a git error inside `rollback_to_snapshot`, `_teardown_coordination_for_abort`) leaves `__global_merge__` owned by A while A's record still has remaining WPs — so it reads as live and blocks every other mission's consolidate until someone re-runs `--abort` for A. The pre-WP04 abort never took the lock, so this is a new failure mode. Release on the exception path (e.g. wrap the restore section in try/except BaseException -> `release_merge_lock_if_owned(..., owner_token=state.mission_id)`; re-raise), keeping `_dispatch_abort` <= 15 (extract if needed), and add a unit test that forces the authority to raise (a real failure, e.g. a snapshotted branch whose ref file is made unreadable, or monkeypatch only the authority call) and asserts the lock is released.

## 3. (Non-blocking, note in Activity Log) legacy/dead lock path runs the restore unlocked

When the lock is held by a dead owner or a legacy unowned lock, the abort proceeds without holding the lock (docstring says so). Acceptable, but a legacy unowned lock while another mission's record is active is exactly what `_lock_owner_is_dead` treats as *live*; consider refusing in that case too for consistency with `release_merge_lock_if_owned`. Your call — document the decision.
