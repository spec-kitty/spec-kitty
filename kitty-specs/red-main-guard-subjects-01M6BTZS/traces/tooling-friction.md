# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The pre-review gate's 300 s budget timed out twice on WP01's for_review move (observed 300 s and 308 s) with the auto-scope resolving to no explicit targets, so it ran `make test-fast` unbounded under batch host load. This is the operator-recorded item in OPERATOR-DECISIONS.md #5, tracked by #6865. Resolution: declare a bounded `pre_review_test_scope` in each WP's frontmatter (the documented FR-004 per-WP override) so the gate still runs and diffs a baseline, scoped to the tests that cover the WP, rather than opting the gate out with --skip-pre-review-gate.
