# Work Packages: Derive the mission-state audit's CI trigger list from what the audit executes

**Inputs**: Design documents from `/kitty-specs/audit-trigger-derivation-01M4RKRD/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/code-grounding.md

**Tests**: The deliverable IS a test (the derivation/non-vacuity acceptance test). ATDD-first (C-011).

**Organization**: One work package. Fine-grained subtasks (`Txxx`) roll up into `WP01`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`. The only edited file is `tests/ci/test_mission_state_audit_routing.py`.

---

## Work Package WP01: Derive the audit trigger list and remove the hand copy (Priority: P1) 🎯 MVP

**Goal**: Replace the hand-copied `AUDIT_INPUT_PATHS` mirror with a non-vacuous, self-mutation-proven test that derives the executed-module set from an in-process `run_audit` on a small git fixture and asserts each executed `src/` module is matched by the `mission_state` router group.
**Independent Test**: With a planted out-of-glob executed module (or a dropped covering glob) the new test is RED; on the real current code it is GREEN; `AUDIT_INPUT_PATHS` no longer exists as a hand copy; the `mission_state` routing tests + `make test-fast` pass.
**Prompt**: `/tasks/WP01-derive-audit-trigger-list.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002, C-003, C-004

### Included Subtasks

T001 Add the derived non-vacuity test + small git fixture (warm, function-call-scoped `sys.setprofile` over in-process `run_audit`; assert each executed `src/` module ∈ `mission_state` group via `gate_selection.load_router`/`select_gates`; same-fixture positive control) in `tests/ci/test_mission_state_audit_routing.py` — commit failing-first (witness RED via planted out-of-glob module and via dropped glob; record; do not commit the break)
T002 Remove `AUDIT_INPUT_PATHS`; re-point `test_audit_inputs_match_the_group_directly` and `test_the_reducer_bump_commit_selects_the_audit_job` onto the derived executed-module set plus a small explicit non-executed-input list (manifests, workflow, renderer) in `tests/ci/test_mission_state_audit_routing.py`
T003 Validate: run the touched routing tests by name + sibling CI-router guards + `make test-fast`; ruff + `ruff format --check --force-exclude` + mypy clean on the changed file; complexity ≤ 15

### Implementation Notes

- Reuse the single routing authority (`scripts/ci/gate_selection.load_router`/`select_gates`); never restate the globs.
- Fixture: a `tmp_path` git repo with one modern mission (`mission_id`-keyed events, a reducer-generated `status.json`, `spec.md`, `tasks/WP01.md`) so the normal audit path (classifiers + reducer) runs; ~0.01s.
- Capture: warm-up `run_audit`, then profile a second `run_audit`, recording only function-call frames (`co_name != '<module>'`) to stay deterministic.

### Dependencies

- None (starting and only package). T002 depends on T001 (derived set must exist before removing the hand copy).

### Risks & Mitigations

- Capture order-sensitivity → warm-up run + function-call frames only.
- Fixture driving an abnormal path (legacy `feature_slug`, missing `status.json`) pulling in artifact modules → modern `mission_id` events + reducer-generated `status.json`.
- Over-constraining on a fixture artifact → fixture verified to reproduce the real-corpus executed set exactly (33 modules, zero artifacts).

---

## Dependency & Execution Summary

- **Sequence**: WP01 only (T001 → T002 → T003).
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| C-004 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Derived non-vacuity test + fixture (failing-first) | WP01 | P1 | No |
| T002 | Remove hand copy; re-point consumers | WP01 | P1 | No |
| T003 | Validate (named tests, make test-fast, ruff/mypy) | WP01 | P1 | No |
