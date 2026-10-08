# WP03 review feedback (cycle 1)

Verdict: changes requested. One blocking regression; the lock work itself is sound.

## Blocking

1. **Two existing tests are red on HEAD and green on the base `b87beaf0b`.**
   - `tests/consolidation/test_ordering_bake_seam.py::test_planning_only_assignment_writes_meta`
   - `tests/consolidation/test_ordering_bake_seam.py::test_planning_only_assignment_writes_meta_when_load_returns_none`

   Both patch `bake.write_meta`, which T013 removed from `consolidation/mission_number/bake.py`
   (`AttributeError: ... does not have the attribute 'write_meta'`). On the base, all three `-k planning_only` cases pass.
   Rewrite them against the locked path: seed a real `meta.json` and assert that `mission_number` lands.
   The second test pinned the `load_meta_fail_closed(...) or {}` one-key stub. That stub is gone: a missing `meta.json` now raises `FileNotFoundError` from `locked_update_meta`.
   `needs_number_assignment` returns `False` for a missing `meta.json`, so the stub could only be reached through a TOCTOU race. Replace the test with one that pins the new behaviour, and say in the commit why the stub is no longer created.
   Run the consolidation tests that exercise every module you touched. `tests/consolidation/` was missed: that directory, not only `tests/specify_cli/consolidation/`, holds the bake tests.

## Should fix in the same cycle

2. **Lock-acquisition coverage gaps.** `test_every_writer_takes_the_mission_lock` does not cover these locked writers:
   - `_write_mission_number_to_branch`, the scratch-checkout write that T013 names explicitly;
   - `_assign_planning_only_mission_number_if_needed`;
   - `backfill_identity.backfill_mission_ids`;
   - `doc_state.update_documentation_state`, which uses the raw `mission_write_lock` region.

   Add at least the planning-only case and `backfill_mission_ids`. For the scratch checkout, a focused test is enough: it should show that the key taken is the Mission's primary key, and that no lock is held when the `git add`/`git commit` subprocesses run.

## Non-blocking (fix if touching the file anyway)

3. **The `fallback_to_dir_name` docstrings and the hand-off disagree with the code.** The `mission_write_lock` docstring says the flag is only for "the migrations that heal the very metadata the key is read from (backfill-identity, backfill-topology, the repair)". It is also set by `backfill_mission_type`, `m_0_13_8_target_branch`, `upgrade/feature_meta.write_feature_meta` and `runtime_state_cutover._flip_phase`. The semantics are sound: when the key is unresolvable, every default caller raises, so no rival key exists, and each healer's write is the last act in its hold. Still, update the docstring (or narrow the call sites) so WP08 Rule 4 gets an accurate list. The default stays fail-closed, and both directions are tested; that part is good.
4. **The `bake.py` comment is wrong about where the key comes from.** It says the scratch write's key is "resolved from the scratch meta.json". It is not: `_lock_name_for_dir` → `_primary_meta(main_repo, name)` reads the main repository's primary `meta.json`, because `main_repo/.git` is a directory. Keying on the Mission's primary key is the right behaviour, so fix the comment, not the code.
5. In `backfill_identity.py`, the `# WP04: repo-level walk` banner is now indented inside `backfill_mission`'s body. Dedent it.
6. `backfill_topology._write_meta_canonical` no longer has a production caller; it is a test-only helper now. Note this for WP08 or move it into a test helper later.

## Verified (no action)

- Re-grep of `write_meta`/`json.dump`/`write_text` in doc_analysis, consolidation, migration and upgrade: no read-modify-write in WP03 scope is left outside the lock. The `drivers.py` merge-driver writes are out of scope. The `m_2_0_6` stale-dict write is handed to WP04.
- My own mutations: removing the lock in `backfill_mission` turns both of its cases red, and so does an unlocked read/write in `_locked_assign_mission_number`, for both bake cases. The overlap harness release (B's non-blocking probe) is correct, and it cannot pass vacuously, because each case also asserts the writer's own result.
- Sorted-key output from `m_0_13_8` and `backfill_mission_ids` via `write_meta`: their tests pass, and I found no golden affected.
- ruff, ruff format and complexity are clean. mypy shows 12 errors on both the base and HEAD, none new. The single `type: ignore` in the diff is a pre-existing line that was re-indented.
- Targeted run: 939 passed, 2 failed (item 1), 1 skipped.
