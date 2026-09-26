# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · Stale-entry policy split (post-spec divergence renata vs priti/debbie): hand-curated allowlists (join, kernel, os-detect) fail on stale entries; census allowlists keep documented warn-on-stale so unrelated src deletions never fail a census gate. Rationale: epic #5104 goal 'no manual re-pin toll on unrelated changes'.
