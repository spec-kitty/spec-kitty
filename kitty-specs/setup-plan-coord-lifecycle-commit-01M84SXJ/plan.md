# Implementation Plan: setup-plan commits its lifecycle events on coordination Missions

**Branch**: `kitty/mission-setup-plan-coord-lifecycle-commit-01M84SXJ` (merge target `issue-3933-lifecycle-event-placement`) | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/setup-plan-coord-lifecycle-commit-01M84SXJ/spec.md`

All planning questions are answered. The Engineering Alignment was confirmed by the operator (Decision Moment `01M84X0BXENG3QN8NJBWP6YKJP`, "agreed").

## Summary

On a Mission whose coordination branch exists at setup-plan time (explicit `coord` / `lanes_with_coord`), `spec-kitty agent mission setup-plan` today appends `SpecifyCompleted`, `PlanStarted` and `PlanCompleted` to the coordination worktree's status log (its `feature_dir` comes from the coordination-aware read resolver) and leaves them uncommitted (`_lifecycle_log_for_plan_commit` excludes that log from the plan commit on purpose, a recorded residual of PR #7562). This Mission moves the writes onto the single write location for status records, `placement_seam(...).write_dir(STATUS_STATE)` (no behaviour change, FR-001 ratchet), and commits them on the coordination branch with one `commit_for_mission(kind=STATUS_STATE)` call at the end of the run. A refused commit fails loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`. The stranded-event report (FR-005) is the existing `doctor coordination` warning `COORDINATION_WORKTREE_DIRTY` (operator ruling `01M853E34H1MN0CQGQ9209P8MR`); no doctor change.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing in-repo modules only: `mission_runtime.placement_seam` (write location), `specify_cli.coordination.commit_router.commit_for_mission` (commit entry point), `specify_cli.status.emit_artifact_phase` (lifecycle event writer), `specify_cli.cli.commands._coordination_doctor` (health check). No new third-party dependency, so no supply-chain review is needed (DIRECTIVE_051 not triggered).
**Storage**: git-tracked files: the Mission's `status.events.jsonl` on the coordination branch (coordination worktree) and, for the residue check, the repository root checkout copy.
**Testing**: pytest, red-first through the real entry points (`spec-kitty agent mission setup-plan --json` via the Typer app on a real git repository; `spec-kitty doctor coordination --json`). New tests go in the in-matrix `tests/coordination/` directory. Regression: the existing `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py` (out of matrix, nightly-only, disclosed if changed) plus `make test-fast`.
**Target Platform**: the spec-kitty CLI on Linux/macOS/Windows (git >= 2.38 as today).
**Project Type**: single project (`src/` + `tests/`).
**Performance Goals**: at most one extra git commit per setup-plan run on a coordination Mission; zero when nothing is new (NFR-001).
**Constraints**: no new placement seam, no new commit path, no ADR (C-003); non-coordination topologies byte-identical (NFR-002); no migration of stranded events (C-002); default Missions before settlement untouched (C-001, follow-up #7827).
**Scale/Scope**: one source module changed (`mission_setup_plan.py`), one new test module.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority**: placement uses the one write-location authority (`write_dir`), the commit uses the one mission commit entry point. Pass.
- **Architectural alignment**: no new layer edge; `specify_cli` already imports both seams. Pass.
- **ATDD-first / red-first (Standing Order 4)**: each concern starts with a failing entry-point test. Pass (planned).
- **Fail loud (operator ruling on #7792)**: the refused-commit path exits 1 with a named code. Pass.
- **Campsite (Standing Order 2)**: the commit leg goes in a small new helper with its own tests instead of growing `setup_plan`. Complexity stays <= 15.
- **Terminology**: "Mission", "coordination branch", "repository root checkout" are used per the glossary. Pass.
- **Test policy**: in-matrix home for new tests; any changed out-of-matrix test is disclosed with a local run.

Post-design re-check: unchanged, all pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/setup-plan-coord-lifecycle-commit-01M84SXJ/
├── spec.md
├── plan.md              # this file
├── research.md          # decisions D1-D5
├── data-model.md        # lifecycle event / stranded event
├── quickstart.md        # how to see the fix work
└── tasks.md             # /spec-kitty.tasks output (not created here)
```

No `contracts/`: the Mission adds no interface. `meta.json` records `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/mission_setup_plan.py   # placement + one coordination commit + fail loud
tests/coordination/test_setup_plan_coord_lifecycle_3933.py # entry-point tests (new, in matrix)
```

**Structure Decision**: single project; changes stay in the two modules that own the behaviour.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — setup-plan records and commits its lifecycle events on the coordination branch

- **Purpose**: on a coordination Mission, the three setup-plan lifecycle events land on the coordination record and are committed there in the same run, or the run fails loud.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-003
- **Affected surfaces**: `mission_setup_plan.py` (`_emit_lifecycle_phase_markers`, the `PlanCompleted` emission in `_commit_plan_if_substantive`, the setup-plan result emission), the JSON result (`lifecycle_commit` field, error code `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`).
- **Sequencing/depends-on**: none
- **Risks**: the coordination worktree may be unmaterialized (the write-location authority establishes it or refuses with its own named error); the plan commit must stay untouched; a scaffold-only run must still commit the events recorded so far; `write_dir` must be resolved outside the best-effort `try` so a refusal is never swallowed (finalize WP15 B3 precedent).

### Folded: stranded-event report (FR-005)

Satisfied by the existing `doctor coordination` warning `COORDINATION_WORKTREE_DIRTY` (operator ruling `01M853E34H1MN0CQGQ9209P8MR`). No concern, no work package.
