# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi:python-pedro · Provision before the fixture's Initial commit so the activation ledger lands in that first commit and the fixture's commit shape (asserted by existing nodes) is unchanged. Pin on the absence of the fallback log record, not the code_producing boolean, because the boolean is True both before and after the fix (no-op passable otherwise).
