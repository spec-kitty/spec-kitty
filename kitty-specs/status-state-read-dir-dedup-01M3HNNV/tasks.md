# Tasks: Single STATUS_STATE read-dir resolver with phantom-coord degrade

**Mission**: `status-state-read-dir-dedup-01M3HNNV` · **Issue**: #5180 · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first issue-pinned repro (ambient-ancestor phantom) for render + verdict reads | WP01 | |
| T002 | Public `resolve_partition_read_dir(feature_dir, kind)` on the read-path owner | WP01 | |
| T003 | Focused unit tests for the resolver (flat self-home, phantom degrade, both-missing, coord materialised, deleted coord propagates) | WP01 | |
| T004 | Repoint the post-merge gate, render and verdict paths; delete the private copies | WP02 | |
| T005 | Structural delegation guard with poison arm (FR-004) | WP02 | |
| T006 | Convert the red-first repro into focused tests (drop `regression` marker) | WP02 | |

## WP01 — Resolver authority + red-first repro

**Goal**: land the RED reproduction, then the one public resolver with its unit tests.
**Priority**: P1 · **Independent test**: `pytest tests/specify_cli/missions/test_partition_read_dir.py tests/agent/test_status_state_phantom_degrade.py`
**Prompt**: [tasks/WP01-resolver-authority.md](tasks/WP01-resolver-authority.md)

T001 Red-first issue-pinned repro (WP01)
T002 Public resolver on `_read_path_resolver` (WP01)
T003 Resolver unit tests (WP01)

Risks: import cycle with `mission_runtime.resolution` (keep the `resolve_artifact_surface` import lazy).

## WP02 — Repoint consumers + structural guard

**Goal**: the three consumers delegate to the resolver; the repro goes green; a non-vacuous guard stops a copy returning.
**Priority**: P1 · **Depends on**: WP01
**Independent test**: repro + guard + existing `tests/agent/test_workflow_review_cycle_pointer.py`, `tests/review/test_artifacts.py`, `tests/specify_cli/review/test_cycle_kind_flip.py`, `tests/specify_cli/cli/commands/agent/test_2959_override_partition.py`
**Prompt**: [tasks/WP02-repoint-consumers.md](tasks/WP02-repoint-consumers.md)

T004 Repoint consumers, delete private copies (WP02)
T005 Structural delegation guard (WP02)
T006 Convert repro to focused tests (WP02)

Risks: C-001 render split must hold (artifact-pointer resolution stays PRIMARY).
