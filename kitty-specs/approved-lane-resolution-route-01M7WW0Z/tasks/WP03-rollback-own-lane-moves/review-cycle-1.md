---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T19:06:43Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review cycle 1 (lane-c 1e6a09ba33): REJECT (one MED)
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Verified
- The restore is a compare-and-swap (after -> before) and uses only the lane's restore target. post_mutation_refs never makes a lane restorable.
- A dirty checkout refuses before any ref moves. This was probed on every checkout of the lane, including a second worktree on the same branch.
- The restore goes through restore_branch_ref (resync_checkouts=True). No raw reset is used. The destructive_op_routing and single_rollback_authority gates are green.
- A lane that has moved is never reset, and its record is kept. The output contains no reset or --force text.
- On restore, WP02's record is deleted. If that cleanup fails, the result is still RESTORED and the leftover residue is named.
- The resume target is kept only while the lane is still at its own `after`. The re-baseline keep rule is correct, and adding LANE_MISSING to it is sensible.
- An interrupted rollback that is re-run is idempotent (ALREADY_AT_SNAPSHOT).

## Must fix
1. (MED) The destructive restore trusts unvalidated state.
   - Where: _own_lane_move (~:1056-1069) and _rollback_lane. Nothing checks that `after` really is the auto-rebase merge of `before`.
   - Repro:
     1. Put the lane at `before`.
     2. Commit reviewed-work-after-snapshot (a non-merge).
     3. Set lane_rebase_moves[lane] = [before, live].
     4. Run rollback_to_snapshot.
     Result: RESTORED, and the lane is rewound past the reviewed commit. That commit is now reachable only through the reflog.
   - Fix (fail closed): restore only when both of these hold:
     - `after` is a 2-parent merge whose first parent is `before` (commit_parents);
     - auto_rebase_record.is_recorded(repo, branch, after) is True. An AutoRebaseRecordError counts as not restorable.
     Otherwise report the lane only: UNCHANGED_BY_RUN, or a named NOT_RESTORED reason.
   - Test: add the repro. The lane must be reported, not moved, and the commit must be kept.

## Design decisions
1. Accepted: LANE_MOVED_SINCE_AUTO_REBASE counts as OK for fully_restored, but it is not re-baselineable, so the record stays.
2. Accepted as a residual for WP13: an interrupted rollback can leave a stale entry. A second --abort drops the entry (ALREADY_AT_SNAPSHOT), and the case where cleanup keeps the lane fails closed.

## For WP13
CLAUDE.md still says lanes are "report-only: snapshotted, never recorded, never restored". Document the FR-009 exception: the run's own recorded, validated auto-rebase move.

## Evidence
- Red-first (new file + test_rollback_authority against c5b1be72c3): 17 failed, 1 passed, 3 errors. test_rollback_authority fails at collection with AttributeError on LANE_MOVED_SINCE_AUTO_REBASE. The history records "1 failed, 4 passed" for this run, which was measured differently; correct the history.
- tests/consolidation: 3687 passed.
- terminus/lanes subset: 172 passed.
- arch gates: 195 passed.
- ruff, C901, format, mypy: clean.
