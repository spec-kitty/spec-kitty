# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Not fixed here: the gate still scopes off a workspace diff, so a planning-lane WP's commit is never inspected (#2741's larger scope). #6792 only asks the recorded reason to stop contradicting the commit; touching scope selection would change gate policy and could start running tests on a planning lane.
