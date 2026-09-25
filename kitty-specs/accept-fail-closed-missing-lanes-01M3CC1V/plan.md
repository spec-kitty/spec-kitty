# Implementation Plan: Accept fail-closed on absent lanes.json

**Branch**: `issue-4891-accept-fail-closed-missing-lanes` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/spec.md`

## Summary

Make `spec-kitty accept` **fail closed** when `kitty-specs/<slug>/lanes.json` is absent, instead
of the current silent early-return that skips the entire acceptance-matrix gate (exit 0,
`ok=True`, acceptance recorded and committed on a `pending` matrix). The change is a single edit to
`_resolve_lanes_manifest_or_stop` in `src/specify_cli/acceptance/gates_core.py`: treat a
`read_lanes_json → None` (genuine absence) exactly as the existing `CorruptLanesError` arm does —
record an `activity_issue` (the field that flips `AcceptanceSummary.ok`), a `blocked_checks`
`lanes_manifest` diagnostic, and `_append_skipped_lane_checks(..., include_matrix_presence=True)` —
with remediation wording sourced from `MissingLanesError`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, pytest, mypy (strict), ruff — no new deps
**Storage**: filesystem (`kitty-specs/<slug>/lanes.json`, `meta.json`)
**Testing**: pytest (`tests/characterization/`, `tests/cross_cutting/misc/`, `tests/integration/`)
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (CLI/library)
**Performance Goals**: N/A (guard is a cheap in-memory check on an already-read manifest)
**Constraints**: `ruff` + `ruff format` + `mypy --strict` zero new issues; touched functions ≤15 complexity; ATDD red-first; no new suppressions
**Scale/Scope**: one production function edit + one characterization-test inversion + focused unit/e2e coverage

## Constitution Check

- **Single canonical authority (NFR-001):** extends the existing `_resolve_lanes_manifest_or_stop`
  seam; introduces no second lanes-resolution authority and no coord-aware read (`lanes.json` is
  PRIMARY-partition per `mission_runtime/artifacts.py:158-186`). ✅
- **ATDD-first (C-001):** red-first repro through the real accept path before the fix. ✅
- **Fail-closed toward safety:** absence → refuse, consistent with `implement`/`review`/`merge`
  (`MissingLanesError`). ✅
- **Terminology canon:** internal `feature_dir` parameter names are pre-existing/legacy-internal;
  no new user-facing `feature*` surface introduced. ✅
- **Locality of change / smallest-viable-diff:** one function's behaviour on the `None` path; no
  file-set growth beyond the seam + its tests. ✅

No violations → Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/
├── spec.md                     # done
├── plan.md                     # this file
├── tracer-approach.md          # done
├── tracer-design-decisions.md  # done
├── tracer-tooling-friction.md  # done
├── tasks.md                    # next (/spec-kitty.tasks)
└── tasks/                      # WP files
```

### Source Code (repository root)

```
src/specify_cli/acceptance/
├── gates_core.py     # EDIT: _resolve_lanes_manifest_or_stop None-path → fail closed
└── __init__.py       # READ-only reference: AcceptanceSummary.ok (why activity_issue is load-bearing)

tests/
├── characterization/test_trio_pure_cores.py          # INVERT the codified-bug test + add fail-closed case
├── cross_cutting/misc/test_acceptance_support.py      # ADD e2e summary.ok is False on absence
└── integration/                                       # WATCH: coord golden paths stay green
    ├── test_accept_matrix_coord_partition.py
    └── test_placement_partition_golden_path.py
```

**Structure Decision**: Single-project CLI layout. The change is localized to the acceptance
gate seam under `src/specify_cli/acceptance/`; tests live in the existing acceptance/characterization
test homes (no new test packages).

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

## Parallel Work Analysis

Single-stream mission (one work package). No parallelism required; the fix, its red-first test, and
its regression coverage are one cohesive slice with no independent sub-streams.

- **Sequential work**: red-first test → fix → green + regression watch.
- **Parallel streams**: none.
- **Agent assignments**: one implementer (python-pedro, sonnet) owns `src/specify_cli/acceptance/`
  and the named test files; review by reviewer-renata (opus).
