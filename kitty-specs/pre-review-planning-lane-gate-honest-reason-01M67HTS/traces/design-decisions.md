# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Not fixed here: the gate still scopes off a workspace diff, so a planning-lane WP's commit is never inspected (#2741's larger scope). #6792 only asks the recorded reason to stop contradicting the commit; touching scope selection would change gate policy and could start running tests on a planning lane.

2026-10-31 · python-pedro · Development-assist test verdict: the mission added exactly one test module (test_tasks_move_task_pre_review_planning_lane_reason.py) and it is KEPT as a regression test for the real contract: the pre-review gate's empty-diff reason selection. It drives the production move-task entry point on a real git repo, contains no WP##/NFR label, and asserts observable behaviour (verdict reason, dispatch spy, transition applied), not module shape. No retire/split needed; nothing filed for the suite-wide audit because no characterization or parity scaffolding was created.
