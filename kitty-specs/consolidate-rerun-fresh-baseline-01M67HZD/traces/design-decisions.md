# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · D1: clear the transaction record when RollbackReport says the attempt was undone (via state.clear_state), instead of re-anchoring or refusing non-resume runs; the record's pre_mutation_target_sha is only honest while attempt 1's landing is on the target.

2026-10-31 · python-pedro · D1b after aggregate review: field-scoped re-baseline, not record deletion. Dropping the whole record broke the #5051 claim anchor (a re-run false-FAILed with an empty authorship set) and 11 resume-after-rollback tests. The window-base hazard is closed by dropping only the attempt geometry.
