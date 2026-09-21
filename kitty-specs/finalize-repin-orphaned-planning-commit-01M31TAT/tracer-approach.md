# Tracer: Approach — Finalize re-pins an orphaned planning_commit_sha (#4827)

Seed at planning; append during implement.

- **ATDD red-first (ADR 2026-07-17-1)**: two issue-pinned `@pytest.mark.regression` repros written failing against the pre-fix entry points BEFORE the fix — (1) finalize side: plain run preserves the orphan / `--refresh-planning-commit` refuses; (2) consumer side: allocator emits the generic conflict for an orphaned pin. After the fix, transitional repros become focused unit/integration tests, never left marked `regression`.
- **Single-authority discipline**: orphan DETECTION centralized in the shared `_merge_recorded_planning_commit` helper; finalize stays the sole WRITER (C-001). No second re-pin site.
- **Classification keyed off the target-branch tip** (not lane HEAD) — the load-bearing correction from the regression lens (HIGH-1).
- **Fail-closed but degrade-safe**: default fails closed only on a proven orphan against a capturable tip; non-git/foreign/uncapturable degrade to the historical preserve (protects the #3311 non-git test).
- **Per-commit greenness**: WP01 (classifier) lands first as the foundation; corrected-expectation test edits land in the same WP that changes the behavior they assert, so no intermediate commit is red on a gate.
- **Surface parity in the same PR**: golden-contract frozenset, envelope 1.6.0, CLI-ref regen, CHANGELOG — all folded so no gate reds on a partial surface.

## Implement log
- (append per WP)
