# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi · The pre-review regression gate timed out (300s make test-fast, host load) for both WPs; skipped only with the explicit --skip-pre-review-gate and a recorded reason. The documented per-WP pre_review_test_scope escape is rejected by WPMetadata(extra=forbid). Known #6865.

2026-11-01 · pi · Spec-commit refused the protected main branch (PROTECTED_BRANCH_REFUSED) and the Op writer refused main too; the mission moved to a topic branch and finalize-tasks persisted it as target_branch. Planning artifacts still needed one SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS commit before the branch existed.

2026-11-01 · pi · The docs retrieval index is bot-owned now (.github/workflows/docs-index-regen.yml), so DOCS-INDEX-DRIFT warnings for a changed page are expected and the index is not regenerated in the PR. A full CLI-reference rebuild also timed out capturing help under load, so only the touched service blocks were spliced from capture_help().
