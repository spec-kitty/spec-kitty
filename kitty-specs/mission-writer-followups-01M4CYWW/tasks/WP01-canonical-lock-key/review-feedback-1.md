# WP01 review feedback, cycle 1 (claude-reviewer)

Verdict: changes requested. What is good: the key function, the held-key thread-local, the core doors and the tests are solid. Mutation checks were killed: making `mission_write_lock` key on `feature_dir.name` fails 7 of 18 tests, and making `_registered_hold` a no-op fails the hold-stability test. The tests pass 5 of 5 runs. ruff, format and C901 are clean, and mypy shows 24 errors both before and after the change, so there are no new ones. One blocker remains: the A1 invariant does not hold for every Mission shape.

## B1 (blocker): the transaction lock key and `mission_lock_key` still differ on flat legacy Missions

`_transaction_lock_key(slug, mid8)` builds `<slug>-<mid8>` whenever a mid8 is known. It does not ask whether the Mission is coordination-routed. `mission_lock_key` uses the coordination name only when `coordination_branch` is recorded. So the two functions disagree on a flat legacy Mission whose identity was backfilled: a `kitty-specs/060-test/` directory whose meta records `mission_id` but no `coordination_branch`. This is a common shape: every pre-083 project that ran `migrate backfill-identity`.

Reproduction (git repo, `kitty-specs/060-test/meta.json` = `{"mission_slug":"060-test","mission_id":"01KXYZAB...","mission_number":60}`):

```
resolve_bookkeeping_transaction_identifiers(...) -> effective_mid8='01KXYZAB', coord_branch=None
_transaction_lock_key('060-test', '01KXYZAB') -> '060-test-01KXYZAB'
mission_lock_key(kitty-specs/060-test)        -> '060-test'
```

A real flow takes the transaction on this shape. The flat or legacy arm of `implement_planning_commit._commit_planning_artifacts_transaction` calls `_run_planning_artifact_commit`, and that calls `BookkeepingTransaction.acquire` with `effective_mid8`. The transaction then locks a file that no `mission_write_lock` writer takes. This mismatch was already there before this WP. But the WP's deliverable is the data-model invariant "for every Mission, `mission_lock_key(primary) == mission_lock_key(coord) ==` the transaction key", and the plan says "the status transaction and every door use the same function". Today the transaction site shares only the composer (`mission_lock_dir_name`). It does not share the routing decision.

Fix: derive the transaction key from `mission_lock_key`. Two ways:
- Call it on `<lock_root>/kitty-specs/<slug>` (for an owned checkout, read the primary meta from the canonical root, not from the owned root).
- Or give `_transaction_lock_key` the coordination-routing fact, so it returns `<slug>-<mid8>` only for a coordination-routed Mission and the Mission directory name otherwise.

Add a key-equality test for the flat backfilled shape, through the real `acquire` (or `resolve_bookkeeping_transaction_identifiers` plus the lock site). It must fail on the current head.

## S1 (should fix): `060-test` with a coordination branch and no mid8

`resolve_transaction_mid8` returns `""` for a legacy `NNN-` slug even when `coordination_branch` is declared, so the transaction locks `060-test`. On the same shape, `mission_lock_key` raises `MissionLockKeyUnresolved`. So every `mission_write_lock`, `mission_write_lock_dir` and `capture_rollback_point` call on such a Mission now raises, where it used to work. That breaks implement and review there.

Pick one rule and apply it to both functions:
- Option (a): follow the cascade's legacy carve-out. The key becomes the bare directory name, and the raise is kept only for the modern case where the cascade itself raises.
- Option (b): also refuse in the transaction.

Plan A3's "no silent fallback" reads most naturally as option (a): the carve-out is the documented dual-era rule, not a silent fallback. Whichever you choose, the parametrized `SLUG` case in `test_coordination_mission_without_a_resolvable_mid8_raises_a_typed_error` must match it.

## Notes (no change needed in WP01)

- Accepted deviation: leaving `_mission_specs_dir_name` producing the trailing-dash `foo-` for paths is fine, because only the lock key matters for A1/A3 and `test_coord_dir_seam` pins the path composition. But see B1: the separate lock-key function has to share the routing decision as well as the grammar.
- Gap until WP13: emit, work_package_lifecycle, move-task, mark-status and the other direct `feature_status_lock(.name)` callers still lock `060-test`, while `mission_write_lock` and `coord_status_lock` now lock `060-test-<mid8>` on a bare-directory coordination Mission. I found no `capture_rollback_point` call made under one of those old-key holds, so capture is not refused in the interim. But one thread can now hold both keys, so there is a possible lock-order inversion between threads until WP13 lands. WP13 must close this before the PR.
- Hold reuse covers only `mission_write_lock`. `BookkeepingTransaction` and `coord_seed` take `feature_status_lock` directly and do not register a held key, so a meta change inside a transaction is not covered by A4. WP13 should either register those holds or record why it is safe.
- When a caller passes a worktree path explicitly as `repo_root`, `literal_primary_meta` reads that worktree's copy and not the canonical primary copy (A4). Current callers pass `main_repo_root`. Consider canonicalising the root used for the meta read.
