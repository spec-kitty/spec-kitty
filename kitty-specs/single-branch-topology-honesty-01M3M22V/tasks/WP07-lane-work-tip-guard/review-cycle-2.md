---
affected_files: []
cycle_number: 2
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-29T04:56:18Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review feedback, cycle 2 (reviewer-renata)

**Verdict: changes requested.** Both cycle-1 items are fixed. One `record_tip` call site is still untested, and two record points that T032 requires were never implemented.

## Call-site classification

I grepped every `record_tip(` call in `src/` on c5682566. Each "remove the call" mutation was run in a throwaway worktree over the #5115 file, `test_issue_5115_record_points`, `test_lane_tip`, `test_lane_tip_recorder` (not timing), `test_claim_base`, the #4889 guard file and `test_issue_4889_caller_independence`. The baseline is 77 passed.

| Call site | Mutation result | Class |
|---|---|---|
| `tasks_move_task.py:959` (for_review auto-commit) | red: `test_for_review_auto_commit_records_tip_despite_foreign_hook` | (a) tested |
| `auto_rebase.py:926` | red: `test_auto_rebase_commit_records_tip_despite_foreign_hook` | (a) tested |
| `implement_support.py:544` (self-heal re-entry) | red: `test_reenter_self_heal_records_tip_despite_foreign_hook` | (a) tested |
| `worktree_allocator.py:1066` (REUSE) | red: `test_live_branch_backfills_tip` | (a) tested |
| `worktree_allocator.py:1254` (FRESH) | red: `test_tip_equals_base_reopens` and `test_reopen_after_merge_no_false_refusal` | (a) tested |
| `worktree_allocator.py:1131` (CRASH_RECOVERY) | **green: 77 passed** | **(c) untested, load-bearing** |
| `_merge_recorded_planning_commit` / `_merge_dependency_lane_tips` | no own call; the allocator route calls that run right after them on the same path cover them | (b) covered by the FRESH, REUSE and CRASH calls |
| for_review transitions `agent/status.py:~276`, `orchestrator_api/commands.py:~1755` | **not implemented** (no `record_tip` in either file) | **missing (T032)** |

## Blocking

**Issue 1: the CRASH_RECOVERY `record_tip` (`worktree_allocator.py:1131`) is untested.**

- It is the backfill-on-touch for a lane whose branch survived but whose worktree directory was lost (FR-021).
- Without it, a lane that predates tip recording, or one whose tip went stale under a foreign hook, keeps no tip or a stale one. If its branch is later deleted, the guard either fails closed (`LANE_WORK_TIP_UNKNOWN`) or, with a stale tip that equals the base, **fails open**: it reads as absorbed and the lane is re-cut empty.
- **Required fix.** Add a test that deletes only the worktree directory, keeps the branch, adds a commit on the branch (foreign hook, or no hook), and runs implement. Assert that `read_tip == branch HEAD`. The mutation must go red.

**Issue 2: the T032 record points "the for_review transitions (`agent/status.py:276`, `orchestrator_api/commands.py:1755`)" were never implemented.**

- **Why this matters when the hook cannot record.** If a foreign hook occupies the slot (C-010 skip), the operator's own lane commits are never recorded. The tip then stays at the FRESH fork point, which equals the base.
- `move-task --to for_review` records only when its auto-commit actually commits.
- So a WP moved to for_review through `agent status emit` or the orchestrator `transition`, whose lane is later destroyed, reads `tip == base`. That counts as absorbed, and the lane is re-cut over the stranded work: exactly the #5115 failure mode.
- **Required fix, either:**
  - record the lane tip, if the lane branch exists, on the for_review transition in both surfaces (and in move-task even when nothing was auto-committed), with a foreign-hook test each; or
  - document in the WP Activity Log and the PR why these were dropped, and file a follow-up issue. Given the fail-open analysis above, I recommend implementing them.

## Verified (cycle-1 items resolved)

- **M5** (`AbsorptionUnsupported` → proceed) is now caught by `test_absorption_unsupported_refuses_at_the_guard`.
- **M2, M3 and M4** are each caught by a dedicated record-point test.
- **The foreign-hook fixture is real.** `_install_foreign_post_commit_hook` writes a foreign hook and then calls the real `install_lane_tip_recorder`. It asserts `post-commit` is not among the installed slots and that the foreign bytes survive. The self-heal test also asserts `read_tip is None` before the touch.
- **The live-branch backfill nit is fixed.** The test asserts through `read_tip`.
- **Tests.** Baseline 77 passed across the named files (`-m "not timing"`, empty `GIT_CONFIG_GLOBAL`).
