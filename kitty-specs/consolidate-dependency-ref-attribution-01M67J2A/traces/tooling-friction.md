# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · The pre-review gate runs the repo's declared review.test_command (make test-fast) unscoped with a fixed 300s budget; on this shared 20-agent host it times out, blocking every for_review transition. A WP frontmatter pre_review_test_scope cannot be used: WPMetadata sets extra=forbid and has no such field, so the WP file then reads as unreadable. Worked around with the documented per-invocation --skip-pre-review-gate plus the affected suites run directly; CI still runs the full suite.
