# Work Packages: Align the composition-backed run advance with the engine advance

**Inputs**: Design documents from `kitty-specs/composition-advance-alignment-01M49EKF/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: required (ATDD red-first, charter SO #4).
- The acceptance gate is `tests/runtime/test_composition_advance_alignment.py`: twin-run parity through `decide_next_via_runtime`. On the base it gives 4 failed.
- WP02 commits the gate failing first, then turns it green.

**Organization**: two work packages run in sequence in the repository root checkout (`single_branch`).
- WP01 owns the engine module: the tidy-first split of `provide_decision_answer`, then the shared per-event primitives and the pre-completion guard.
- WP02 owns the adapter and the bridge call site: the behaviour change.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows, not checkboxes. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done --mission composition-advance-alignment-01M49EKF`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Characterise every `provide_decision_answer` branch through the public engine API | WP01 | |
| T002 | Split `provide_decision_answer` into helpers (≤15 each), drop `# noqa: C901` | WP01 | |
| T003 | Extract the per-event recording primitives from `_commit_advance` | WP01 | |
| T004 | Add the abort-only `before_run_completed` guard to `_commit_advance` / `commit_advance` | WP01 | |
| T005 | Engine unit tests for the primitives and the guard (order, dedupe, abort leaves state unwritten) | WP01 | [P] |
| T006 | Commit the red acceptance gate (twin-run parity) | WP02 | |
| T007 | Bridge plans the composition advance with `_engine_adapter.plan_advance(..., "success")` | WP02 | |
| T008 | Adapter commits through `_engine.commit_advance` with the retrospective guard; non-blocking capture after a terminal commit; delete the parallel planner, plan type, payload code and dead wrappers | WP02 | |
| T009 | Re-seam the adapter unit tests onto a real frozen template (no assertion removed); stale-plan test; shape gates | WP02 | |
| T010 | CHANGELOG `[Unreleased]` entry; module docstrings | WP02 | |

---

## Work Package WP01: Engine primitives and the `provide_decision_answer` split (Priority: P1)

**Goal**: the engine module holds one definition of each run-event recording, exposes an abort-only pre-completion guard on its commit path, and carries no complexity suppression. Behaviour-preserving.
**Independent test**: `pytest tests/next/test_internal_runtime_engine_coverage.py tests/next/test_internal_runtime_coverage.py tests/next/test_internal_runtime_parity.py tests/next/test_engine_commit_primitives.py tests/next/test_provide_decision_answer_characterisation.py` passes. `ruff check --select C901 src/runtime/next/_internal_runtime/engine.py` passes without the noqa.
**Prompt**: `tasks/WP01-engine-primitives-and-answer-split.md`

### Included Subtasks
- T001 Characterise every `provide_decision_answer` branch (WP01)
- T002 Split `provide_decision_answer`, drop the noqa (WP01)
- T003 Extract per-event primitives (WP01)
- T004 `before_run_completed` guard (WP01)
- T005 Engine unit tests for primitives + guard (WP01)

### Implementation sketch
Characterise first (T001, green on the base), then extract (T002). Then T003, then T004 with T005.

### Dependencies
- none

### Risks
- The MEDIUM "re-add pending" path reads the original `snapshot.pending_decisions`.
- The `DecisionAuthorityDenied` payload carries `rationale_linkage=None`.
- Event order and snapshot-write timing of `next_step` must stay byte-identical.

---

## Work Package WP02: Route the composition advance through the engine (Priority: P1)

**Goal**: a composition-backed advance records `raci:` / `significance:` decisions and the `SignificanceEvaluated` event exactly as the engine does. It keeps the single-dispatch invariant, the plan-first refusal, the retrospective gate and emitter seeding, and it refuses a stale plan.
**Independent test**: `pytest tests/runtime/test_composition_advance_alignment.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_decision_log_flush.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/next/test_mission_run_back_reference.py` passes.
**Prompt**: `tasks/WP02-route-composition-advance-through-engine.md`

### Included Subtasks
- T006 Red acceptance gate (WP02)
- T007 Bridge plans with `plan_advance` (WP02)
- T008 Adapter commits through the engine; deletions (WP02)
- T009 Re-seam adapter tests, stale-plan test, shape gates (WP02)
- T010 CHANGELOG + docstrings (WP02)

### Implementation sketch
1. Commit the gate red (T006).
2. T007 + T008 turn it green.
3. T009 restores the adapter unit suite.
4. T010 documents the change.

### Dependencies
- WP01

### Risks
- The adapter tests stub the old planner seam (squad BLOCKER); re-seam them without weakening.
- `StaleAdvancePlan` must surface as the EDGE-003 blocked Decision, never as a legacy fall-back.
- Dead symbols (`apply_result` wrapper, `_mark_step_completed`, `_live_template_path`) must be deleted.
