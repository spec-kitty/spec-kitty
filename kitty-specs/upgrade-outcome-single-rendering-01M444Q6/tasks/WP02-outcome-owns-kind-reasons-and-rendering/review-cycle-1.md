---
affected_files: []
cycle_number: 1
mission_slug: upgrade-outcome-single-rendering-01M444Q6
reproduction_command:
reviewed_at: '2026-10-04T20:23:46Z'
reviewer_agent: claude-reviewer
wp_id: WP02
---

# WP02 review cycle 1: REJECT (one blocking finding)

## Blocking

**B1. The mission-state repair gate now runs after a failed commit recovery.**
`_finalizer_step_offer_repair` in `src/specify_cli/cli/commands/upgrade.py` still skips the gate on `not outcome.result.success`. `_finalizer_step_commit_churn` no longer flips `result.success` on `SafeCommitRecoveryFailed` (it sets `commit_recovery_failed`), so the gate is now offered, and under `--yes` executed, in a checkout whose staging restore just failed. Before this WP it was not invoked.

Fix: skip the gate when `outcome.commit_recovery_failed` as well; update the docstring; add a test, through the finalizer wiring, asserting the gate is not called after a recovery failure (and still is called on a clean run).

## Non-blocking, fold in the same pass

**N1.** `UpgradeOutcome.errors()` adds its generic fallback only when the whole list is empty. T005 step 6 asks for it whenever a `surface_repair_failed` or `preview_incomplete` reason has no message of its own, even if another message (for example the drift line) is present. Make the fallback per reason, and add the unit row (repair failed + one drifted path → both a repair line and the drift line).

## Verified and sound

Red→green at the repro commit; golden outputs unchanged; single authority holds under three mutations; contract rows; no JSON key removed; constraints. 414 passed on the 13 named files; ruff, C901, format and mypy clean.
