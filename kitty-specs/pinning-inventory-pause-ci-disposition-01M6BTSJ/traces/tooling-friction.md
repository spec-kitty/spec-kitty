# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · The pre-review regression gate refused the WP01 for_review transition twice with 'scoped test run timed out after 300s' (monotonic observed elapsed 300.009s), reporting 'normalized targets: (empty)' — the census auto-scope resolves no pytest targets for a WP whose write scope is scripts/ci/derive_pinning_inventory.py plus tests/release/pinning_rule_inventory.json, so the gate falls back to the repo-wide review.test_command (make test-fast) and cannot finish inside the fixed 300s budget on this shared host. The documented scope override cannot be used: setting pre_review_test_scope in WP frontmatter makes the WP unreadable because WPMetadata is extra=forbid (same finding recorded in kitty-specs/consolidate-dependency-ref-attribution-01M67J2A/traces/tooling-friction.md; operator decision tracked by #6865). Used the documented per-invocation --skip-pre-review-gate instead, after running the affected suites directly: tests/release/test_pinning_inventory_fresh.py (8 passed, SPEC_KITTY_STRICT_PINNING_INVENTORY=1) and tests/ci/test_pause_ci_label.py (7 passed). CI still runs the full suite.
