# Tasks: Remote-only branch recovery remedy

**Mission**: `remote-only-branch-remedy-01M7X5Z5` · **Planning base / merge target**: `issue-5287-remote-only-coord-remedy`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first ATDD: unmaterialized refusal next_step names the resolved remote, has the `git branch` step, no "has not fetched" | WP01 | |
| T002 | `mission_runtime/coord_remedy.py`: `RemoteOnlyBranch` facts + `remote_only_branch()` + pure `remote_only_steps()` with unit tests | WP01 | |
| T003 | Rewire `CoordinationWorktreeUnmaterialized._compose_next_step` remote arm to the builder | WP01 | |
| T004 | Rewire `_coordination_doctor._coord_worktree_missing_remote_only_steps` to the builder | WP01 | |
| T005 | Rewire `write_target_degrade` remote arm to the builder | WP01 | |
| T006 | Parity test (doctor finding, unmaterialized refusal, write refusal embed one remedy) + re-pin existing remedy assertions | WP01 | |
| T007 | Red-first ATDD: `agent tasks status --json` on a remote-only coordination Mission reports `STATUS_SURFACE_REF_REMOTE_ONLY` + remedy | WP02 | |
| T008 | `StatusSurfaceRefRemoteOnly` subtype + code in `status_service.py` | WP02 | |
| T009 | Door classification at `_coord_ref_decision` prefetch (COORD_BRANCH_REF) | WP02 | |
| T010 | Door classification at `_ref_text` (MISSION_BRANCH_REF) + door unit tests incl. corrupt-local-ref negative control | WP02 | |
| T011 | `next` query relay test; ADR 2026-11-06-2 amendment; changelog fragment | WP02 | |

## Phase 1 — Foundation

### WP01 — Canonical remote-only remedy (`tasks/WP01-canonical-remote-only-remedy.md`)

**Goal**: one builder composes the truthful remote-only remedy; the three remedy-emitting surfaces use it. **Priority**: P1. **Independent test**: the remote-only fixture (remote `coord-remote`) yields identical, correct steps on all three surfaces.

T001 Red-first ATDD for R3 (WP01)
T002 Builder module + unit tests (WP01)
T003 Unmaterialized refusal remote arm → builder (WP01)
T004 Doctor remote-only steps → builder (WP01)
T005 Write refusal remote arm → builder (WP01)
T006 Parity test + re-pins (WP01)

**Dependencies**: none. **Risks**: re-pins in `test_coord_branch_remote_probe_4979.py` and `test_coordination_remedy_5113.py`; layer gate.

## Phase 2 — Status read door

### WP02 — Typed remote-only refusal at the status read door (`tasks/WP02-door-remote-only-refusal.md`)

**Goal**: a failed ref read of a branch with no local head raises `StatusSurfaceRefRemoteOnly` with the WP01 remedy, at both ref sources. **Priority**: P1. **Independent test**: `agent tasks status --json` on the remote-only fixture.

T007 Red-first CLI ATDD for R1 (WP02)
T008 Subtype + code (WP02)
T009 COORD_BRANCH_REF classification (WP02)
T010 MISSION_BRANCH_REF classification + door unit tests (WP02)
T011 `next` relay test, ADR amendment, changelog (WP02)

**Dependencies**: Depends on WP01. **Risks**: NFR-001 (no extra subprocess on success); corrupt local ref must keep the unreadable code.
