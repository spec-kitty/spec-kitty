# Implementation Plan: Green the reds — coord review honest-receipt re-pin

**Branch**: `kitty/mission-green-reds-coord-review-repin-01M4H53K` | **Date**: 2026-10-09 | **Spec**: `kitty-specs/green-reds-coord-review-repin-01M4H53K/spec.md`
**Input**: Mission specification from `kitty-specs/green-reds-coord-review-repin-01M4H53K/spec.md`

## Summary

Re-pin the single stale characterization assertion in `TestAgentActionReviewTextEnvelope::test_coord_mission_prompt_skeleton` (`tests/characterization/test_trio_json_envelope.py`) from `[refused]` to the honest-receipt `[ok]` behavior, plus add a prose assertion that pins the meaningful honest-failure line and update the now-stale docstring. No production (`src/`) change. Grounding and the operator-confirmed triage verdict are recorded in `spec.md` and `research.md`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest, typer (CliRunner); the test is `integration` + `git_repo` marked.
**Storage**: N/A
**Testing**: Characterization test run `-n0` (serial) via the project venv: `PWHEADLESS=1 .venv/bin/python -m pytest -n0 tests/characterization/test_trio_json_envelope.py`.
**Target Platform**: Linux (CI module matrix)
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: Smallest viable diff — edit only the coord review case body + its docstring; zero `src/` lines (NFR-001, C-002). Red-first, no green-washing (C-001).
**Scale/Scope**: 1 WP, 1 test file.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Standing Order #4 (test remediation):** the test is judged stale (behavior evolved via the #5440 honest-receipt fix) → re-pin, not product-fix. ✅ matches "stale → re-pin".
- **Standing Order #9 (red-main / no green-wash):** the re-pin is red under the old expectation and green under the new; the test is never skipped/disabled/xfail'd. ✅
- **DIRECTIVE_024 locality / smallest-viable-diff:** one test case + docstring only; Implement variant and `src/` untouched. ✅
- **Terminology Canon:** no `feature*` identifiers introduced; test uses existing fixtures. ✅
- **ATDD-first (C-011):** the re-pinned assertion is the failing-first contract — RED on the pre-edit expectation, GREEN on the final commit. ✅
- **No full heavy-suite runs:** validate the single file + targeted characterization dir only; CI owns the full sweep. ✅

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/green-reds-coord-review-repin-01M4H53K/
├── plan.md              # This file
├── spec.md              # Mission spec + triage verdict
├── research.md          # Grounding (root cause, mechanism, evidence)
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
tests/
└── characterization/
    └── test_trio_json_envelope.py   # ONLY file changed — review-variant coord case + docstring
```

**Structure Decision**: Single project; the mission edits exactly one existing test file under `tests/characterization/`. No new modules, no `src/` changes.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*
