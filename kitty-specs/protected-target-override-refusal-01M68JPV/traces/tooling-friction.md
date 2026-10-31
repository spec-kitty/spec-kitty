# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · move-task --to for_review ran the pre-review regression gate (make test-fast, 300s budget) and reported 'timed_out' with 'budget classification unknown; normalized targets: (empty)'. Host load average 145 on 20 cores (20 parallel agents); the gate produced no verdict on this diff. Recorded with SPEC_KITTY_SKIP_PRE_REVIEW_GATE plus the scoped suites run by hand (tests/terminus/test_protected_target_preflight.py, tests/orchestrator_api/test_consolidate_mission_protected_target.py). A timeout should classify as an environment failure, not 'unknown'.
