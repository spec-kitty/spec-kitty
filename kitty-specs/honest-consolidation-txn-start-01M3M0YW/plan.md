# Implementation Plan: Honest consolidation transaction start + nightly integration green

**Branch**: `issue-5111-honest-consolidation-txn-start` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

This plan does three things:
- **Transaction start (#5111).** Make the start of a consolidation transaction honest: the reconciliation marker is created with the fresh `state.json`, and `clear_state` clears both.
- **Dry run (#5110).** Make `consolidate --dry-run` fail closed on coord read-path errors.
- **Integration fixtures (#5044).** Re-pin the stale `tests/integration` fixtures to the current product contracts. `test_sc007` goes to the operator for a verdict.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer, rich; `spec_kitty_events` 10.4 (the reducer used by drift E)
**Testing**: pytest with real-git fixtures, driven through the `consolidate` CLI via `typer.testing.CliRunner`
**Target Platform**: the CLI on Linux, macOS and Windows
**Constraints**: `NO_FULL_HEAVY_SUITES_IN_MISSION`; sibling slices own `ci-nightly.yml`, `nightly_escalation.py`, `tests/charter/test_consistency_check.py` and `tests/specify_cli/**`

## Charter Check

| Rule | How it is honoured |
|------|--------------------|
| ATDD / red-first (DIRECTIVE_041/034) | Both product defects were reproduced RED through the real CLI before any product edit. |
| Single canonical authority | The marker filename moves to `consolidation/state.py`, which owns the transaction record. `reconciliation.py` imports it, so no second definition exists. |
| Never quarantine or retry to green | Fixture re-pins seed real state (markers, approvals, `lanes.json`, a materialized worktree) wherever feasible. A stub is used only where the fixture fakes git, and the plan says so. |
| Complexity ≤ 15 | The forecast guard is an extracted helper, so `run_dry_run_forecast` does not grow. |

No violations, so the Complexity Tracking table is omitted.

## Project Structure

### Documentation (this mission)

```
kitty-specs/honest-consolidation-txn-start-01M3M0YW/
├── spec.md, plan.md, tasks.md, tasks/WP0*.md
└── traces/ (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
src/specify_cli/consolidation/state.py           # clear_state clears the marker; the marker filename is owned here
src/specify_cli/consolidation/reconciliation.py  # imports the marker filename
src/specify_cli/consolidation/resolve.py         # the fresh branch writes the marker before save_state
src/specify_cli/consolidation/forecast.py        # dry-run guard for coord read-path errors
tests/consolidation/test_issue_5111_*.py, test_issue_5110_*.py   # red-first CLI tests (new)
tests/integration/<12 files>                     # fixture re-pins
tests/performance?/test_merge_resume budget      # C1 re-pin (location confirmed by the scout)
```

## Implementation Concern Map

### IC-01 — Transaction-start ordering

- **Purpose**: A fresh transaction's `state.json` never exists without its reconciliation marker, and clearing the transaction clears both.
- **Relevant requirements**: FR-001, FR-002, FR-003
- **Affected surfaces**: `consolidation/state.py`, `consolidation/resolve.py`, `consolidation/reconciliation.py`
- **Sequencing/depends-on**: none. This concern lands first.
- **Risks**: A re-run after a gate failure is now a zero-progress resume, so persisted attempt-1 values (target, strategy) take precedence. The post-spec squad assesses this. Genuinely pre-fix state must still be refused (FR-012).

### IC-02 — Dry-run fail-closed

- **Purpose**: `consolidate --dry-run` renders coord read-path errors the same way the real path does, then exits 1 with valid `--json` output.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `consolidation/forecast.py`
- **Sequencing/depends-on**: none
- **Risks**: The JSON error shape must stay backwards compatible. The change only adds an `error_code` key.

### IC-03 — Integration fixture drift

- **Purpose**: Re-pin each #5044 red to its current contract and route `sc007` to the operator.
- **Relevant requirements**: FR-005, FR-006, FR-007
- **Affected surfaces**: 12 `tests/integration` files, plus the perf resume test
- **Sequencing/depends-on**: IC-01, because the C1 resume fixtures depend on marker semantics.
- **Risks**: A re-pin could turn a test vacuous. Each one keeps its load-bearing assertion, and any stub is justified in the commit message.
