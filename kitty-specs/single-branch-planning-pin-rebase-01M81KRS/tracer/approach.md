# Tracer: approach

Mission `single-branch-planning-pin-rebase-01M81KRS`. Append during implementation; assess at close.

- 2026-11-22 WP01 cycle 1 fold, red-first evidence:
  - B1 (`test_an_explicit_refresh_clears_the_derived_marker`) and B2 (`test_minted_repin_refuses_when_the_planning_change_is_only_upstream`) both fail on WP01's pre-fold source f134aeba. The marker stayed `True`; the minted re-pin exited 0 on main's copy.
  - SC-004 (`test_repin_after_rebase_follows_planning_commit_and_keeps_the_work`, both shapes) fails on base 4a6b8cc4. Commit-to-target: `refreshed` to the tip. Minted: `PLANNING_REFRESH_FAIL_CLOSED`. On base the minted case stops at that refusal before the window assertion runs, so the window-content assertion is red-witnessed only through it.
  - The dropped `test_minted_mission_refresh_no_longer_dead_ends` passed on base: before execution begins, the minted refresh does not reach the dead end. The dead end is the post-execution path, which the parametrized minted case covers.
