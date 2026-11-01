# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Pre-review move-task gate: review.test_command is 'make test-fast', so the derived scope targets are appended to a make invocation and never narrow the run; it exceeds the 300s budget and blocks the transition on every WP. The documented recovery (pre_review_test_scope in WP frontmatter) is rejected by WPMetadata as an extra field. Both are #6865; worked around with --skip-pre-review-gate plus the equivalent scoped suites run by hand.
