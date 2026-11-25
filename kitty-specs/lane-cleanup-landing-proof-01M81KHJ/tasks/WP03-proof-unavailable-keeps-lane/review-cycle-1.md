---
affected_files: []
cycle_number: 1
mission_slug: lane-cleanup-landing-proof-01M81KHJ
reproduction_command:
reviewed_at: '2026-11-23T23:49:36Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review, cycle 1: CHANGES REQUESTED (claude::reviewer-renata)

The reviewed lane tip is a596f0cf, on lane-c. Its base, 2c7e0031, merges lane-a b62172e7.

## Verdict

Changes requested for one blocking, operator-facing defect (finding 1). The fail-closed core is sound. Everything else is low or non-blocking.

## Blocking

1. **The rendered kept line prints `then run: None`.** The defect is at `lane_cleanup.py:159`, in `_render_result`. It formats `Remedy: {remedy}, then run: {command}` unconditionally. T013 now sets `command=None` when no worktree remains, so `spec-kitty consolidate` prints the following for every kept worktree-less lane:
   `Remedy: its worktree is gone, ...; ... delete it by hand only if its work is on main, then run: None`
   I reproduced this through the real CLI, using a coord Mission whose lane-b had no worktree (the parity probe below). The JSON envelope is correct (`"command": null`). Only the text renderer is wrong.
   - Fix: omit `, then run: ...` when `command is None`.
   - Pin it: add a render assertion, either in `test_lane_cleanup_kept_report.py::test_missing_branch_keeps_lane_tip_ref` (which already looks at the lane-c kept line) or as a unit test on `LaneCleanupReport.render_lines`. Nothing pins this today, because the new tests assert only `result.command`.

## Non-blocking (fold or record)

2. **(low) Remedy for "no tip can be named".** On this path the branch ref does not exist (`test_no_tip_to_name_keeps_the_lane` deletes it), yet the remedy says to run `git log <ref>..<branch>` and "delete it by hand". That command fails with "unknown revision". Consider wording this reason so it does not name a branch check.
3. **(low) Remedy when `landing is None`.** It renders as `git log the target branch..<branch>`, which is not a runnable command. None of the three production callers pass `landing=None`, so this only shows in tests. Either word the fallback without a command, or drop it.
4. **(nit) Parity of the kept case is not pinned.** The comment in `tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py::_build` claims "a worktree-less lane is kept on both paths alike", but the test now gives both lanes worktrees, so only the removed case is compared.
   - My probe confirms parity. With lane-a only, both paths report `[(lane-a, removed), (lane-b, kept)]`, the code is `LANDING_PROOF_UNAVAILABLE`, `command` is null, and both lane-b branches survive.
   - Consider keeping that as a second case, so the comment is backed by a test. Fold it together with finding 1.
5. **(info, for the operator at consolidation)** 2e8c9484 (the WP01 folds) and 09266f69 touch files outside WP03's `owned_files`:
   - `src/specify_cli/lanes/lane_tip.py` (docstring only)
   - the ADR
   - `tests/lanes/test_lane_tip_mission_bookkeeping.py`
   - `src/specify_cli/consolidation/lane_cleanup.py`
   - `tests/consolidation/test_lane_cleanup_kept_report.py`

   The WP03 prompt sanctions all of them as out-of-map edits. The commits are on **lane-c**, not lane-a, which still sits at its approval stamp b62172e7. So lane-a will not refuse with LANE_MOVED_AFTER_APPROVAL; the commits fall under WP03's own approval bound on lane-c. One caveat: the recorded review range pathspec (`git log 2c7e0031..a596f0cf -- tests/consolidation/test_lane_remover_proof_unavailable_7325.py`) shows only the owned file. I reviewed the full `2c7e0031..a596f0cf` diff, and the lane_tip.py change is docstring only.

## Adversarial checks that passed

- **Red-first.** At f16064dd, 4 tests fail for the right reason: the old remover returned `Removed` and deleted the branch, including the worktree-present cases. The other 2 pass as pins of unchanged behaviour (nothing-left, and PD-1).
- **Fail-closed.** `MainTodayRemover` is now reached only for `item.branch is None`. Every branch-bearing leg goes through `_proof_unavailable` and then the guard:
  - vanished worktree (or `safe_is_dir` false, or `worktree=None` from retention): kept;
  - blank `passed_sha`: kept;
  - `landing=None`: kept;
  - no tip (branch gone, no `expected_tip`, worktree present): kept;
  - nothing left: REMOVED.

  An unstattable worktree raises out of `safe_is_dir` and becomes `LANE_CLEANUP_FAILED` (kept). The "unreachable" defensive line 509 is truly unreachable, because its conditions are identical to `_guarded_removal`'s.
- **Resume.** `_lane_cleanup_report` is the only lane-deleting call. On a resume whose worktree was removed before a kill, the lane is kept: intended, and named in the WP risks. `test_abort_after_partial_cleanup_never_restores_lane_branches` still passes with worktrees added.
- **`--abort`.** It never reaches lane cleanup.
- **`mission close --discard`.** It still uses `MainTodayRemover` directly (C-003).
- **PD-1.** The retained-branch leg goes to the fallback: the worktree is removed through `guarded_worktree_remove` and the branch is never deleted. Pinned by `test_a_retained_branch_keeps_todays_worktree_removal` and the split `test_phase_cleanup_retained_branch_removes_the_worktree_through_the_guard` (`guarded_branch_delete` not called).
- **Retention.** `retain_worktrees` with a live worktree drops both legs (RETAINED_BY_POLICY, unchanged). With the worktree gone, the branch leg is kept (fail-closed, and the reason is true).
- **Re-pins.** Each re-pin reflects the new intent; none is green-washing.
  - lane-naming: the four cases now run on a real landed state with a PASS anchor at the target tip. The renamed case asserts KEPT plus the CREATED branch name, which is stronger than before.
  - coverage split: the retained-branch case plus a no-PASS-anchor case that removes nothing.
  - kept_report: adds worktrees and newly asserts that lane-c is kept.
  - orchestrator: adds a lane-b worktree and tightens the worktree assertion to both lanes.
- **Parity.** Shown by the probe in finding 4.
- **WP01 fold scope.** Matches review findings 1 to 3: the status-log exception is pinned and stated, and there are direct tests for both-sides, own-Mission scoping, the git-error path, root commit and sync-merge loss. The ADR wording is clarified.

## Evidence

- New, re-pinned and kept-report files: 112 passed. That run covered `test_lane_remover_proof_unavailable_7325`, `test_lane_cleanup_kept_report`, `test_lane_remover_guard_binding`, `test_executor_coverage` and `test_executor_lane_naming`.
- The blast-radius run was cut off at 99% by a container restart, with 0 failures or errors up to that point (xfails and skips only). It covered:
  - `tests/consolidation`, `tests/lanes`, `tests/specify_cli/lanes`, `tests/acceptance`;
  - `tests/orchestrator_api/test_consolidate_mission_lane_cleanup.py`;
  - `tests/architectural/test_destructive_op_routing.py`.
- `make test-fast`: 3222 passed, 7 skipped.
- ruff check, ruff format `--check --force-exclude` and mypy: clean on the changed files.
- diff-cover, `src/specify_cli/consolidation/*` against lane-a: 94.6%. The missing lines are 509 (unreachable) and 580 (the `"the target branch"` fallback).
