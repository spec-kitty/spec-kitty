# Implementation Plan: Corpus advisory suite budget you can defend

**Branch**: `issue-7206-corpus-advisory-budget` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/corpus-advisory-budget-01M6P49E/spec.md`
**Input**: Mission specification from `kitty-specs/corpus-advisory-budget-01M6P49E/spec.md`

## Summary

The advisory `built-in-corpus-suite` job in `.github/workflows/packs.yml` runs at
`timeout-minutes: 20` while its measured p95 is 20.3 min (102 % of the cap). The measurement
(`research.md`) shows most of a PR run is fixed cost that two pinned guards forbid narrowing, so
the fix is: record the measured maximum suite wall-clock on the job, derive the cap from it with the
repository's existing #5378 formula (`ceil((max + 0:30) × 1.5)` = 31), enforce that derivation in
the cap guard that already owns this convention, and make a budget expiry legible as an incomplete
advisory run instead of a bare cancellation. No selection semantic moves: same marker, same
deselects, same `continue-on-error`, same trigger, same exclusion from `packs-gate.needs`.

## Technical Context

**Language/Version**: YAML workflows + Python 3.11/3.12 test guards (no production Python change)
**Primary Dependencies**: GitHub Actions (`packs.yml`), pytest, PyYAML (already test deps)
**Storage**: N/A
**Testing**: `pytest tests/ci/test_nightly_timeout_headroom.py tests/ci/test_corpus_suite_budget.py` plus the lane's existing invariants (`test_corpus_blocking_home.py`, `test_contracts_routing.py`, `test_xdist_worker_policy.py`, `test_ci_corpus_trigger_completeness.py`)
**Target Platform**: GitHub Actions `ubuntu-24.04` (4 vCPU) and the local `fast` tier
**Project Type**: single project (workflow + guard tests)
**Performance Goals**: measured p95 ÷ cap ≤ 0.75 (20.3 ÷ 31 = 65 %); guards run in < 2 s and read workflow text only
**Constraints**: no path shard, no matrix, exactly one pytest invocation in the job, advisory posture unchanged, no gate skipped or weakened
**Scale/Scope**: 1 workflow file, 2 test files (1 extended, 1 new), 1 reference doc, 1 changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — pass: the cap derivation stays in the one guard that owns it
  (`tests/ci/test_nightly_timeout_headroom.py`); no second formula, no second job registry.
- **`change-apply-smallest-viable-diff` / `DIRECTIVE_024` locality** — pass: the workflow diff
  touches the corpus job's budget keys and its notice only; the pytest command line is untouched.
- **ATDD-first / `DIRECTIVE_034`** — pass: the cap guard is written first and shown red on the
  pre-fix cap before the workflow value changes.
- **Pre-existing Failure Reporting Rule** — pass: nothing pre-existing is claimed fixed; the
  deferred items are named in the PR.
- **No gate weakened** — pass: C-002 in the spec; every selection guard runs unchanged.

## Project Structure

### Documentation (this mission)

```
kitty-specs/corpus-advisory-budget-01M6P49E/
├── plan.md              # This file
├── spec.md              # Requirements
├── research.md          # Measured evidence (runs, jobs, per-step timings)
├── reasons-canvas.md    # REASONS canvas
└── tasks.md             # Work packages (/spec-kitty.tasks)
```

### Source Code (repository root)

```
.github/workflows/packs.yml                     # corpus job: headroom record, cap, step budget, notice
tests/ci/test_nightly_timeout_headroom.py       # extended: packs.yml::built-in-corpus-suite target
tests/ci/test_corpus_suite_budget.py            # new: step budget, notice legibility, 75 % ratio
docs/development/reference/ci-gate-mechanics.md # advisory lane budget + derivation
docs/changelog/unreleased/<pr>.fixed.md         # per-PR fragment
```

**Structure Decision**: Single project. The change is one workflow plus the guard modules that
already model CI budgets and the corpus lane; no source package is touched, so no module mirrors
are involved.

## Complexity Tracking

*No charter violations.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — Derive and record the cap

- **Purpose**: Replace the picked 20-minute cap with the value the measured maximum implies, and
  record the measurement next to it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-007, NFR-001, NFR-002, C-003
- **Affected surfaces**: `.github/workflows/packs.yml` (job comment + `timeout-minutes`),
  `tests/ci/test_nightly_timeout_headroom.py`
- **Sequencing/depends-on**: none
- **Risks**: the existing guard's block parser is per-file and 4-space-indent sensitive; the headroom
  comment must sit directly above the job-level `timeout-minutes` or the guard reports "missing".

### IC-02 — Make a budget expiry legible

- **Purpose**: Ensure a killed suite still reaches a notice that says INCOMPLETE/advisory, and that
  the notice cannot be mistaken for a test failure.
- **Relevant requirements**: FR-004, FR-005, NFR-004, C-002, C-004
- **Affected surfaces**: `.github/workflows/packs.yml` (suite step `timeout-minutes`, notice step),
  `tests/ci/test_corpus_suite_budget.py`
- **Sequencing/depends-on**: IC-01 (the step budget is defined relative to the job cap)
- **Risks**: a step-level `timeout-minutes` at or above the job cap would be dead config and is
  rejected by the guard; the notice must keep `if: failure()` (a job-cap expiry runs no steps).

### IC-03 — Guards and the recorded ratio

- **Purpose**: Machine-check the issue's own acceptance rule (p95 ≤ 75 % of the cap) against the
  recorded measurement, and prove the guards are load-bearing with mutation controls.
- **Relevant requirements**: FR-001, FR-006, SC-001, SC-002, SC-003, NFR-003
- **Affected surfaces**: `tests/ci/test_nightly_timeout_headroom.py`,
  `tests/ci/test_corpus_suite_budget.py`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: duplicating selection guards would create a second source of truth; the new module
  asserts only budget/notice facts and cites the existing guards for semantics.

### IC-04 — Docs and fragment

- **Purpose**: Keep the recorded rationale discoverable next to the lane's ownership statement and
  give the change a per-PR changelog fragment.
- **Relevant requirements**: FR-007, SC-004
- **Affected surfaces**: `docs/development/reference/ci-gate-mechanics.md`,
  `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-01..IC-03 (needs the final numbers and PR number)
- **Risks**: the doc page is docs-indexed; touching prose only (no new page, no ADR) avoids a
  regeneration; `check_changelog_style` rejects `[Unreleased]`-shaped fragments.
