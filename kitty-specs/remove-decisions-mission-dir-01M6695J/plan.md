# Implementation Plan: Remove the read-side decisions service._mission_dir

**Branch**: `issue-6766-remove-decisions-mission-dir` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/remove-decisions-mission-dir-01M6695J/spec.md` (issue spec-kitty/spec-kitty#6766)

## Summary

Delete the read-side `src/specify_cli/decisions/service.py::_mission_dir`
helper, left caller-less by PR #6762 (#4848) when the opened-row check moved
onto the pre-resolved write-side `events_path`. Remove the two
`tests/specify_cli/test_read_seam_leniency.py` pins that exercise only the
dead helper (and correct that file's module-docstring site ledger), re-point
the docstrings/comments in `service.py` that still name the helper, and add a
red-first guard test pinning the standing invariant: all STATUS_STATE access
in `decisions/service.py` is write-side
(`_write_mission_dir` / `_write_events_path`), never a read-side
`placement_seam(...).read_dir(STATUS_STATE)` call. No behaviour change for
any decisions CLI verb; the separate live `decisions/emit.py::_mission_dir`
is out of scope.

## Technical Context

**Language/Version**: Python 3.11+ (repository standard, `pyproject.toml`)
**Primary Dependencies**: typer, rich, ruamel.yaml; `mission_runtime`
(placement seam: `placement_seam`, `MissionArtifactKind`)
**Storage**: N/A (no data change; reads/writes of
`kitty-specs/<mission>/status.events.jsonl` unchanged)
**Testing**: pytest; targeted module suites (`tests/decisions/`,
`tests/specify_cli/decisions/`, `tests/specify_cli/test_read_seam_leniency.py`)
plus the named architectural gates; `make test-fast` baseline; ruff +
`ruff format --check --force-exclude` and mypy on touched files. Never a full
heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: cross-platform CLI (Linux/macOS/Windows 10+)
**Project Type**: single (open-core Python CLI monorepo)
**Performance Goals**: N/A (dead-code removal; no runtime path changes)
**Constraints**: diff-cover ≥90% on changed lines; no gate suppression, no
allowlist additions; `decisions/emit.py` untouched (C-001)
**Scale/Scope**: ~4 files (`src/specify_cli/decisions/service.py`,
`tests/specify_cli/test_read_seam_leniency.py`, one new guard test file,
`docs/changelog/CHANGELOG.md`); single implementer, single WP

## Charter Check

- Single canonical authority: the mission REMOVES a second (dead) read path
  for decisions STATUS_STATE — it unifies, not duplicates. PASS.
- Architectural alignment: stays inside `src/specify_cli/decisions/`; the
  placement-seam contract is untouched; `decisions/emit.py` (the COORD writer
  census entry) unchanged. PASS.
- ATDD-first: FR-004's guard test is red on the planning base (the
  `read_dir(STATUS_STATE)` call exists at `service.py:358` inside the dead
  helper) and green on the mission head. PASS.
- Terminology canon: no new user-facing terms. PASS.
- Campsite: the docstring/comment re-points (FR-003) and the leniency-file
  module-docstring correction (FR-002) are the in-file-surface tidy-up;
  nothing beyond the touched file set (locality brake, DIRECTIVE_024). PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/remove-decisions-mission-dir-01M6695J/
├── plan.md              # this file
├── research.md          # discovery findings (grounding evidence)
├── reasons-canvas.md    # SPDD canvas (Requirements / Entities)
└── tasks.md             # /spec-kitty.tasks output (Phase 2)
```

### Source Code (repository root)

```
src/specify_cli/decisions/
├── service.py           # delete _mission_dir; re-point stale docstrings
└── emit.py              # UNTOUCHED (own live _mission_dir; census-named)

tests/specify_cli/
├── test_read_seam_leniency.py   # drop the two dead-helper pins; fix ledger docstring
└── decisions/
    └── test_service_status_state_access.py   # NEW: red-first guard (FR-004)

tests/architectural/     # NOT edited: test_no_dead_symbols.py,
                         # test_no_read_side_bypass.py,
                         # test_no_write_side_rederivation.py must stay green

docs/changelog/CHANGELOG.md   # [Unreleased] entry (user-facing dead code removal)
```

**Structure Decision**: single-project layout (repository root `src/` +
`tests/`); the only new file is the guard test co-located with the decisions
service's test tree (`tests/specify_cli/decisions/`), mirroring
`src/specify_cli/decisions/service.py`.

## Implementation Concern Map

One concern; a single work package carries it.

### IC-01 — Dead read-side helper removal with invariant guard

- **Purpose**: Remove the caller-less read-side `_mission_dir` and pin the
  surviving write-side-only STATUS_STATE access invariant so the read/write
  split #4848 established cannot silently regress.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004; NFR-001,
  NFR-002; C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/decisions/service.py`,
  `tests/specify_cli/test_read_seam_leniency.py`,
  `tests/specify_cli/decisions/` (new guard test),
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none
- **Risks**: (a) hidden references to the helper beyond the surveyed set —
  mitigated by a repo-wide grep for `service._mission_dir` /
  `decisions.service import` plus the green module suites; (b) the
  `test_no_write_side_rederivation.py` census keys `_write_mission_dir`
  (live) and `_PRE_SPLIT_QUALNAMES` (base-proof only) — surveyed to survive
  unchanged, verified by running the gate; (c) red-first discipline — the
  guard test must be committed before the removal commit so the reviewer can
  verify red on the planning base.
