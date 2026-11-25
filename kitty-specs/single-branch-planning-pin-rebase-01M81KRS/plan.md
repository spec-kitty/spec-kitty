# Implementation Plan: single_branch planning pin across a rebase

**Branch**: `kitty/mission-single-branch-planning-pin-rebase-01M81KRS` (lands on `issue-7793-single-branch-planning-pin`) | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/single-branch-planning-pin-rebase-01M81KRS/spec.md`

## Summary

Make the pin authority single-branch aware, so it records and maintains the pin on the line the
evidence window reads (the mission branch). An orphaned-pin re-pin follows the planning commit by
patch-id, refuses with a named code when that fails, and never writes a pin whose window drops the
committed owned-file work. A derived pin is marked in `lanes.json` and the automatic refresh keeps
it. Derivation anchors on the latest (re-)appearance of any task file. The messages are aligned
across finalize, `move-task` and `doctor`. Design detail: [research.md](research.md),
[data-model.md](data-model.md), [contracts/pin-decisions.md](contracts/pin-decisions.md).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git (CLI subprocess through `kernel.git.run_git` and `consolidation.git_probes`)
**Storage**: files; `kitty-specs/<slug>/lanes.json` (one additive optional key)
**Testing**: pytest; red-first real-CLI integration tests (`tests/integration/`, the #5939 harness) plus unit tests over real temporary git repos
**Target Platform**: Linux, macOS, Windows (git ≥ 2.38 already required elsewhere; patch-id needs none newer)
**Project Type**: single (CLI)
**Performance Goals**: finalize < 2 s on a 200-commit mission branch (NFR-001)
**Constraints**: fail closed on git errors (NFR-002); no second patch-id/derivation authority (C-001); lane topologies unchanged (C-003)
**Scale/Scope**: about 5 source modules, about 6 test files, one ADR amendment

## Charter Check

- **Single canonical authority**: patch-id via `git_probes.patch_id_of`/`patch_ids_in_range`;
  derivation stays in `lanes/planning_base.py`; the pin branch line is resolved once
  (`planning_base.pin_branch_line`) and used by capture, refresh and derive. PASS.
- **ATDD-first / red-first**: the #7793 scenario and the no-match refusal are written first, through
  the real CLI, and fail on `main`. PASS (planned in the first WP).
- **Architectural alignment**: no new layer edges (`specify_cli` internal only). PASS.
- **Terminology canon**: "Mission", "pin", "evidence window"; no "feature". PASS.
- **Tiered rigour**: the pin authority is core-domain logic. It gets decision-table tests and
  real-git fixtures, not mocks. PASS.
- **Campsite cleaning (SO #2)**: `mission_finalize_planning_pin.py` is 1376 lines. The new decisions
  go in small helpers. `_resolve_preserve_planning_commit_decision` is at the complexity ceiling,
  so the derived-freeze branch is extracted rather than nested. PASS.
- **No heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION)**: targeted files only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/single-branch-planning-pin-rebase-01M81KRS/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/pin-decisions.md
├── tracer/ (tooling-friction.md, approach.md, design-decisions.md)
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/lanes/planning_base.py                         # derivation anchor, patch-id follow, pin branch line
src/specify_cli/lanes/models.py                                # LanesManifest.planning_commit_source (optional)
src/specify_cli/lanes/compute_and_persist.py (or mission_finalize_lanes.py)  # carry the source into the written manifest
src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py  # decisions: repin, freeze, capture line, reasons, text
src/specify_cli/cli/commands/agent/tasks_move_task.py          # single_branch refusal remedy text
src/specify_cli/migration/mission_state.py + cli/commands/_mission_state_doctor.py  # doctor gaps
docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md  # amendment
tests/lanes/, tests/integration/, tests/specify_cli/cli/commands/agent/, tests/specify_cli/migration/
```

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Pin authority primitives

- **Purpose**: one place that answers "which branch line holds the pin", "which commit is the
  rebased copy of this pin", and "what is the derived base".
- **Relevant requirements**: FR-001, FR-002, FR-005, FR-008, FR-009, C-001
- **Affected surfaces**: `lanes/planning_base.py`, `lanes/models.py`
- **Sequencing/depends-on**: none
- **Risks**: patch-id of an empty-diff pin is `""`. It never matches, so it refuses (by design).
  Rename detection must stay bounded to the Mission's `tasks/` directory.

### IC-02 — Finalize pin decisions

- **Purpose**: wire the primitives into capture, the explicit refresh/repin, the automatic refresh
  and the success report; add the window guard and the derived freeze.
- **Relevant requirements**: FR-001-FR-006, NFR-001, NFR-002, C-002, C-003
- **Affected surfaces**: `mission_finalize_planning_pin.py`, the lanes write that carries the source
- **Sequencing/depends-on**: IC-01
- **Risks**: overlaps Slice 1a on `mission_finalize.py`, so edits stay inside
  `mission_finalize_planning_pin.py`. The `_prepare_primary_pin_refresh_commit` destination check
  must compare against the pin line. Golden JSON contract tests must stay byte-identical when the
  source key is absent.

### IC-03 — Messages, doctor and ADR

- **Purpose**: the `move-task` single_branch refusals name a live route; doctor warns on a `None`
  pin and names next steps; the ADR records the rules and residuals.
- **Relevant requirements**: FR-007, FR-010, C-004, C-005
- **Affected surfaces**: `tasks_move_task.py`, `migration/mission_state.py`,
  `cli/commands/_mission_state_doctor.py`, ADR `2026-10-04-5`
- **Sequencing/depends-on**: IC-02 (the remedy names the route IC-02 makes work)
- **Risks**: `tasks_move_task.py` overlaps #7809 (landing soon), so keep the edit to message text.
  The doctor change overlaps Slice 10, so keep it to the two warnings.
