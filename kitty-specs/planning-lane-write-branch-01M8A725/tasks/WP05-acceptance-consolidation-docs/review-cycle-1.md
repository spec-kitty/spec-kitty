---
affected_files: []
cycle_number: 1
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T07:07:28Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 1 (reviewer-renata): changes requested

## Issue 1 (blocking, fail-open): an empty planning `write_scope` walks the whole Mission branch unscoped

`src/specify_cli/consolidation/reconciliation_authorship.py`, `_lane_walk_range` (returns `tuple(lane.write_scope)`), with `_collect_authored` (`if scope:` filter) and `_scoped_walk` (`if not scope: return walk`).

The scope is used both as "no scoping wanted" (code lanes, `single_branch` window: `()`) and as "scope to these owned paths" (the new Mission-branch window). When the planning lane's `write_scope` is empty, the two cases look the same, so the Mission-branch window `<planning pin>..<coordination base>` is walked **unscoped**. Every commit on the Mission branch in that range then counts as approved planning authorship: status files, stray commits and any code path someone committed in the coordination worktree.

This is reachable. `lane-planning`'s `write_scope` is the union of its planning WPs' `owned_files` (`lanes/compute.py::_build_planning_lane`). `finalize-tasks` accepts an explicit `owned_files: []` for a `planning_artifact` WP (`mission_finalize_bootstrap.py:223-232` refuses only for `code_change`). Such a WP is lifted past `IMPLEMENTATION_MISSING` with `--attest-no-implementation`, which is the documented route for a WP that owes no implementation. After that, a stray `src/...` commit on the Mission branch passes the squash blob-attribution axis and lands. Before this change, the planning lane walked `coord_base..<target>` and authored nothing, so the gate failed that path.

I reproduced it with a scratch test (not committed) built on `test_planning_lane_authorship_7860._mission`, using `ExecutionLane(PLANNING_LANE_ID, ("WP02",), (), (), (), 0)` and `_reader(True)`:

```
claim.blobs paths == ['curation/apply_curation.py', 'kitty-specs/auth-01M8EEEE/status.events.jsonl', 'sneaky.py', 'stray.py']
```

The module docstring of `test_planning_lane_authorship_7860.py` says "Mission-branch status and stray commits never read as approved planning authorship". With an empty scope that is false.

**Fix:** keep "no scope" and "empty scope" apart. For example, `_planning_lane_mission_branch_window` returns `None` when `lane.write_scope` is empty, so the lane keeps today's range and authors nothing. Or the walk carries an explicit `scoped: bool`/`Optional` scope, and an empty scoped walk yields no commits. Add a unit test for the empty-`write_scope` planning lane that asserts `stray.py`, `sneaky.py` and the status path are absent from `claim.blobs` (red on the current code, as above). Also add a sentence to the `_lane_walk_range` docstring.

## Notes (no action needed)

- `approved_attestation.py` is unchanged, correctly: `_bound_lanes` excludes planning lanes, so the attestation never walks the planning branch.
- mypy reports `reconciliation_authorship.py:134 no-any-return`. That line comes from 9dcf5f48, before this WP, so it is not caused by WP05.
- The out-of-owned-files paths (`mission_runtime/__init__.py`, `wp_evidence.py`, `_read_path_resolver.py`, `docs/migrations/README.md`, `test_mission_runtime_surface.py`, `test_planning_lane_authorship_7860.py`) are consistent with the prompt's T022/T023 and the WP04 review carry-over. Please list them in the history note when you rework.
