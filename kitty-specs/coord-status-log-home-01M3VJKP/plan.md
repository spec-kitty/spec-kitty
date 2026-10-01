# Implementation Plan: Coordination status log stays off the target branch

**Branch**: `claude/project-thread-oymt0g` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/coord-status-log-home-01M3VJKP/spec.md`

## Summary

`create_mission_core` builds one scaffold commit over `meta.json`, `status.events.jsonl`, `tasks/README.md` and `tasks/.gitkeep` and lands it on the target branch for every topology. For a coordination-routed topology the status log is a COORD-partition kind, so the create itself puts it on the target branch (#5440, red-first in PR #5518). The fix gives the status log its coordination home at create: the create materializes the coordination worktree through the canonical write-time seam, emits `MissionCreated` and `SpecifyStarted` into the worktree's mission directory, and commits the log on the coordination branch. The target-branch scaffold commit carries only the primary-partition files. Because the coordination worktree now holds the mission directory from birth, the canonical status surface resolves there, so later lifecycle writes (implement, lane moves, accept residuals) never touch a primary copy.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git (worktrees), existing `mission_runtime` placement seam, `specify_cli.coordination.surface_resolver`
**Storage**: Files in git (`kitty-specs/<mission>/status.events.jsonl`)
**Testing**: pytest; red-first reproduction from PR #5518; targeted `tests/core` mission-create files; one new e2e lifecycle test (CI-owned lane)
**Target Platform**: Linux, macOS, Windows (cross-platform git subprocess calls only)
**Project Type**: single
**Performance Goals**: one extra worktree materialization and one extra commit on a coordination create (both previously paid at the first coordination write)
**Constraints**: no edits to `coordination/commit_router.py` or `cli/commands/accept.py` (owned by the #5513 remediation); complexity at most 15 per function
**Scale/Scope**: one source module (`src/specify_cli/core/mission_creation.py`) plus tests

## Charter Check

- **Single canonical authority**: placement reuses `routes_through_coordination`, `resolve_placement_only(STATUS_STATE)` and `materialize_coord_surface_for_write`. No new placement authority. Pass.
- **ATDD / red-first**: the PR #5518 test is adopted unchanged; the e2e lifecycle test is shown red on `main` before the fix. Pass.
- **Test remediation discipline**: the characterisation tests that pinned the defective tree (`test_scaffold_commit_is_single_commit_excluding_spec_md`, the fanout-boundary tests) are stale, not wrong about intent; they are re-pinned per topology, never deleted or skipped. Pass.
- **Campsite cleaning**: `mission_creation.py` repeats the `"status.events.jsonl"` literal; it is hoisted to a module constant as part of the change. Pass.
- **No heavy suites in mission**: targeted files only. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/coord-status-log-home-01M3VJKP/
├── spec.md
├── plan.md
├── research.md
├── tasks.md
├── traces/
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/core/mission_creation.py      # the only product module changed
tests/core/test_mission_create_coord_status_placement.py   # PR #5518 red-first test (adopted)
tests/core/test_mission_creation_decomposition.py          # re-pinned per topology
tests/core/test_mission_creation_fanout_commit_boundary.py # re-pinned: log committed on its own home
tests/e2e/test_coord_status_off_target_lifecycle.py        # new lifecycle guard (implement leg)
```

**Structure Decision**: single project; the change is confined to the create pipeline.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Seed the status log on the coordination branch at create

- **Purpose**: Give a coordination mission's status log one durable home from birth and keep it out of the target-branch scaffold commit.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-006
- **Affected surfaces**: `src/specify_cli/core/mission_creation.py` (`_scaffold_mission_dir`, new `_place_status_log` / `_seed_coordination_status_dir` / `_commit_coordination_status_seed`, `_create_mission_core_impl`, `_build_create_result`)
- **Sequencing/depends-on**: none
- **Risks**: Characterisation tests pin the old tree and must be re-pinned per topology. The fanout-after-commit contract must hold for the coordination copy (commit before fanout).

### IC-02 — Roll back the coordination worktree on a failed create

- **Purpose**: A failed create must not leave an orphan coordination worktree that blocks deleting the orphan branch, and must keep the status log as diagnosis evidence.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `_restore_git_state_after_failed_create` in `mission_creation.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: Best-effort cleanup must never mask the original failure.

### IC-03 — Lifecycle guard for the later legs

- **Purpose**: Prove that implement and lane moves keep the target branch free of status byte-sets once the status surface is seeded.
- **Relevant requirements**: FR-004
- **Affected surfaces**: new `tests/e2e/test_coord_status_off_target_lifecycle.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: e2e runtime; the test is marked `e2e` + `slow` so CI owns it.
