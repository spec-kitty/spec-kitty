# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · Stale-entry policy split (post-spec divergence renata vs priti/debbie): hand-curated allowlists (join, kernel, os-detect) fail on stale entries; census allowlists keep documented warn-on-stale so unrelated src deletions never fail a census gate. Rationale: epic #5104 goal 'no manual re-pin toll on unrelated changes'.

2026-09-26 · claude · Post-spec squad folded: FR-003 exemption list pinned empty by frozenset equality; FR-011 'enforced' = consumed by a comparison that fails when live exceeds the leaf; exemptions counted per site; 6 os-detect path:line pins added (94 total); #3962 folded into FR-010; widened predicate lives in the ban test module (C-005).
