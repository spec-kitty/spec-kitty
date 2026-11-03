# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi · The cause of an unreadable tracked meta.json travels as data on TrackedMeta (repository/ownership/objects) instead of being re-parsed from git stderr in the notice module: the classifier is already the one place that knows, and a second stderr parser is how this defect class recurs.
