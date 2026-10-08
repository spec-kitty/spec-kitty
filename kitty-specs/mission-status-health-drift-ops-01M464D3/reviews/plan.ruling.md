# Plan phase operator rulings (2026-10-06, plan round)

These replace the acceptance bar for the findings named. They are binding and not re-opened.

1. PLAN-GOV-001: option A. Keep the plan's behaviour. Reword Departs 5 as an explicit departure, and edit AC-REALITY 2, AC-REALITY 3 and the FR-025 sentence in `spec.md` so that offline skips only the resolver-dependent assertions. The Ops walk, the `skippedCount` equality and the read-only fingerprint still run offline.
2. PLAN-ARCH-002: option (a). Pre-check the YAML shape in the reader, and treat a residual `AttributeError` or `TypeError` from `load` as null. The spec wording ("read as load reads it") stays.
3. PLAN-VERIFY-003: option A. The D-0 sync, the baseline and the synced environment become an orchestrator step before any dispatch; IC-01 keeps the re-measurements and the campsite. The IC-01/IC-02 parallel window stays.
4. PLAN-VERIFY-004: the preferred option. AC-DRIFT row 19 and the AC-CROSS 4 corpus-sized cases move into `test_mission_status_reality.py`, with a discovered-count guard.
5. PLAN-VERIFY-005: option B. Restore the procedure order for dev-assist and the verdict; the terminal #5776 verdict comes after the squad. Only the consolidate-before-squad departure stays in Departs 11.
6. PLAN-VERIFY-006: min-of-repeats. Each timing shape is timed as the minimum of at least 5 in-test repeats, the control timed the same way, the planted quadratic mutation still failing.
7. PD-2 is acknowledged: the widened registration file set is approved. Record it; `SLICE_ALLOWED` lists every such file.

# Plan round 3 operator rulings (2026-10-06)

8. PLAN-FRESH3-001: accept the recommendation. The proxy escalation threshold in D-P5 and IC-01 moves to about 70 s local (the 120 s ruled bound divided by the 1.7 local-to-CI factor); the W-7 pass rule stays the final arbiter.
9. PLAN-FRESH3-003: accept the recommendation. The `cache-the-result` mutation is added to the AC-CROSS 4 row and to IC-09 Red-first, so the real 5 s listing case is covered.
10. PLAN-FRESH3-002: single remedy. D-P5 says the combined case and the job gain are different quantities (the completion equality and the listing repeats sit in the job gain only) and makes the W-7 pass rule the arbiter.

# Orchestrator note (plan round 5, 2026-10-06; within ruling 8, not a new ruling)

11. PLAN-FRESH4-001: ruling 8 stands. The 70 s figure (120 s divided by 1.7) bounds the whole local job-gain proxy; D-P5 and IC-01 state the escalation line against the sum of the combined case and the 10 to 15 s the job gain adds, so the combined case alone escalates at about 55 s local. The two options of the finding are the same rule, so no new operator decision arises.
