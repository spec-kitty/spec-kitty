---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T12:42:13Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP09
---

# WP09 review cycle 1: changes requested (reviewer-renata)

Verified: red-first holds (at 0a4e2edd79 the WP's tests give 14 failed, 6 passed). The two flipped assertions (lifecycle_sync recreate, legacy-topology sparse) follow restated ruling 3; they are not weakened, because both now also assert the exclusion is applied and the fork-time blob is still there. Every lane-checkout creation route in src goes through `open_lane_checkout`. The gate flags the pre-WP09 allocator, lifecycle_sync and review sites. The blast-radius tests pass (2751 passed, 12 skipped).

## Blocking

**Issue 1: on the `lanes` topology, the new exclusion counts as LEGACY sparse-checkout and blocks `implement` and `consolidate` (regression).**
`git/sparse_checkout.py::_policy_from_meta` counts a lane worktree as `MANAGED_LANE` only when `meta.json` has a `coordination_branch`. WP09 now gives `lanes`-topology lanes, and the review and recreate routes of non-coordination Missions, a sparse checkout. `scan_repo` classifies those as `LEGACY_USER` / `is_blocking`. I reproduced it with your `_seed_mission(topology="lanes")` and `_allocate` fixtures. `require_no_sparse_checkout(... command="spec-kitty agent action implement")` raises `SparseCheckoutPreflightError: legacy sparse-checkout state detected`. A review checkout on `lanes` gives the same `LEGACY_USER` result. So after the first lane is allocated, `implement` of any further WP and `consolidate` (`consolidation/executor.py`) refuse. `doctor sparse-checkout --fix` would also strip the exclusion. `lanes_with_coord` is unaffected.
Fix: make the managed-lane policy cover every Mission with code lanes. Derive the expected patterns from the same `lane_status_exclusion_patterns(lane_mission_dir_name(...))` the helper writes, with one definition for both. Check `_coordination_doctor`'s expected-pattern check as well. Add red-first tests: after a `lanes`-topology allocation (and a review checkout), `scan_repo(...).any_blocking` is False and `require_no_sparse_checkout` passes. `git/sparse_checkout.py` is out of map, so record it.

**Issue 2: the index-only regeneration in `lanes/consolidation.py::_regenerate_snapshot_in_index` writes a wrong `status.json` (out-of-map hunk).**
It materializes in a bare `tempfile` directory that has only the events file. `materialize_snapshot` reads `meta.json` from that directory (`resolve_mission_identity`) and the existing snapshot (`_target_schema_version`). In the scratch directory these are missing, so the staged and committed `status.json` loses `mission_type`, and `mission_number` too once one is assigned. I checked this on this Mission's own log: in-place gives `mission_type: 'software-dev'`, scratch gives `''`. `notify_written` also fires with the scratch path.
On the other questions: it does not drop events. It reads the stage-0 merged log, fails closed when the log is unmerged, and the log blob is untouched. The merged log is the right source, and it uses the status-owned `reconcile_status_snapshot`, not a second writer.
Fix: materialize in a scratch Mission directory that carries the Mission's `meta.json` (from disk, or `:0:` in the index) and the same directory name. Add a test that the index-staged `status.json` is byte-identical to an in-place `reconcile_status_snapshot` of the same merged log plus `meta.json`.

**Issue 3: the gate's `_NON_LANE_WORKTREE_MODULES` allowlists two lane-checkout creators with no issue, owner or exit (Standing Order #5).**
`core/worktree.py::create_wp_workspace` (with its raw `git worktree add -b` fallback) and `core/vcs/git.py::create_workspace` create WP code-change worktrees, which are lane checkouts. They are listed as "non-lane" with "retire it", and the tooling-friction trace says "follow-up issue", but no issue was filed. The gate's docstring also says "There is NO allowlist for a lane checkout outside the seam", which is not true while these entries stand. Standing Order #5: a transient allowlist needs an issue, an owner and an exit date.
Fix: file the retirement issue and record issue, owner and exit on both entries, in a separate dead-creator set rather than the "non-lane" set. Or delete the dead creators if that is within reach. Correct the docstring either way.

**Issue 4: duplicate authority / dead code for the status exclusion.**
T047 added `coordination/workspace.py::register_lane_status_exclusion`, and the wrapper `register_lane_sparse_checkout` remains. After cc534e728c neither has a production caller; only tests and the `coordination` re-export use them. Both duplicate `lane_checkout.exclude_lane_status_files` with a different materialization step (`read-tree -mu HEAD` against `sparse-checkout reapply`). Only `reapply` is pinned as safe for a dirty local log (`test_status_exclusion_keeps_dirty_local_status_rows`).
Fix: keep one authority. Delete the `workspace.py` registrars, or make them delegate to `exclude_lane_status_files`, and repoint their tests.

## Non-blocking

- Leaving the `landed_worktrees._recreate` hint unchanged is defensible: it is an undo hint for a prune of any worktree, spec-kitty never runs it, and WP16 owns the file. But both ADR amendments (2026-07-29-1 and 2026-04-03-1) still say the helper covers "the printed recreate command". Correct the ADR text, or name the hint as the one exception.
- The gate's budget uses `process_time()`. This only affects the new gate; no existing budget changed. NFR-006 says "completes in at most 5 s", which reads as wall clock. Say in the PR that this is a deviation (measured: 1.15 s wall clock).
- The gate does not catch a shell string built by concatenation (`"git worktree add " + p`). It is a known limit; list it with the imported-constant limit.
- The flip in `test_worktree_allocator_recovery` landed in the green commit, not the red one.
