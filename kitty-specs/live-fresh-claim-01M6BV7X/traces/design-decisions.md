# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude:opus-5.5:python-pedro:implementer · Deliverable is a live end-to-end guard, not a production change: no src/ file is touched. DIRECTIVE_041 rules out another unit assertion (tests/status/test_actor_identity_reconciliation_4665.py already pins the projection); what no test does is run the documented CLI command against a real allocator-created lane worktree with no seeded claim.

2026-11-01 · claude:opus-5.5:python-pedro:implementer · NFR-001 amended during implement: the original 'under 60 s locally' budget is unmeasurable on this host (load average 237 on 40 cores; the SAME test measured 11.9 s and 157.3 s in consecutive runs). Replaced with an honest, checkable criterion -- no sleeps/retries/network and five real CLI invocations -- and recorded both measurements. Nothing was weakened: the module keeps one real invocation per claim attempt.

2026-11-01 · claude:opus-5.5:python-pedro:implementer · Red proof for the NEW guard, measured: with the pre-e455ce26c1 _actor_key restored in-process in BOTH binding modules (work_package_lifecycle + review_roles), the new module fails on scenario 1 with 'Error: WP WP01 is already claimed for implementation by claude:opus-5.5:python-pedro:implementer', exit 1; on the branch head the same module is 3/3 green. The guard discriminates.
