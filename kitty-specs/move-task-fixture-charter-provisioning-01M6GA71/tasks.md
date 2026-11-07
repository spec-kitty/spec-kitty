# Work Packages: Provision the move-task git-validation fixture's charter (#7073)

**Inputs**: Design documents from `/kitty-specs/move-task-fixture-charter-provisioning-01M6GA71/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required — this mission is itself a test-fidelity fix; the red-first regression pair is the deliverable.

**Organization**: One work package. The change is two fixture lines plus a new regression test class in a single
test module, and a changelog fragment.

**Prompt Files**: `tasks/WP01-provision-fixture-charter.md`

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `tests/`, `docs/`.

---

## Work Package WP01: Provision the fixture's charter and pin it red-first (Priority: P0)

**Goal**: `git_repo_with_worktree` builds a provisioned project, so the review-ward guard reads the resolved
`software-dev` mission-type profile instead of `code_producing_for`'s caught-exception built-in fallback, and a
regression test fails if the fixture ever goes back to being unprovisioned.
**Independent Test**: `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py`
— the two new tests go from red (`UnknownMissionTypeError` / fallback WARNING) to green, and the 15 pre-existing
node ids, decorators, assertions and fail/pass set are unchanged.
**Prompt**: `/tasks/WP01-provision-fixture-charter.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Record the base red: run the module on the planning base and capture the 8 `IMPLEMENTATION_MISSING` failures plus the `UnknownMissionTypeError` fallback traceback in the output
T002 [P] Add the red-first regression pair (resolve the fixture's mission type; assert the capability read logs no fallback record) to `tests/tasks/test_move_task_git_validation_unit.py` and record their red output
T003 Provision `git_repo_with_worktree` through `tests/_factories.provision_test_charter` before the fixture's `Initial commit`
T004 Prove non-vacuity: re-run green, then revert the provisioning call and show both new tests fail again; confirm the node set (15 ids) and the fail/pass set are unchanged
T005 [P] Run the module's lint/format/type gates (`ruff check`, `ruff format --check`, `mypy`) on the branch and on the base; record 0 new findings
T006 [P] Add `docs/changelog/unreleased/<pr>.internal.md` and pass `check_changelog_style` + `check_spelling --pass unreleased`

### Implementation Notes

- Import `provision_test_charter` from `tests._factories` (production-delegating wrapper over
  `specify_cli.provisioning.default_charter.provision_default_mission_type_activations`); never hand-write the
  activation key.
- Provision **after** `.kittify/config.yaml` is written and **before** `git add .` / `Initial commit`, so the
  activation ledger lands in the first commit and the fixture's commit shape is unchanged.
- Pin on the absence of the `charter.activation.mission_type_profiles` fallback record, not on
  `code_producing_for`'s boolean (identical before and after the fix).

### Parallel Opportunities

- T002 and T005/T006 touch different files; T001 is a recorded run, not a code change.

### Dependencies

- None (single package).

### Risks & Mitigations

- **Collision with PR #7100** in the same helper → keep hunks disjoint (mine: the `config.yaml` write region and
  an appended test class; #7100: WP01 frontmatter, lane commit, one `--agent` flag).
- **Vacuous pin** (`code_producing_for` is `True` either way) → assert the resolved bundle and the absence of the
  fallback log record.
- **Commit-shape drift** → provisioning before the first commit; verify the auto-commit and commit-history nodes
  still behave identically.

---

## Dependency & Execution Summary

- **Sequence**: T001 → T002 → T003 → T004 → T005/T006.
- **Parallelization**: T005 and T006 can run alongside T004 once the code change is in place.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Record the base red and the fallback traceback | WP01 | P0 | No |
| T002 | Add the red-first regression pair | WP01 | P0 | Yes |
| T003 | Provision the fixture via the production provisioner | WP01 | P0 | No |
| T004 | Prove non-vacuity and behaviour parity | WP01 | P0 | No |
| T005 | Lint / format / type gates, base vs branch | WP01 | P0 | Yes |
| T006 | Changelog fragment plus style and spelling checks | WP01 | P0 | Yes |
