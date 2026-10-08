# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-07 · claude · Seed: core fix deletes migration/runner.py step 10 (git add -A + --no-verify retry) so schema-3 writes land through upgrade's baseline-scoped commit (capture_upgrade_baseline -> commit_touched_checkout -> safe_commit --only). Widened per maintainer to the rule 'automatic commits record exactly the paths the tool wrote': claim bundle (#5673), merge bake commit, metadata writer (#5229), rollback debris (#4763), dead sweeping helpers, a src/ gate, skill text, and safe-commit CLI path bugs (#5401/#5671/#4722) as a parallel WP.

2026-10-07 · python-pedro · Worktree commit rules: added a separate worktree_errored flag (detect/apply exceptions) instead of reusing worktree_failed, because worktree_failed also suppresses the schema stamp (WP02 territory); both suppress the worktree commit via _commit_worktree_churn.
