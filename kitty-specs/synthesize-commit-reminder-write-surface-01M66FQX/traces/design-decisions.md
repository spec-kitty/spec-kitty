# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · Post-tasks review (reviewer-renata profile): (1) e2e regression test must commit the seeded project state before running synthesize, so promote-modified charter.yaml shows as M rather than ?? and the cleanliness assertion is meaningful; (2) resynthesize prints no commit reminder at all today — writing the record there still leaves it uncommitted; out of scope for #6631, record in PR Deferred; (3) keep warnings byte-identical through the result-shape change.
