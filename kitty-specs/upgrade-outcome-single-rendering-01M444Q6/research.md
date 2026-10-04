# Research: Upgrade reports one outcome

All findings were verified on `main` at `9adc68803f` by the pre-spec grounding squad (a reproduction lens and a scope lens) unless marked as an inference.

## R1 — Where the exit code and the messages come from

- **Decision**: extend `UpgradeOutcome`; do not add a new type.
- **Rationale**: `derive_exit_code()` is called once (`upgrade/finalize.py`) and its result raised once (`cli/commands/upgrade.py`). The error list is built by `_combined_errors(outcome, summary)` in the CLI module, with the surface summary passed through `_FinalizerRenderContext`. `_display_no_migrations_results` prints `Project is already up to date!` unconditionally and prints `result.warnings`, `activation_errors` and `result.errors`, never the drift message.
- **Alternatives considered**: a print added to the no-migrations renderer (fixes the instance, keeps two error-list builders and the unconditional success line); a new `UpgradeReport` wrapper around the outcome (a second authority).

## R2 — What `surface_drift_failed` means today

- **Decision**: replace it with `drifted_paths` and `surface_repair_failed`.
- **Rationale**: it is true for consent-required drift, for a repair result that is neither `applied` nor `skipped`, and for an incomplete dry-run preview. The renderer words all three as drift, which yields `drift in 0 file(s)`.
- **Alternatives considered**: keep the boolean and guard the message on a non-zero count (hides the repair failure instead of naming it).

## R3 — Is non-zero on drift intended?

- **Decision**: keep it; record the open operator decision in the spec and the ADR.
- **Rationale**: pinned by FR-006 of mission `agent-profile-projection-plugin-production-01KV3NGS`, by `tests/specify_cli/tool_surface/test_drift_policy.py`, by the changelog entries for the earlier exit-honesty fix and the Windows drift mission, and restated in the code. No ADR rules on it.
- **Alternatives considered**: exit 0 with a warning on a no-migrations run (what the reporter first expected; reverses the pinned contract).

## R4 — Is the legacy surface-repair branch reachable?

- **Decision**: verify with a test, then remove.
- **Rationale (inference from code reading)**: the fallback runs only when `ctx.prepared_repairs is None` on a real successful run; preparation either sets it or returns errors that skip the step.
- **Alternatives considered**: leave it and route it through the new report type (keeps dead code and the tests that patch it).

## R5 — Collision with neighbouring work

- **Decision**: own `upgrade/outcome.py`, `upgrade/finalize.py` and the renderers in `cli/commands/upgrade.py`; leave `upgrade/runner.py` and `upgrade/assessment.py` alone.
- **Rationale**: the sibling mission for per-worktree metadata writes works in `runner.py`; an open pull request touches `assessment.py` and the managed-skills provider.

## R6 — Supply chain

No dependency is added, upgraded or removed. DIRECTIVE_051 controls: not applicable.
