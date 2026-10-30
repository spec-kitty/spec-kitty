# Work Packages: Route the remaining `kitty-specs/` walkers through the Mission predicate

**Inputs**: Design documents from `/kitty-specs/route-kitty-specs-walkers-through-the-mission-predicate-01M66YN5/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md

**Tests**: yes — the Mission spec (FR-009, SC-002/SC-004) requires one red-first behavioural test per changed walker.

**Organization**: Six walker call sites (IC-01) split across two work packages by surface, then the architectural pin and the user-facing documentation (IC-03).

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`. All paths are repo-root relative.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the shared git-aware Mission + residue fixture helper | WP01 | |
| T002 | Write red-first tests for the three doctor walkers, including the one-probe memo assertion | WP01 | [P] |
| T003 | Route `_collect_topology_rows` (`doctor topology`) through the shared walk and predicate | WP01 | |
| T004 | Route `_resolve_mission_dirs` (`doctor coordination`) through the predicate | WP01 | |
| T005 | Route `_mission_dirs_for` (`doctor review-cycle-reconcile`) through the predicate | WP01 | |
| T006 | Prove red-first and run the doctor blast radius | WP01 | |
| T007 | Write red-first tests for materialize, charter-activate and the release changelog | WP02 | [P] |
| T008 | Route `_mission_dirs_to_process` (materialize) through the predicate | WP02 | |
| T009 | Route `_collect_inflight_missions` (charter activate) through the predicate | WP02 | |
| T010 | Route `build_changelog_block` (release changelog) through the predicate | WP02 | |
| T011 | Run the WP02 blast radius | WP02 | |
| T012 | Add the architectural predicate ledger, AST check and planted-walker case | WP03 | |
| T013 | Shrink the raw-walk allowlist and classify the remaining five walkers | WP03 | |
| T014 | Update the `doctor topology` docstring and regenerate the CLI reference | WP03 | |
| T015 | Add the `[Unreleased]` changelog entry | WP03 | [P] |
| T016 | Run the full blast radius, docs freshness and ruff | WP03 | |

---

## Work Package WP01: Doctor read surfaces (Priority: P1) 🎯 MVP

**Goal**: `doctor topology`, `doctor coordination` and `doctor review-cycle-reconcile` list Missions only, decided by one predicate, proven red-first.
**Independent Test**: with the shared fixture, each of the three walks returns the Mission and not the residue child; `spec-kitty doctor topology --json` reports one mission.
**Prompt**: `tasks/WP01-doctor-read-surfaces.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-007, FR-009, NFR-001, SC-001, SC-002

### Included Subtasks

T001 Add the shared git-aware Mission + residue fixture helper
T002 [P] Write red-first tests for the three doctor walkers
T003 Route `_collect_topology_rows` (`doctor topology`) through the shared walk and predicate
T004 Route `_resolve_mission_dirs` (`doctor coordination`) through the predicate
T005 Route `_mission_dirs_for` (`doctor review-cycle-reconcile`) through the predicate
T006 Prove red-first and run the doctor blast radius

### Implementation Notes

- T001 builds `tests/_support/mission_residue_fixture.py`: one git repository, one selectable Mission
  (`meta.json` with `mission_id`, an accepted `WP01` and an in-flight `WP02` event) and one residue child
  (`spec.md` + `tasks/WP01` accepted + an in-flight `WP02` event, no `meta.json`), committed so the
  residue child is tracked and the read-side rule (not file presence) decides.
- T002 must run against the unchanged walkers and fail; capture the failing test ids for the PR.
- T003 uses `mission_resolver.iter_kitty_specs_children` + `is_selectable_mission_dir` with one
  `TrackedMissionPaths` memo; the `--mission` branch is untouched.
- T004 keeps `safe_is_dir` evaluated first so an unstattable child still raises (`#3194`).
- T005 keeps the existing comprehension and filters it.
- T006: `pytest tests/specify_cli/cli/commands/test_identity_audit.py test_coordination_doctor.py
  test_review_cycle_reconcile_doctor.py test_doctor_coordination.py -q`.

