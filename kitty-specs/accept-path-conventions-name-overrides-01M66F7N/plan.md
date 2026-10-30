# Implementation Plan: Name the path-convention override routes in accept's failure text

**Branch**: `issue-6633-accept-path-conventions-name-overrides` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/accept-path-conventions-name-overrides-01M66F7N/spec.md`

## Summary

The strict path-convention failure (`PathValidationResult.format_errors()` in `src/specify_cli/validators/paths.py`, the single seam consumed by `PathValidationError` and `summary_core.evaluate_path_conventions`) names only two levers: `accept --lenient` and `mkdir -p`. The two honest project-level levers — the `project.path_conventions` remap override in `.kittify/config.yaml` (#3016) and the mission-type override at `.kittify/overrides/missions/<type>/mission.yaml` (#4088) — are never named, so a non-`src/` repo cannot self-serve.

Approach: extend `PathValidationResult` with the data needed to render project-level guidance — the missing keys that a `path_conventions` override could remap (non-artifact-routed, per `ARTIFACT_ROUTED_KEYS`) and the mission-type slug derived from the mission's resolver path — and have `validate_mission_paths()` populate them. `format_errors()` then appends two guidance blocks after the existing `--lenient` sentence: a copy-pasteable `project.path_conventions` YAML snippet listing exactly the missing remappable keys, and a line naming the mission-override route for dropping a key the project has no directory for. The #3783 contract (`--lenient` named before `mkdir -p`, no unconditional "required" claim) is preserved and pinned by the existing unmodified test. The accept how-to and the changelog document both routes.

## Technical Context

**Language/Version**: Python 3.11+ (repo standard; `src/specify_cli/`)
**Primary Dependencies**: stdlib `dataclasses`, `pathlib`; `specify_cli.config.path_conventions.ARTIFACT_ROUTED_KEYS`; `specify_cli.mission.Mission`
**Storage**: N/A (rendered text only; no persistence)
**Testing**: `pytest` via `uv run pytest`; unit tests in `tests/agent/test_validators_unit.py` (the file that owns `format_errors` contract tests); acceptance-seam test in `tests/specify_cli/acceptance/` if needed for the `--diagnose` wrapper. Red-first: the regression test is written against the pre-fix entry point (`validate_mission_paths` strict mode / `format_errors`) and fails on `main`.
**Target Platform**: CLI operator surface (Linux/macOS/Windows terminals; plain text)
**Project Type**: single (core CLI package)
**Performance Goals**: N/A (string rendering on failure paths only)
**Constraints**: #3783 text contract (C-001); remap-only override vocabulary, no `deliverables` suggestion (C-002); single seam (C-003); no layout inference (C-004)
**Scale/Scope**: one dataclass, one validator function, one how-to page, changelog

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Single canonical authority: the remediation text stays in `format_errors()` only (C-003); docs cross-reference rather than duplicate it verbatim.
- Locality of change (DIRECTIVE_024): changes confined to `validators/paths.py`, its unit test file, one docs page, changelog.
- ATDD-first: FR-001/FR-002 pinned red-first through `validate_mission_paths` strict mode before the fix.
- No architectural boundary moves; no new module. Passes.

## Project Structure

### Documentation (this mission)

```
kitty-specs/accept-path-conventions-name-overrides-01M66F7N/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output
└── traces/              # Tracer files
```

### Source Code (repository root)

```
src/specify_cli/validators/paths.py     # PathValidationResult fields + format_errors guidance
src/specify_cli/config/path_conventions.py  # ARTIFACT_ROUTED_KEYS (read-only reference)
tests/agent/test_validators_unit.py     # red-first regression + contract tests
docs/guides/how-to/missions/accept-and-merge.md  # name both routes
docs/changelog/CHANGELOG.md             # [Unreleased] entry
```

**Structure Decision**: single-project layout; the mission touches only existing files, adds no new module.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — Failure-text guidance data and rendering

- **Purpose**: Carry (and render) which missing keys a `project.path_conventions` override could remap and the mission-type slug for the override route, without changing validation semantics.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/validators/paths.py`, `tests/agent/test_validators_unit.py`
- **Sequencing/depends-on**: none
- **Risks**: hand-built `PathValidationResult` fixtures (existing tests) must keep rendering valid text — new fields default empty and guidance degrades gracefully; the mission-type slug must not be guessed for neutral org missions (generic placeholder when not derivable).

### IC-02 — Documentation and changelog

- **Purpose**: Name both routes in the accept how-to where it says the other conventions "stay in force"; add the `[Unreleased]` changelog entry.
- **Relevant requirements**: FR-004, SC-004, SC-005
- **Affected surfaces**: `docs/guides/how-to/missions/accept-and-merge.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (text lands first so docs can reference actual output)
- **Risks**: none material; keep the how-to addition short and cross-linked to the ADR.
