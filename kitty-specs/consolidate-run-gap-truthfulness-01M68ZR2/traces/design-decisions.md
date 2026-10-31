# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · The tombstone commit reuses commit_merge_bookkeeping (the one sanctioned protected-flow seam) instead of a new guarded call site; the path set is filtered to contexts that were tracked before the run, so safe_commit never has to add a file that is not in the index.

2026-10-31 · reviewer-renata · Review round 1 (WP01): found that _phase_push runs before teardown, so a --push consolidation would have left the new tombstone commit local-only. Fixed in-round by re-using _phase_push after the tombstone commit (one push implementation, no duplication).

2026-10-31 · reviewer-renata · Review round 1 (WP02/WP03): both message fixes are additive — the flat-topology accept sentence and the missing/in-mission verdict remedy are pinned by positive-control tests, and no gate verdict or blocking mode changed (tests/policy 220 passed, agent CLI 285 passed).
