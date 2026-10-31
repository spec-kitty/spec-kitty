# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · D1: clear the transaction record when RollbackReport says the attempt was undone (via state.clear_state), instead of re-anchoring or refusing non-resume runs; the record's pre_mutation_target_sha is only honest while attempt 1's landing is on the target.
