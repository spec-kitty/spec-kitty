# Work Packages: single_branch gate fallout (#6370, #6369)

**Inputs**: [spec.md](spec.md), [plan.md](plan.md)
**Prerequisites**: plan.md (decision record: scenario 6 assertion)

## Subtask Format: `[Txxx] [P?] Description`

## Path Conventions

Single project: `src/`, `tests/` at the repository root.

---

## Work Package WP01: Complete the single_branch e2e fixture (Priority: P0)

**Goal**: `test_single_branch_mission_survives_implement_and_merge_end_to_end` builds its mission the supported way and passes under the unchanged #5939 gate (#6370).
**Independent Test**: `.venv/bin/python -m pytest tests/specify_cli/test_specify_topology_flag.py -q` is green.
**Prompt**: `/tasks/WP01-e2e-fixture.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-001

### Included Subtasks

- [ ] T001 Record the planning commit in `_finalize_single_branch_lanes`
- [ ] T002 Seed distinct implementer and reviewer actors in `_seed_wp_approved`

### Implementation Notes

- `planning_commit_sha` = repo `HEAD` at `compute_and_write_lanes` time (what finalize-tasks captures).
- Implementing hops `implementer-ivan`; `in_review` and `approved` hops `reviewer-renata`.

### Parallel Opportunities

Independent of WP02 (disjoint files).

### Dependencies

None.

### Risks & Mitigations

- The planning commit must precede the WP code commits. `HEAD` at compute time is the create commit, which does.

---

## Work Package WP02: Align the single_branch move-side refusal wording (Priority: P0)

**Goal**: the move-side `SINGLE_BRANCH_IMPLEMENTATION_MISSING` refusal says "no implementation commit", like `for_review_gate` and the consolidate axis (#6369, scenario 6).
**Independent Test**: a focused unit test of `_mt_require_single_branch_implementation` asserts the code and the phrase; it is red on the old wording.
**Prompt**: `/tasks/WP02-refusal-wording.md`
**Requirement Refs**: FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003

### Included Subtasks

- [ ] T003 Write the focused unit test red-first
- [ ] T004 Reword the `SINGLE_BRANCH_IMPLEMENTATION_MISSING` message
- [ ] T005 Fold in #5939 consumer-audit findings within scope; report the rest

### Implementation Notes

- Message text only. Decision logic, codes and envelope are unchanged.

### Parallel Opportunities

Independent of WP01.

### Dependencies

None.

### Risks & Mitigations

- Another consumer could assert the old prose. A grep of `tests/`, `docs/` and `tests/scenarios/` found none.

---

## Dependency & Execution Summary

- **Sequence**: WP01, then WP02. single_branch runs WPs one after another in the write checkout.
- **Parallelization**: none needed (shared write checkout).
- **MVP Scope**: both (each clears one P0 nightly red).

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| NFR-001 | WP01, WP02 |
| NFR-002 | WP01, WP02 |
| C-001 | WP01, WP02 |
| C-002 | WP02 |
| C-003 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Record planning commit | WP01 | P0 | No |
| T002 | Distinct seed actors | WP01 | P0 | No |
| T003 | Red-first unit test | WP02 | P0 | No |
| T004 | Reword refusal | WP02 | P0 | No |
| T005 | Audit fold-in | WP02 | P1 | No |
