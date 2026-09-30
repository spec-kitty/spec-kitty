# Tracer: design-decisions

Mission single-rollback-authority-01M3RCP4 (#5385). Seeded at planning 2026-09-30.

- DM-01M3RCPP2CR19QH3GZVPJT52BH: one mission, rollback routing + preflight (triage ruling).
- DM-01M3RCRDBS2RKWVVZH07AZ1B4M: committed done bookkeeping is rolled back with everything else; #1826 keep-done tests re-pinned.
- Preflight reuses the transaction's policy gate (extracted), not a second protection rule (research R-2).
- Wrapper re-raises original exception types; only BookkeepingPolicyRefused gets a command-layer rendering (research R-3).
- WP01: the in-phase `_restore_and_guard_coord_coherence` no longer heals (a forward `git revert` would commit inside the span and move the coordination branch off its recorded post tip); the heal runs only at resume start in the driver (AST-pinned).
- WP01: the #2786 successor trigger is another actor's commit on the coordination branch: the door reports it NOT restored, keeps the record and the strand marker, and the resume heal reconciles.
- WP01: `--abort` repro residue comes from a hard-kill wrapper (`_report_rollback` -> `os._exit(137)`), the only way a real run still leaves residue; the killed run's own global lock is released in the foreign-lock case.
- WP02: the transaction's step-4 gate is `_preflight_policy_verdict` and the coordination arm's caller-ref verdict is `_caller_ref_refusal`; `_acquire_locked` and the lock-free `BookkeepingTransaction.preflight_refusal` both call them (C-001). An equivalence test pins probe == acquire on the same fixture.
- WP02: in the coordination arm the probe treats `DESTINATION_REF_NOT_FOUND` for the coordination branch as no refusal: `acquire` materializes the branch before its gate runs. Found by the blast radius (DESTINATION_REF_NOT_FOUND refusals on coord fixtures without a coord branch).
- WP02: the preflight probes only when a `done` write is pending (lane WPs minus canceled-with-provenance, current lane not `done`); an unreadable status surface counts every WP pending (fail toward probing).
- WP02: a flat mission on protected `main` is now refused by `--dry-run` too; `test_flat_topology_forecast_is_noop` (about the lanes.json surface) sets the hatch.
- Pre-PR fold (correction to the WP02 `DESTINATION_REF_NOT_FOUND` bullet above): `acquire` does NOT materialize a missing coordination branch; it fails closed with `BookkeepingWorktreeMissing` while resolving the coordination worktree, before its gate. The probe's `None` is still right (that failure is not a policy refusal); only the stated reason was wrong. Docstrings corrected.
- Pre-PR fold: the orchestrator-api `consolidate-mission` path (`_execute_lane_merge`, and its planning-only closeout under a captured console) runs the same `refuse_protected_status_target` preflight before any gate or merge; a refused `--resume` (merge record present) points at `consolidate --abort` instead of claiming no branch moved.

## Development-assist test cleanup (fold-or-keep, `development-assist-test-cleanup` procedure)

| File | Verdict | Reason |
|------|---------|--------|
| `tests/terminus/test_repro_5385_rollback_door.py` -> `tests/terminus/test_rollback_door.py` | KEEP, renamed | Real-git acceptance test of a live contract (every post-mutation exit restores target + mission branch via the door, record truthful, re-run lands). Not inert after the fix and not duplicated by the AST pin or the in-process wiring tests (those do not exercise real per-phase mutation). `regression` marker dropped (ADR 2026-07-17-1: repros are converted once fixed); `test_5385_` prefixes and WP/NFR/SC/US labels stripped. |
| `tests/terminus/test_repro_5385_protected_target.py` -> `tests/terminus/test_protected_target_preflight.py` | KEEP, renamed | Real-CLI acceptance test of the up-front refusal plus its controls (hatch, empty protection, coord, commit_to_target, all-done, `--target` laundering, `--resume` hint). The unit seam tests mock the policy, so this is the only end-to-end proof. Same marker/label treatment. |
| `tests/consolidation/test_executor_rollback_wiring.py` | KEEP as is | Predates this mission (#5318 slice); this mission added door/interrupt cases that guard live behaviour. Out of this procedure's scope for renaming (pre-existing file). |
| `tests/specify_cli/coordination/test_transaction_preflight_refusal.py` | KEEP as is | New in this mission, already behaviour-named with no WP/NFR labels; pins probe == acquire equivalence (C-001), a standing contract. |
| `tests/consolidation/test_single_rollback_authority.py` | KEEP as is | Pre-existing standing architectural gate; this mission extended it. |

Historical planning records (`lanes.json` write scopes, `tasks/WP01-*.md`, `tasks/WP02-*.md`) keep the old paths: they describe what those WPs owned at the time.