### Dependencies

- None (starting package; the predicate already exists on `main`).

### Risks & Mitigations

- Weakening the `#3194` raise → T004 evaluates `safe_is_dir` before the predicate; the existing
  unstattable-child tests stay green.
- A non-git fixture cannot exercise git-aware residue → T001 always `git init`s and commits.

---

## Work Package WP02: The remaining read surfaces (Priority: P1)

**Goal**: `materialize`, the charter-activate in-flight warning and the release-changelog block skip residue, proven red-first.
**Independent Test**: with the shared fixture (extended by WP01), each of the three surfaces yields only the Mission.
**Prompt**: `tasks/WP02-remaining-read-surfaces.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, FR-009, NFR-001, SC-002

### Included Subtasks

T007 [P] Write red-first tests for materialize, charter-activate and the release changelog
T008 Route `_mission_dirs_to_process` (materialize) through the predicate
T009 Route `_collect_inflight_missions` (charter activate) through the predicate
T010 Route `build_changelog_block` (release changelog) through the predicate
T011 Run the WP02 blast radius

### Implementation Notes

- T007 reuses `tests/_support/mission_residue_fixture.py` from WP01; keep the existing non-residue
  assertions in the same files as positive controls.
- T008 keeps the dot-directory skip and the `errors[]` contract; a residue child must produce neither a
  target nor an error entry.
- T009 derives `repo_root` as the parent of the `kitty-specs/` argument and keeps the best-effort posture.
- T010 filters the sorted `mission_dirs` before the per-mission loop.

### Dependencies

- Depends on WP01 (the shared fixture helper).

### Risks & Mitigations

- Release-changelog fixtures in `test_release_prep.py` write no `mission_id` in a non-git tmp dir → they
  stay selectable through the predicate's existence rule; do not rewrite them.

---

## Work Package WP03: One authority, enforced, and the user-facing record (Priority: P2)

**Goal**: an architectural gate that fails when any of the six walkers drops the predicate, plus the changelog entry and the CLI reference sentence that tell an operator where residue is reported.
**Independent Test**: the gate passes on the changed tree and fails on a planted walker without the predicate call; `docs/api/cli-commands.md` is fresh; the changelog entry validates.
**Prompt**: `tasks/WP03-pin-and-docs.md`
**Requirement Refs**: FR-008, SC-003, NFR-002, NFR-003, C-001

### Included Subtasks

T012 Add the architectural predicate ledger, AST check and planted-walker case
T013 Shrink the raw-walk allowlist and classify the remaining five walkers
T014 Update the `doctor topology` docstring and regenerate the CLI reference
T015 [P] Add the `[Unreleased]` changelog entry
T016 Run the full blast radius, docs freshness and ruff

### Implementation Notes

- T012 adds `_PREDICATE_ROUTED_WALKERS` (six `(module, function)` pairs), an AST test asserting each
  function body calls `is_selectable_mission_dir`, and a planted-walker case proving the checker can fail.
- T013 removes `src/specify_cli/cli/commands/_identity_audit.py` from the raw-walk allowlist (its walk is
  now the shared `iter_kitty_specs_children`) and records how each remaining allowlisted walker decides
  residue.
- T014 adds one sentence to the `topology` command docstring and regenerates
  `docs/api/cli-commands.md` with the docs script; the freshness check must report clean.
- T015 follows the changelog format: bold impact-first lead with `(#6758)`, before/after, under 1,200 chars.

### Dependencies

- Depends on WP01 and WP02 (the pin can only pass once all six route through the predicate).

### Risks & Mitigations

- Vacuity: a pin that never resolves a function name passes silently → T012 asserts each name resolves.
- Generated-docs drift → T014 regenerates and runs the freshness script in the same commit.
