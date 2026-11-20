# Implementation Plan: Per-mission-type path conventions and a narrow path waiver

**Branch**: `kitty/mission-path-conventions-per-type-01M7VRQM` (lands on `issue-7566-path-conventions-per-type`) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/path-conventions-per-type-01M7VRQM/spec.md`

Planning questions were answered by the operator rulings recorded for specify (Q1: both waivers, Q2: `mkdir -p` only for real deliverables, Q3: the layered roster). The remaining design choices are recorded in [research.md](research.md).

## Summary

`project.path_conventions` gains per-mission-type sections (a mapping value keyed by a mission-type id). The reader validates the new shape fail-closed against the project's layered mission-type roster. The accept seam resolves overrides per type (per-type, then flat, then the mission default). The failure and warning texts name the per-type remap first. Two narrow waivers make path conventions advisory without touching metadata strictness: a per-run `accept --waive-path-conventions --waive-reason` and a per-Mission `meta.json` declaration.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, ruamel.yaml (existing). No new dependency, so no supply-chain check applies.
**Storage**: `.kittify/config.yaml` (project config) and the Mission's `meta.json` (files)
**Testing**: pytest, red-first. Unit tests for the reader and validator; seam tests for `evaluate_path_conventions`; a CLI test for the `accept` flags; an open-packs-shaped acceptance fixture.
**Target Platform**: the Spec Kitty CLI (Linux, macOS, Windows)
**Project Type**: single
**Performance Goals**: one config read per accept run; the roster is read only when a per-type section exists (NFR-001)
**Constraints**: `validate_mission_paths` keeps a single production caller (C-001); no pack schema change (C-002); C901 ≤ 15; ruff, ruff format and mypy clean
**Scale/Scope**: about 6 source modules and about 8 test files; docs (ADR amendment, how-to, changelog fragment)

## Charter Check

- **Single canonical authority**: one reader for `project.path_conventions` (`config/path_conventions.py`) and one `meta.json` waiver reader family (`core/paths.py`, generalized from the #5298 contracts waiver rather than copied). Roster resolution reuses the existing layered seam (`resolve_layered_roster`) instead of a third copy. PASS.
- **ATDD-first / red-first**: every FR gets a failing test before code (see the IC sequencing). PASS.
- **Architectural alignment**: the change stays in `specify_cli` (config, validators, acceptance, cli/commands/accept). No charter or pack change. PASS.
- **Test policy**: the targeted modules plus `make test-fast`, and the named architectural gate `test_lifted_root_validate_mission_paths_single_caller.py`. No full heavy suites. PASS.
- **Terminology**: Mission, not feature, in new text. PASS.
- **Campsite**: generalizing the contracts waiver reader is a behaviour-preserving preceding step with its pins unchanged. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/path-conventions-per-type-01M7VRQM/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── config-schema.md
    ├── precedence-contract.md
    └── accept-waiver-contract.md
```

### Source Code (repository root)

```
src/specify_cli/config/path_conventions.py     # reader: per-type sections, fail-closed, roster check
src/specify_cli/validators/paths.py            # remedy text: per-type snippet first, waiver lines
src/specify_cli/acceptance/summary_core.py     # per-type resolution + waiver effect at the single caller
src/specify_cli/acceptance/__init__.py         # thread the per-run waiver through collect_feature_summary / record
src/specify_cli/core/paths.py                  # meta.json path-conventions waiver (generalized waiver reader)
src/specify_cli/mission_metadata.py            # history entry field + MissionMetaOptional fields
src/specify_cli/cli/commands/accept.py         # --waive-path-conventions / --waive-reason
src/specify_cli/cli/commands/agent/mission_accept_merge.py  # forward the flags
docs/adr/3.x/2026-08-28-1-project-path-convention-override-precedes-doctrine.md  # amendment
docs/guides/how-to/missions/accept-and-merge.md
docs/changelog/unreleased/7566-*.md
```

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Per-type configuration reader

- **Purpose**: read and validate per-type sections fail-closed while keeping the flat form byte-for-byte compatible.
- **Relevant requirements**: FR-001, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-005
- **Affected surfaces**: `src/specify_cli/config/path_conventions.py`, `tests/specify_cli/config/test_path_conventions_reader.py`
- **Sequencing/depends-on**: none
- **Risks**: the roster read can raise on a malformed org pack. It is done only when a per-type section exists. A roster failure is reported as a `PathConventionsConfigError` naming the cause, not a traceback.

### IC-02 — Per-type resolution at the accept seam

- **Purpose**: resolve overrides for the Mission's own type at the single caller of `validate_mission_paths`.
- **Relevant requirements**: FR-002, C-001, C-003, C-004, SC-001
- **Affected surfaces**: `src/specify_cli/acceptance/summary_core.py`, `src/specify_cli/validators/paths.py` (mission-type input to the result), `tests/specify_cli/acceptance/test_path_conventions_all_types.py`, the new open-packs fixture test
- **Sequencing/depends-on**: IC-01
- **Risks**: the Mission's type must come from the same source the Mission was loaded from (`meta.json` `mission_type`, defaulting to software-dev).

### IC-03 — Remedy text

- **Purpose**: name the per-type remap first; no `mkdir -p` for remappable keys; `contracts: none` named for `contracts/`; the mission.yaml copy demoted to a last resort; the narrow waivers named before `--lenient`.
- **Relevant requirements**: FR-006, FR-007, FR-008, FR-012, C-004
- **Affected surfaces**: `src/specify_cli/validators/paths.py`, `tests/agent/test_validators_unit.py`, `tests/specify_cli/acceptance/test_acceptance_support.py` (pinned payloads), `src/specify_cli/cli/commands/accept.py` (`--lenient` help), `tests/specify_cli/cli/commands/test_accept_lenient_help.py`
- **Sequencing/depends-on**: IC-02 (the remedy needs the resolved type)
- **Risks**: the #3783 and #7512 wording pins are updated deliberately, each with the reason recorded in the test docstring.

### IC-04 — Narrow path-convention waivers

- **Purpose**: a per-run flag and a per-Mission `meta.json` declaration that make path misses advisory with metadata still strict.
- **Relevant requirements**: FR-009, FR-010, FR-011, FR-013, C-006, SC-004
- **Affected surfaces**: `src/specify_cli/core/paths.py`, `src/specify_cli/acceptance/summary_core.py`, `src/specify_cli/acceptance/__init__.py`, `src/specify_cli/mission_metadata.py`, `src/specify_cli/cli/commands/accept.py`, `src/specify_cli/cli/commands/agent/mission_accept_merge.py`, their tests
- **Sequencing/depends-on**: IC-02 (shares the `evaluate_path_conventions` seam)
- **Risks**: orchestrator-api must stay strict; a positive control pins it.

### IC-05 — Documentation

- **Purpose**: record the precedence change and the waivers.
- **Relevant requirements**: brief scope item 5
- **Affected surfaces**: ADR `2026-08-28-1` (amendment), `docs/guides/how-to/missions/accept-and-merge.md`, a changelog fragment
- **Sequencing/depends-on**: IC-01 to IC-04
- **Risks**: the docs-retrieval index or link gates may need regeneration.
