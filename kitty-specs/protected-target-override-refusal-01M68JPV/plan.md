# Implementation Plan: Refuse a `--target` override onto a protected branch

**Branch**: `issue-6464-protected-target-override-refusal` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/protected-target-override-refusal-01M68JPV/spec.md`
**Issue**: spec-kitty/spec-kitty#6464

## Summary

`consolidate` resolves an effective target (explicit `--target` > persisted record > `meta.json` >
repo default) and retargets the run's lane manifest to it, but the only protected-branch refusal in
the pipeline (`refuse_protected_status_target`, #5385) probes the **recorded** target. An operator who
passes `--target main` on a Mission recorded for `develop` therefore squash-commits the Mission onto
local `main` — the branch-integration commit is a raw `git commit` inside an ephemeral worktree
(`lanes/consolidation.py::_merge_branch_into` → `conclude_in_progress_op`), so the workflow mutation
policy every status commit passes through never sees it.

The fix adds one narrow, pre-mutation refusal: when the effective target is **not** the Mission's
recorded target and `ProtectionPolicy.is_protected_target` says that branch is protected, refuse with
`PROTECTED_BRANCH_REFUSED` and a message naming both branches and the ways forward. It is scoped to
the override, so every decision #5385 already makes (recorded target; coordination, all-done and
`commit_to_target` landings) keeps its outcome.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer (CLI), `ruamel.yaml` (config), in-repo `ProtectionPolicy`
**Storage**: `meta.json` (recorded target), `.kittify/config.yaml` (protected set), git refs
**Testing**: pytest; end-to-end through the real `spec-kitty consolidate` CLI over real git
(`tests/terminus/`, nothing mocked) and through the orchestrator-api JSON envelope suite
**Target Platform**: any git checkout; no platform-specific code
**Project Type**: single project (CLI library plus tests)
**Performance Goals**: no measurable change to a refused run; one extra policy resolution pre-lock
**Constraints**: reuse `PROTECTED_BRANCH_REFUSED` (no new code); refuse before the global merge lock
so nothing is written; one protection authority only (`ProtectionPolicy`)
**Scale/Scope**: one seam function plus three call sites, and tests; no schema, no migration

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|------|---------|
| Single canonical authority | **Pass** — the decision stays `ProtectionPolicy`'s; no second list, no bespoke name comparison. |
| Architectural alignment / locality of change | **Pass** — the guard sits beside the existing refusal in `consolidation/preflight.py`; the CLI shim (`cli/commands/consolidate.py`) is not grown (its decomposition rules forbid it). |
| ATDD-first | **Pass** — the red test drives the real `spec-kitty consolidate` CLI through the pre-existing entry point before the fix. |
| Terminology | **Pass** — "mission", "consolidate", "target branch", "primary branch" in their documented senses; the refusal names the *branch-integration* sense. |
| Test-first bug fixing (DIRECTIVE_034) | **Pass** — the repro is added red, the fix turns it green, and the repro stays as a `regression` test. |
| No new doctrine | **Pass** — no `packs/` change. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/protected-target-override-refusal-01M68JPV/
├── plan.md              # This file
├── spec.md              # Authored specification
├── tasks.md             # /spec-kitty.tasks output
└── meta.json            # Mission identity (lanes topology, PR-bound branch)
```

### Source Code (repository root)

```
src/specify_cli/consolidation/preflight.py         # the refusal seam, beside refuse_protected_status_target
src/specify_cli/consolidation/entry_preflight.py   # pre-lock CLI door (extends _refuse_protected_status_target_or_continue)
src/specify_cli/consolidation/forecast.py          # --dry-run parity: same code and remedy in the JSON payload
src/specify_cli/orchestrator_api/consolidation.py  # orchestrator-api parity: failure envelope

tests/terminus/test_protected_target_preflight.py                   # red-first e2e + in-bounds and hatch controls
tests/orchestrator_api/test_consolidate_mission_protected_target.py  # API envelope parity
```

**Structure Decision**: single project. All production change sits in the consolidation seam family
plus the orchestrator-api adapter that already calls the same preflight; the CLI shim is untouched.

## Implementation Concern Map

### IC-01 — The decision seam and its three entries

- **Purpose**: One function asks `ProtectionPolicy` whether the effective target is protected and,
  when it differs from the recorded target, returns the policy-shaped refusal; the CLI door, the
  dry-run forecast and the orchestrator-api path each call it before any mutation.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001
- **Affected surfaces**: `consolidation/preflight.py`, `consolidation/entry_preflight.py`,
  `consolidation/forecast.py`, `orchestrator_api/consolidation.py`
- **Sequencing/depends-on**: none
- **Risks**: the recorded target must be read with the *no-override* resolver (`meta.json`), never
  from the retargeted manifest, or the guard becomes vacuous; the guard must run after #5385's probe
  so the pinned recorded-target refusal (code, remedy, footer) keeps its exact text; the dry-run
  forecast holds the un-retargeted manifest but already has `resolved_target_branch`, so both values
  are in hand on every path.

### IC-02 — The pinned regression and its controls

- **Purpose**: Prove the refusal through the real CLI and the real orchestrator-api, and prove on the
  same fixtures that an in-bounds `--target` still consolidates and the operator hatch still stands
  the guard down — so a guard that refuses everything fails.
- **Relevant requirements**: FR-001, FR-003, FR-004, NFR-001
- **Affected surfaces**: `tests/terminus/test_protected_target_preflight.py`,
  `tests/orchestrator_api/test_consolidate_mission_protected_target.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the fixture must leave the checkout on the override branch, otherwise the pre-existing
  `MERGE_UNSAFE_PRIMARY_OFF_TARGET` guard refuses first and the new guard is never exercised — the
  test would pass vacuously.

## Complexity Tracking

No charter violations.

## Residuals (named, not closed)

- An override onto an **unprotected** branch other than the recorded target keeps today's behaviour:
  the squash lands, then `done` bookkeeping fails on the checkout HEAD mismatch and the rollback door
  restores the refs. Out of this Mission's scope (C-002).
- The recorded-target case (no override) keeps #5385's decision, including its deliberately-allowed
  coordination / all-done / `commit_to_target` landings.
