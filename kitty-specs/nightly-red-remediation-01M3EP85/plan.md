# Implementation Plan: Nightly red remediation (run 36225024230)

**Branch**: `claude/lucid-ptolemy-fjtzep` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/nightly-red-remediation-01M3EP85/spec.md`

## Summary

Honestly turn the nightly `integration-next` and `performance` suites green, and close the CI escalation blind spot. The work falls into three groups:

1. **Re-pin seven fixture drifts (FR-001..FR-007).** Each drift was caused by a deliberate, ADR- or issue-backed product change (#4959, #5001, #4982, #4764, #4758, #4990). The fix aligns each fixture with the *current* contract rather than stubbing a gate the test itself is about.
2. **Fix two merge defects red-first (FR-008, FR-009).**
   - The dry-run forecast gets the same clean coordination refusal the real merge already has.
   - A fresh merge that stops in the pre-mutation gate phase clears its own just-created state, generalising the #4764 precedent. `--abort` also drops the reconciliation marker.
3. **Fix CI and the perf gate (FR-010, FR-011).**
   - Bound the interpreter suite step inside its job cap so the escalation and fail-loud steps always run.
   - Make the nightly summary fail closed.
   - Re-aim the doctor-ops sweep gate at the close loop.

## Engineering Alignment

- **Scope and approach:** confirmed by the operator via Decision Moment `01M3EP8GQWCEAWKGMBVQYNFN65`.
- **No further planning questions:** the review-squad analysis on #5045 already settled each design choice, and the operator asked to run the mission through to closeout and PR.
- **Rules that must always hold:**
  - A genuine pre-fix resume stays refused (FR-012 of the terminus mission).
  - An unmaterialized coordination read stays fail-closed (ADR 2026-09-24-2).
  - A stale non-causal approval stays ignored (events#69).

## Technical Context

**Language/Version**: Python 3.11 (CI floor); interpreter leg 3.13
**Primary Dependencies**: typer, rich, ruamel.yaml, spec-kitty-events 10.4, pytest 9, pytest-xdist, pytest-timeout
**Storage**: Files — `.kittify/runtime/merge/<mission_id>/state.json` and the reconciliation post-fix marker in the same runtime dir; `status.events.jsonl`; `lanes.json`
**Testing**: pytest (`tests/integration`, `tests/next`, `tests/merge`, `tests/cli`, `tests/ci`, `tests/specify_cli/invocation`), with the `performance` marker gated by `SPEC_KITTY_RUN_PERFORMANCE=1`
**Target Platform**: Linux CLI; GitHub Actions `ubuntu-latest`
**Project Type**: single (CLI + library)
**Performance Goals**: Doctor-ops sweep close path is linear in closes and independent of spine size; interpreter suite fits inside its bounded step budget
**Constraints**: No skip/xfail/retry (C-001); red-first for product fixes (C-002); `tests/integration` stays nightly-only (C-003); no `packs/` edits (C-005); ruff/format/mypy clean; complexity ≤15
**Scale/Scope**: ~12 test files, 3 source files (`merge/forecast.py` or `cli/commands/merge.py`, `merge/executor.py`, `cli/commands/merge.py` abort path), 1 workflow file

## Charter Check

- **ATDD / red-first (Standing Order 4):**
  - FR-008 and FR-009 each start with a failing test through `spec-kitty merge` (CLI runner) or `_run_lane_based_merge`.
  - The fixture re-pins judge the test, not git-blame: each is *stale → re-pin*, and its docstring cites the product change behind it.
- **Never green-wash red main (Standing Order 9):** no skip, xfail or retry. The retrospect fixture change keeps the reducer's stale-event rule untouched.
- **Single canonical authority:**
  - FR-009 reuses the #4764 "clear only this run's own fresh state" rule instead of adding a second marker-write site.
  - FR-008 reuses the executor's refusal wording through one shared helper instead of duplicating it.
- **Locality of change (DIRECTIVE_024):** fixes stay inside the modules already on the failing paths.
- **Campsite cleaning (DIRECTIVE_025):** limited to the touched helpers. No unrelated refactors.
- **Terminology:** "Mission", "coordination worktree", "status commit". No "feature" in new prose.
- **Git discipline:** PR to `main`, and the operator merges. Tests are run per the CLAUDE.md test policy.

**Result:** PASS, no violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/nightly-red-remediation-01M3EP85/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── checklists/requirements.md
└── tasks/ (by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/merge.py        # FR-008 dry-run call site; FR-009 abort marker cleanup
└── merge/
    ├── executor.py              # FR-008 shared refusal helper; FR-009 fresh-state clear on pre-mutation exit
    └── forecast.py              # FR-008 (if the catch lands at the forecast seam)

tests/integration/               # FR-001..FR-007 re-pins
├── test_surface_translation_seam.py
├── test_coord_unprotected_lifecycle_loop.py
├── test_merge_lane_planning_data_loss.py
├── test_post_merge_index_refresh.py
├── test_post_merge_unrelated_untracked.py
├── sparse_checkout/test_merge_refresh_and_invariant.py
├── test_merge_resume.py
├── test_merge_lane_worktree_safety.py
├── test_merge_primary_checkout_safety.py
├── test_review_durability_matrix.py
└── test_implement_review_retrospect_smoke.py

tests/cli/commands/ or tests/merge/   # FR-008 / FR-009 red-first regressions
tests/specify_cli/invocation/test_doctor_ops.py   # FR-011
tests/ci/                             # FR-010 workflow-shape tests
.github/workflows/ci-nightly.yml      # FR-010
```

**Structure Decision**: Existing single-project layout; no new modules.

## Implementation Concern Map

| Concern | Requirements | Files | Notes |
|---|---|---|---|
| IC-1 Coordination fail-closed re-pins | FR-001 | seam, Guard4, retention tests | Reuse `_materialize_coord_worktree` pattern (42adce94) |
| IC-2 Merge-path fixture re-pins | FR-002, FR-003, FR-004, FR-005 | 7 integration merge files | Stubs only where the test's subject is not the gate; append new patches at the end of `_patches()` |
| IC-3 Review/retrospect fixture re-pins | FR-006, FR-007 | review durability, retrospect smoke | Add the guard negative cell |
| IC-4 Merge dry-run clean refusal | FR-008 | cli merge / forecast / executor | Red-first CLI test; JSON parity |
| IC-5 Fresh-stop wedge | FR-009 | executor, cli merge abort | Red-first: gates-fail then re-run |
| IC-6 Nightly fail-closed | FR-010 | ci-nightly.yml, tests/ci | Step-level timeout + summary gate |
| IC-7 Sweep gate re-aim | FR-011 | test_doctor_ops.py | Scaling assertion |

## Parallel Work Analysis

- **Dependencies:** IC-1, IC-3, IC-6 and IC-7 are independent. IC-2 and IC-5 both touch the merge-executor surface; IC-5 changes production code that IC-2's tests exercise, so IC-5 lands first and IC-2 re-runs against it. IC-4 is independent of IC-5 but shares `cli/commands/merge.py`, so sequence IC-4 → IC-5 on one lane to avoid overlap.
- **Execution:** a single agent on a single-branch topology. Work packages run sequentially, grouped to minimise re-runs of the slow integration suite.

## Complexity Tracking

None.
