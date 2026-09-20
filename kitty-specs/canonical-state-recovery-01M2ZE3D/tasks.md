# Tasks: Canonical-State Integrity & Recovery

**Mission**: canonical-state-recovery-01M2ZE3D
**Planning base / merge target**: `fix/canonical-state-recovery` (final PR → `main`)
**Discipline**: ATDD red-first for every defect (issue-pinned `@pytest.mark.regression`, RED through the pre-existing entry point). Do NOT edit `status/models.py` or the upstream `spec_kitty_events.diary` fold. `lanes/` stays a pure domain layer (no CLI/console/policy imports). Recovery is homed in `doctor mission-state --fix`, not `agent mission repair`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: `agent tasks finalize-tasks` seeds events with **no** `lanes.json` (#4758 minting) | WP01 | |
| T002 | Extract pure `compute_and_write_lanes` → `lanes/compute_and_persist.py`; keep CLI wrapper in `mission_finalize.py` | WP01 | |
| T003 | Legacy `finalize-tasks` co-locates the `lanes.json` write (or refuses-and-delegates) via the pure core | WP01 | |
| T004 | Narrow wedge predicate (execution-begun AND lanes-absent); route finalize refusal + `MissingLanesError` message through it, naming the repair | WP01 | |
| T005 | Green + unit tests: convergence/refusal honest; pure-core determinism (NFR-004) | WP01 | |
| T006 | Blast-radius: `tests/cli/` finalize + `tests/status/` lane-compute; record counts | WP01 | |
| T007 | Red: `move-task --to doing` with no `lanes.json` currently SUCCEEDS (the escape) (#4758) | WP02 | [P] |
| T008 | Gate `move-task` from leaving `planned` when `lanes.json` absent; refusal names the repair | WP02 | [P] |
| T009 | Green + unit tests; legitimate move-task (lanes present) unaffected; protected-branch message names repair | WP02 | [P] |
| T010 | Blast-radius: `tests/cli/` move-task | WP02 | [P] |
| T011 | Red: wedged mission (execution-begun, lanes absent) — `doctor mission-state --fix` does not rebuild lanes (#4758) | WP03 | |
| T012 | Add lanes-rebuild action to `repair_repo`/`run_mission_state`, importing WP01 pure core + shared wedge predicate; rebuild ONLY when wedge holds (preserve #3311) | WP03 | |
| T013 | Green e2e: reproduce wedge → repair → advance WP to approval; NFR-001 advanceable-or-repairable + NFR-002 parity + NFR-004 idempotence | WP03 | |
| T014 | Blast-radius: `tests/unit/migration/` + `tests/cli/` doctor mission-state | WP03 | |
| T015 | Red: #4786 rejection-cycle repro → `accept` blocks "missing agent" (RED through `accept`) | WP04 | [P] |
| T016 | Add `_project_implementer_attribution` to `status/reducer.py` (mirror `_project_cancellation_provenance`); derive durable provenance from the raw event log | WP04 | [P] |
| T017 | `summary_core.py` reads the derived slot via one shared family accessor; gate passes for released-but-owned, refuses honestly for never-owned | WP04 | [P] |
| T018 | Narrow `status/doctor.py:215-240` blanked-slot detector to genuine on-disk `agent: ""`; reword recommended-action | WP04 | [P] |
| T019 | Guard `merge.py:259/456` `(mission or "").strip()` against an unresolved `OptionInfo` default (FR-008) | WP04 | [P] |
| T020 | Green: repro reaches `accept` clean via derivation; never-owned still refuses; projection idempotent/read-only | WP04 | [P] |
| T021 | CHANGELOG `[Unreleased]` entry (#4758 #4786), no version bump | WP04 | [P] |
| T022 | Blast-radius: `tests/status/` + `tests/acceptance/` | WP04 | [P] |

## Work Packages

### WP01 — #4758 finalize minting + pure-core extraction + wedge predicate
- **Goal**: legacy `agent tasks finalize-tasks` never leaves events-seeded-without-lanes; extract the pure lane-compute core so recovery can reuse it; introduce the narrow wedge predicate shared with WP03.
- **Priority**: P1. **Requirements**: FR-001, NFR-004, C-001, C-003.
- **Independent test**: `agent tasks finalize-tasks` then check `lanes.json` exists (or the command refused and named the canonical path).
- **Subtasks**: T001–T006. **Depends on**: none. **Prompt**: [tasks/WP01-finalize-minting-and-extraction.md](./tasks/WP01-finalize-minting-and-extraction.md)

### WP02 — #4758 move-task planned-boundary guard
- **Goal**: `move-task` refuses to move a WP out of `planned` when `lanes.json` is absent, naming the repair — defense in depth for the wedge.
- **Priority**: P1. **Requirements**: FR-002, FR-006, C-003.
- **Independent test**: `move-task --to doing` with no `lanes.json` refuses with a message naming `doctor mission-state --fix`.
- **Subtasks**: T007–T010. **Depends on**: none. **Prompt**: [tasks/WP02-move-task-planned-guard.md](./tasks/WP02-move-task-planned-guard.md)

### WP03 — Canonical-state recovery (lanes rebuilder in `doctor mission-state --fix`)
- **Goal**: one documented action rebuilds `lanes.json` from the event log when the wedge predicate holds, reusing WP01's pure core; never rewrites existing lanes.
- **Priority**: P1. **Requirements**: FR-003, FR-006, NFR-001, NFR-002, NFR-004, C-002, C-003.
- **Independent test**: reproduce the #4758 wedge, run `doctor mission-state --fix --mission X`, then advance the WP through approval.
- **Subtasks**: T011–T014. **Depends on**: WP01 (imports the extracted pure core + shared wedge predicate). **Prompt**: [tasks/WP03-recovery-lanes-rebuild.md](./tasks/WP03-recovery-lanes-rebuild.md)

### WP04 — #4786 attribution projection + accept read-side + detector + merge guard
- **Goal**: derive durable implementer provenance at the read-root (`status/reducer.py`), so an ordinary rejection cycle no longer blocks `accept`; unify the accept-gate metadata family; narrow the blanked-slot detector; guard the merge slug path.
- **Priority**: P1. **Requirements**: FR-004, FR-005, FR-006, FR-007, FR-008, C-003, C-004.
- **Independent test**: reject→re-review→approve without `--agent`, then `accept` clean; a never-owned WP still refuses honestly.
- **Subtasks**: T015–T022. **Depends on**: none. **Prompt**: [tasks/WP04-attribution-projection-and-readside.md](./tasks/WP04-attribution-projection-and-readside.md)

## Dependency Summary
```
WP01 → WP03      WP02 ∥ WP04 ∥ WP01
```
