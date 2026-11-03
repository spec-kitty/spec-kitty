# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · Implemented the issue's option 1 only. A failed evidence diff is classified: branch_ref_absent (renamed public from _branch_ref_absent so move-task applies #6780's exit-1-only rule), lane_branches_absent_locally (a local fact, never a history), and absent_lane_window_cause, asked once per failed lane window and shared by move-task and accept/consolidate. Option 2 (judging a lanes Mission on planning_commit..target_branch) is a policy change left to the operator on #7120.
