# Approach — honest-consolidation-txn-start

Initial approach:
- Reproduce #5111 and #5110 red-first through the real `spec-kitty consolidate` typer command, reusing the #4764 real-git coord harness.
- Fix the transaction-start ordering.
- Guard the dry-run forecast.
- Then triage the #5044 integration reds per DIRECTIVE_041, using a read-only scout for the per-test evidence.

- 2026-09-28 — The red-first CLI repros were built before the spec, as pre-spec evidence. Both reproduced on `af847be7`: the #5111 re-run was refused as pre-fix, and the #5110 dry run raised `CoordinationWorktreeUnmaterialized`.
- 2026-09-28 — The post-spec squad (reviewer-renata) showed that the brief's "marker with fresh state" design alone turns every gate failure into a zero-progress auto-resume. The persisted target, strategy and push would then silently win over the re-run's flags. The approach widened to a pre-mutation clear wrapper, which generalises the #4764 clear, and WP01 ownership was widened to `executor.py` and `workspace.py`.
- 2026-09-28 — Phase-order gates (`test_executor_phase_boundary`, `test_reconciliation`) inspect the driver's source text. Extracting the phases into a helper broke them, so the wrapper became a context manager and the phase calls stayed inline. The gates were left untouched.
- 2026-09-28 — A read-only scout proved each #5044 re-pin in scratch copies before any lane edit. The scout's findings corrected the #5045 map in two places. Drift B is now a teardown-gate REFUSE, not a MagicMock `TypeError`. The planning-lane test hits a `LaneNamingSlugMismatch`.
- 2026-09-28 — The sc007 operator verdict was "stale" (stijn-dejongh). It was re-pinned to the #4899 feedback contract.
