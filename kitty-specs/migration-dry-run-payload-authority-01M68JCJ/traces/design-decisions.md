# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Null policy pinned to the 3.0.0 transport fixture plus the real row: keep explicit nulls for reason/review_ref/evidence; mission_id present iff set; summary never produced locally.

2026-10-31 · reviewer-renata · Aggregate-diff review (mission level): LAND. Non-vacuity proven by replaying the red-first commits in a detached worktree — tests/status/test_wire_payload.py fails at 23af798866 (module absent) and all 5 tests/migration parity tests fail at 85a2a7cdeb (pre-fix call site); the count-only-synthesized-envelopes fix was reverted alone and turned the rejection test red. History is NOT regrouped: lanes.json pins planning_commit_sha 63dbdfdee5 as the #6715/#5939 evidence-window base that accept/consolidate diff from, and rewriting it would make the window uncomputable (the #6801 failure class); the sanctioned regroup is a landing-pass step where the operator re-pins it.
