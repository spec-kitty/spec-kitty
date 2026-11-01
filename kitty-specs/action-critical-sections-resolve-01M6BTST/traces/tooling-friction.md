# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The for_review pre-review gate cannot pass in this repo (#6865): derived scope is empty so it runs the configured 'make test-fast' against a 300s budget, and the frontmatter pre_review_test_scope recovery is rejected by WPMetadata (extra_forbidden). Both WP moves used --skip-pre-review-gate with the affected surfaces run manually.
