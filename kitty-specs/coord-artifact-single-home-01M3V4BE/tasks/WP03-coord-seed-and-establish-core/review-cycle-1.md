---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T12:36:41Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Commits reviewed: red `0582d178a8`, impl `1da5a87eaa`.

## What already passes

- The red-first commit is red at `0582d178a8` for the right reasons. The new test modules fail at import because the module and the export do not exist. The 4 re-pinned gate tests fail on the old `COORD_WRITE_SURFACE_UNMATERIALIZED` refusal. Everything is green at the tip.
- Targeted suite: 188 passed (coord_seed, event_prefix, write_location, selfmat, remedy_5113, mission_runtime_surface, layer_rules, no_dead_modules, no_dead_symbols).
- Guards: 1179 passed, 7 skipped. This covers the named guards plus every non-e2e/integration/stress test that references `feature_status_lock` / `FeatureStatusLockTimeoutError` / `assert_coord_write_materialized` / `write_artifact`.
- ruff, `ruff format --check --force-exclude` and C901 are clean. mypy --strict reports 0 errors in WP03 files. The 20 errors it does report are in `runtime/next/*`: pre-existing, pulled in by the lazy import.
- Fork refusal writes nothing. The prefix rule is pure and tested. Idempotence and atomicity hold. MR-1/MR-2 package-root imports are respected. The lock key and lock root follow X6. `checkout_root` is correct. The remote-only refusal (#4970) is kept. DELETED refuses with its hint. The single `COORD_SEED_TRAILER` constant is used. The X1 negative test (#5519 shape, no phantom seed or trailer) is present and correct.
- (a) D22 delegation, including the EMPTY no-op in the gate, matches research D22 exactly, and the re-pins are deliberate and declared. Accepted.
- (b) `error_code = "STATUS_LOCK_HELD"` is accepted. I verified that the bounded lock fires it after about 10s with nothing written. The `next_cmd.py:873` path is not reachable by this exception, so the only visible change is in owned mark-status. Keep the PR-body declaration. A test is still missing (see B4).
- (d) The unified `_run_merge_and_commit` that re-runs the fork check is accepted: a strictly safer superset. Note that it can carry new root records on a retry, which goes slightly beyond the I-SEED-6 wording ("carries nothing new"). Record that in `design-decisions`.

## Blocking

**B1 (HIGH, NFR-002 / FR-003a): post-fix EMPTY never carries root-only COORD records.**
- `_handle_empty_post_fix` restores the COORD paths from the tip and then calls `seed_coord_surface(post_fix=True)`.
- Under the lock, `_seed_coord_surface_locked` re-probes. The Mission dir now exists, so the state is MATERIALIZED, and `_seed_pending` is False because the dir is tracked. It returns `SeedReport()` without carrying anything.
- `_write_merge_in_place` for post-fix is therefore unreachable (lines 344-347 have 0 coverage).
- Reproduction:
  1. prefix EMPTY, then establish (SEEDED);
  2. `rmtree` the coordination Mission dir;
  3. append `{"event_id":"01ROOTONLYAFTERSEED00000"}` to the root log;
  4. establish again: RESTORED_FROM_BRANCH, with `carried=()`, and the event is absent from the coordination log.
- This contradicts data-model §2 ("then seed rules for any root-only records") and accessor contract L41.

**B2 (HIGH, concurrency / NFR-002): the post-fix restore runs outside the status lock, with no re-probe.**
- `_restore_coord_kind_paths_from_tip` runs `git checkout <branch> -- <paths>` before `seed_coord_surface` takes the lock.
- Two writers that both probed EMPTY can interleave like this:
  1. A restores, returns, and appends an uncommitted event.
  2. B's later `git checkout` overwrites that file with the tip content, and A's event is lost.
- Fix B1 and B2 together. For a post-fix request, inside `_seed_coord_surface_locked`:
  1. re-probe;
  2. if the state is still EMPTY, restore the COORD-kind paths;
  3. merge in place with the fork check;
  4. commit;
  5. restore the root copy.
- If the re-probe says MATERIALIZED, another writer won: return.
- Add a test for root-only carry after the post-fix restore. Add a test where the restore is skipped because the state is already MATERIALIZED under the lock.

**B3 (MEDIUM-HIGH): the pending-seed fast path depends on the operator's git config.**
- `_seed_pending` runs `git status --porcelain` and expects exactly `?? kitty-specs/<dir>/`.
- With `status.showUntrackedFiles=all`, git lists per-file lines; with `no`, it prints nothing. Either way the refused seed is **never retried**, and the Mission dir stays uncommitted indefinitely.
- Reproduced with `git config status.showUntrackedFiles all`: refuse, then retry gives `seed=None` and no commit.
- Fix: pass `--untracked-files=normal` explicitly, and parse NUL-separated output (`-z`; the binding correction asks for normalised `-z` paths). Add a test under both config values.

**B4 (HIGH, required tests missing; coverage of coord_seed.py is 89%, below the 90% that T017 requires).** The untested lines are the riskiest branches. The following required or contracted tests are missing:
1. **The refused-then-retried seed commit** (binding U1, "Test it in tests/coordination/test_coord_seed.py"; T015). Lines 429-431 and 480/486/490 have no coverage. The test must cover:
   - the warning in `SeedReport.warnings` and the WARNING log;
   - the dir staying uncommitted;
   - the next COORD write committing it with the trailer;
   - a third write making no further commit.

   My reviewer probe shows the path works under the default git config.
2. **Root restoration, untracked variant.** `test_root_restoration_untracked_extra_events_removed` actually tests the dirty-tracked case; lines 374/378-379 are uncovered. Add a real untracked case, and rename the existing test.
3. **I-SEED-5 non-log COORD carry.** Lines 264-272 are completely uncovered. Cover:
   - a root-only `traces/*.md` / `status.json` / `issue-matrix.json` being carried;
   - both copies present and differing: the coordination copy is kept, a warning is raised, and the root is untouched;
   - PRIMARY files never copied (I-SEED-9).
4. **D4 negative test** (binding "D4 discriminator"): use the shape from `test_surface_resolver_solo_coord_primary.py:107-146`, a branch cut after the target commit that carries `meta.json`/`spec.md`, with the worktree EMPTY. Assert:
   - the result is SEEDED, never RESTORED_FROM_BRANCH;
   - no loud warning;
   - no PRIMARY file is written to the coordination dir.
5. **The decisions stream:** a fork refusal with `stream="decision_log"`, plus a carry of `decisions.events.jsonl`. Only `status_log` is tested today.
6. **The bounded lock fires `STATUS_LOCK_HELD`.** Monkeypatch `BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS` small, hold the lock from a subprocess, and assert `error_code == "STATUS_LOCK_HELD"` and that nothing is written. Also add one assertion on the class attribute.
7. **The owned arm** (lines 567-570, 583-586): at minimum the `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` translation, and owned success if the WP02 fixtures support it.
8. **NFR-002 across fixtures (a)-(d)** (T017 step 7). Only one fixture is used today.

**B5 (MEDIUM): `Establishment.WORKTREE_MATERIALIZED` is never produced.**
- UNMATERIALIZED that becomes MATERIALIZED returns `Establishment.NONE`, because `_handle_materialized` hard-codes NONE. A reviewer probe got `NONE` with `coord_state_before=UNMATERIALIZED`.
- The contract and T016 say the establishment is MATERIALIZED "unless a seed follows".
- Return `WORKTREE_MATERIALIZED` on this path, keep the pending-seed report, and add a test where UNMATERIALIZED with a local head becomes MATERIALIZED and no seed follows.

**B6 (MEDIUM, cross-WP interface): WP04 T021 needs a public post-fix discriminator from WP03.**
- WP04's prompt (L209/L214, round 5) states: "WP03 always provides it". The call there is `coord_branch_is_post_fix(repo_root, coordination_branch, mission_id)`, imported lazily from `coord_seed.py`.
- Only the private `_trailer_present` exists.
- Expose it under that name, as a read-only check with no writes, and use it internally (single authority). See B8 on fail-closed behaviour.

**B7 (MEDIUM, governance): the dead-symbol cap grew from 293 to 299. Ruling: not accepted.**
- Charter Burn-down Policy (a) makes the baseline shrink-only: growth FAILS CI.
- A same-commit cap bump self-certifies the growth it was meant to stop. Shrinkage only WARNS, so the cap would stay loosened even after consumers land.
- The mission already chose OD-DEAD, "expected red + activity-log note, consumer turns it green; prefer zero-red", and said WP03 should be zero-red.
- Required changes:
  - Revert `_baselines.yaml` `allowlist_entries` to **293**. Remove the 6 entries and the `category_c_wp_in_flight_coord_write_location` category.
  - `SeedRequest` / `seed_coord_surface`: their only caller, by contract design, is the same module. Make them private (`_SeedRequest`, `_seed_coord_surface`; out of `__all__`). Tests may import the private names. Confirm the widened walk is clean.
  - `MalformedEventLogLineError` / `DuplicateEventIdError`: give them a real production caller. `coord_seed` catches them and re-raises a structured `ActionContextError` naming the Mission, the file path, the coordination branch and the recovery steps. This also fixes T016 step 6 ("every error message names the Mission, the coordination branch and a recovery command"); today they escape as bare `ValueError`s with no context.
  - `COORD_SEED_TRAILER`, `CoordSeedForkRefused` and the new `coord_branch_is_post_fix` (B6) are genuine cross-WP vocabulary. Leave them **un-allowlisted**: an expected transitional red on `test_no_dead_symbols`, recorded in the Activity Log naming the curing WP:
    - WP04 imports `coord_branch_is_post_fix`;
    - WP06 T031 imports `COORD_SEED_TRAILER`;
    - WP07 (or WP05/WP09) imports `CoordSeedForkRefused` by name where it wraps or translates it.

    No allowlist edits means no cleanup debt, and the red cures itself when the consumer lands.

**B8 (MEDIUM): a silent empty on git error flips decisions.**
- `_trailer_present`, `_coord_tip_relpaths` and `_coord_side_text` return `False`/`()`/`None` on a non-zero git exit.
- A transient git failure therefore:
  - reclassifies a post-fix Mission as pre-fix;
  - makes `_seed_pending` true;
  - treats the coordination log as empty, so the merged log drops the tip events and is then committed.
- The branch is known to exist by then (state EMPTY or MATERIALIZED), so a git failure is an error, not an absence.
- Distinguish "path absent at tip" (`git cat-file -e` / `ls-tree` output) from a command failure, and raise on failure.

**B9 (MEDIUM, byte-faithful merge): a missing trailing newline corrupts the merged log.**
- `merged_log_bytes(r, c, carry_tail)` with a coordination log whose last line lacks `\n` yields `{"event_id":"a"}{"event_id":"b"}\n`: two rows glued together, malformed JSONL that is then committed.
- Insert a separator when the last kept coordination line lacks a newline, and make sure the merged output ends with `\n`.
- Add table rows to `test_event_prefix.py` for this case.

## Non-blocking (fix while you are in there)

- **L1:** `# noqa: BLE001` at `coord_seed.py:585` is an unused directive (BLE is not enabled; RUF100). Remove it. The broad catch is fine because it is translated and has a rationale.
- **L2:** The MATERIALIZED path takes the status lock (bounded 10s) on every gate-delegated write, even when no seed is pending. That adds a `STATUS_LOCK_HELD` failure mode to the hot path under contention. Run the cheap porcelain fast-path check before locking, then re-check under the lock.
- **L3:** T014 step 9 asks `_write_merge_via_temp_rename` to remove the temp dir on `OSError`/`FileExistsError` and re-probe once. Today it relies on the next call's cleanup. Either implement it or record the deviation in `design-decisions`; the atomicity test shows the leftover is healed.
- **L4:** `_restore_root_files` "dirty" uses `git checkout -- <path>`, which restores from the index. A staged-new (`A `) root file is reported as restored but stays on disk. Handle staged entries (for example `git restore --source=HEAD --staged --worktree`, or unstage first).
- **L5:** The selfmat re-pins only assert "no raise". Add one assertion that the committed matrix content is present in the materialized worktree afterwards. That is the #4970 no-clobber control, and it proves D22 did not reintroduce the original data-loss shape.

## Notes for WP04 / WP06 (no action in WP03)

- **WP04:**
  - Delegate `write_dir(kind)` for COORD kinds to `establish_coord_write_location`. Populate `checkout_root` for PRIMARY results (repository root checkout, or `owned.owned_root`).
  - Import `coord_branch_is_post_fix` lazily (B6) for T021. This cures that symbol's transitional dead-symbol red.
  - Do not re-implement the trailer probe.
  - Exceptions propagate unchanged, including `CoordSeedForkRefused` and `FeatureStatusLockTimeoutError` (`STATUS_LOCK_HELD`).
  - After B5, expect `WORKTREE_MATERIALIZED` for an UNMATERIALIZED-to-MATERIALIZED result with no seed.
- **WP06:** import `COORD_SEED_TRAILER` (never a literal) for create's coordination commit. This cures that symbol's red. Create's eager seed relies on the empty-collect path (`carried=()`).
- **Closeout:** `test_no_dead_symbols` must be green with `allowlist_entries` ≤ 293.
