# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · planner-priti · Reproduced #6844 live on main @ 35318ef5 before specifying: the only changed input between MANAGED_LANE and legacy_user_sparse_checkout was the root checkout's branch. Fix therefore targets the policy SOURCE (_load_managed_lane_policies), not the classifier rail.

2026-10-31 · planner-priti · One work package, five sequential subtasks: red tests, preflight+fail-closed controls, fix, doctor pinning, validation. single_branch topology (no lane worktrees) because the change is one module plus its test suite.

2026-10-31 · implementer-ivan · Half-by-half proof ran: stashing only src/specify_cli/git/sparse_checkout.py (fix reverted, tests kept) turns 4 of the 5 new assertions red — the branch-switched scan verdict, the implement preflight, the drift control's UNKNOWN kind and the doctor clean-surface assertion — while the two fail-closed ratchets stay green. Restored; 21/21 in the two changed suites.
