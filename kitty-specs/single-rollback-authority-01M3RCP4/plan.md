# Implementation Plan: Every post-mutation consolidate exit rolls back through one authority

**Branch**: `claude/5385-single-rollback-authority-qqt180` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/single-rollback-authority-01M3RCP4/spec.md`

Planning questions were answered from the operator's triage ruling on #5385 and the two specify Decision Moments; the one planning fork (how the preflight reuses the protection authority) is recorded in [research.md](research.md) R-2.

## Summary

`spec-kitty consolidate` gets one rollback door for its whole post-mutation span. The driver `_run_lane_based_consolidation_locked` wraps every call from `_phase_merge_lanes` (the first mutation) through `_phase_reconcile_before_teardown` (the gate) in one `try`. A non-zero `typer.Exit`, any other exception, or an interrupt calls `_report_rollback`, which calls the existing CAS authority `rollback.rollback_to_snapshot`, then re-raises the original. The revert-based per-phase rollbacks (`_reset_coord_to_checkpoint`, `_revert_coord_done_commit`, `_rollback_to_pre_mutation_checkpoint`, `_revert_orphan_target_bake_commit`) are deleted; working-tree byte restores and the strand marker stay. Separately, a pre-lock preflight asks the bookkeeping transaction's own policy gate whether the done write would be refused on the mission's status write target and refuses before any mutation; `--dry-run` reports the same code; a `BookkeepingPolicyRefused` that still escapes renders as a readable error at the command layer.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git (subprocess); existing `specify_cli.consolidation`, `specify_cli.coordination`, `specify_cli.git.protection_policy`
**Storage**: git refs and the consolidation record `.kittify/runtime/merge/<mission_id>/state.json` (unchanged schema)
**Testing**: pytest over real temporary git repositories (`tests/terminus/` real-CLI repros, `tests/consolidation/` unit and AST pin); red-first regression repros per ADR 2026-07-17-1, converted to focused tests at close
**Target Platform**: Linux, macOS, Windows (git 2.38+ for squash attribution, unchanged)
**Project Type**: single (CLI package under `src/`)
**Performance Goals**: preflight adds at most one policy evaluation (read-only `git rev-parse` probes) per consolidate run; rollback cost unchanged
**Constraints**: complexity ≤ 15 per function; ruff, ruff format and mypy clean; no new suppressions; no version bump; no full heavy suites during work packages
**Scale/Scope**: `consolidation/executor.py` driver and rollback helpers, `coordination/transaction.py` gate extraction, `coordination/status_transition.py` probe, `consolidation/forecast.py`, `cli/commands/consolidate.py`, the AST pin, and about ten test files re-pinned

## Charter Check

- **Single canonical authority**: PASS by design. Rollback converges on `rollback_to_snapshot`; the preflight calls the transaction's own policy gate (extracted, not copied) instead of a second protection rule.
- **ATDD / red-first**: each work package starts with an issue-pinned `@pytest.mark.regression` repro that fails on the base, then converts it to focused tests at wrap-up.
- **Architectural gate discipline**: the AST pin grows a non-vacuous rule (all post-mutation phase calls inside the wrapper; no revert-based rollback helper) with self-mutation cases.
- **Campsite cleaning**: the retirement itself removes the executor's densest dead weight; touched functions stay ≤ 15 complexity.
- **Test policy**: targeted files and named architectural gates only (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Pack tiers / terminology**: no doctrine pack edits; Mission terminology only.

## Project Structure

### Documentation (this mission)

```
kitty-specs/single-rollback-authority-01M3RCP4/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/rollback-door.md
├── traces/ (tooling-friction, approach, design-decisions tracer files)
└── tasks.md (next phase)
```

### Source Code (repository root)

```
src/specify_cli/consolidation/executor.py        # driver wrapper, retirements, preflight call
src/specify_cli/consolidation/forecast.py        # dry-run parity
src/specify_cli/coordination/transaction.py      # extract the pre-flight policy gate
src/specify_cli/coordination/status_transition.py# status_write_refusal probe
src/specify_cli/cli/commands/consolidate.py      # readable BookkeepingPolicyRefused
tests/consolidation/test_single_rollback_authority.py  # AST pin grows
tests/terminus/test_repro_5385*.py               # red-first real-CLI repros
docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md # amendment follow-up
```

**Structure Decision**: single package; no new modules except the repro test files.

## Implementation Concern Map

### IC-01 — One rollback door in the driver

- **Purpose**: every non-zero exit, exception or interrupt between the first mutation and the gate rolls back through the authority.
- **Relevant requirements**: FR-001, FR-002, FR-009
- **Affected surfaces**: `executor.py` driver, `_report_rollback`
- **Sequencing/depends-on**: none
- **Risks**: `typer.Exit` is an `Exception` subclass, so exit-code 0 must pass through untouched; a rollback failure must never replace the original error; the resume short-circuit path must keep its current gate-only wrapping.

### IC-02 — Retire the revert-based rollbacks

- **Purpose**: delete the deprecated authorities so there is one way to undo branch moves.
- **Relevant requirements**: FR-004, FR-005
- **Affected surfaces**: `executor.py` helpers and their callers; `_MergeRunState.pre_bake_target_baseline_sha`; tests pinning the old contract (#1826, #2367, #2711, #2786, #4764, coord reconcile)
- **Sequencing/depends-on**: IC-01 (the door must exist before the old paths go)
- **Risks**: `state.pre_mutation_coord_sha` and `_capture_coord_checkpoint` stay (the authority seeds from them); test re-pins must assert the new contract, never delete coverage.

### IC-03 — AST pin

- **Purpose**: close the class by construction.
- **Relevant requirements**: FR-008
- **Affected surfaces**: `tests/consolidation/test_single_rollback_authority.py`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: vacuity; the pin needs a concrete floor and self-mutation cases.

### IC-04 — Protected-target preflight

- **Purpose**: refuse before any mutation when the done write would be refused.
- **Relevant requirements**: FR-003, FR-006, FR-007
- **Affected surfaces**: `coordination/transaction.py`, `coordination/status_transition.py`, `executor.py` pre-lock checks, `forecast.py`, `consolidate.py`
- **Sequencing/depends-on**: none technically; lands after IC-01 because both touch `executor.py`
- **Risks**: over-refusal (all-done resume, fallback topology, coordination recovery, single_branch landing, `--target` override, operator hatch). The probe must follow exactly the arm selection and gate the real write uses.

### IC-05 — Docs and changelog

- **Purpose**: record the closed residual and the new refusal.
- **Relevant requirements**: all (documentation of shipped behaviour)
- **Affected surfaces**: ADR `2026-09-19-1`, `CLAUDE.md` consolidation section, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01..IC-04
- **Risks**: docs freshness gate; terminology guard.
