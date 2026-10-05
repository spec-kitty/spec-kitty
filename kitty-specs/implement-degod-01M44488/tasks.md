# Work Packages: Implement command degod (tidy-first)

**Inputs**: Design documents from `kitty-specs/implement-degod-01M44488/`
**Prerequisites**: plan.md, spec.md, research.md (R-1…R-6), data-model.md, contracts/seam-decisions.md, quickstart.md, research/code-grounding.md, research/test-remediation.md

**Tests**: required. The spec makes tests part of the deliverable (FR-009..FR-015, SC-002, SC-003, SC-005).

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`).
- WP01–WP11 form one dependency-ordered chain over the same hot file, in a single lane. The
  ownership validator exempts dependency-ordered pairs from the overlap rule.
- WP12 is a planning-artifact package.
- This structure follows the post-tasks squad (research.md §Squad dispositions).

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are **reference rows**. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/specify_cli/…`, `tests/…`. Every WP prompt carries the mission-level binding rules:
- move, then adjust;
- call style;
- ownership leeway for mechanical re-points;
- dispatch-map scope;
- characterization immutability;
- the #5699 failing-set check;
- the no-CLI import guard;
- NFR-003 per WP.

---

## Work Package WP01: Patch-liveness gate for the implement family and vacuous-test repair (Priority: P0)

**Goal**: Make stale patches into the implement family fail loudly (per-family gate with the attribute rule and a dispatch-map hook) and repair the four vacuous tests, before any move.
**Independent Test**: The widened gate is green on the base; planted dead-patch and attribute-rule controls are proven; the FR-013 planted breaks are logged.
**Prompt**: `tasks/WP01-liveness-gate-and-vacuous-tests.md`
**Requirement Refs**: FR-010, FR-013

### Included Subtasks

T001 Generalize the liveness gate to per-family config: package, glob, test pre-filter, attribute rule
T002 Dispatch-map liveness hook (skips until WP02 creates the map), unit-tested with a planted dead entry
T003 Repair or retire the 4 vacuous tests with planted-break proofs
T004 Evidence: counter baseline, gate results, plants

### Dependencies

- None (starting package).

---

## Work Package WP02: Characterization suite through public entry points (Priority: P0)

**Goal**: Pin every refusal family, the side-effect order, #4888, the claim-commit exception table, `--json`, the programmatic call and recover through public entry points; then freeze the suite.
**Independent Test**: Green on the base; a planted break per family; no implement internals named; ≤ 60 s.
**Prompt**: `tasks/WP02-characterization-suite.md`
**Requirement Refs**: FR-009, FR-014, SC-003

### Included Subtasks

T005 Dispatch map + real-git fixture builders
T006 Refusal families incl. DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN, CorruptLanesError, bulk-edit, checkout identity, structural, demotion, WRITE_CHECKOUT_*, --base
T007 Side-effect order, #4888 messages, claim-commit exception table
T008 --json payloads, programmatic call (mirrors workflow.py), --recover
T009 Planted-break proofs; activate the dispatch-map gate hook; freeze

### Dependencies

- Depends on WP01.

---

## Work Package WP03: Context and dependency gate into their seams (Priority: P1)

**Goal**: Move the WP-file lookup, the lane-state dir and the target-branch read into `workspace/context.py`, and the claim-precondition decision into `core/dependency_graph.py` (pure, snapshot in).
**Independent Test**: Seam unit tests without the CLI; characterization unedited and green.
**Prompt**: `tasks/WP03-context-and-dependency-gate.md`
**Requirement Refs**: FR-003, FR-006, FR-012, NFR-002

### Included Subtasks

T010 Verbatim move of the context reads into workspace/context.py
T011 Move the claim-precondition decision into core/dependency_graph.py (pure)
T012 Adjust: renames (resolve_lane_state_dir, resolve_mission_target_branch), re-exports, allow-list row, strict typing incl. 2 pre-existing errors
T013 Seam unit tests (claim preconditions, workspace reads)
T014 Re-point tests and gates; no-CLI import guard; plants

### Dependencies

- Depends on WP02.

---

## Work Package WP04: Planning-commit decisions into the coordination seam (Priority: P1)

**Goal**: Move the pure planning-commit decisions (partition, guard, demotion verdict, identifier cascade, candidate enumeration) into `coordination/planning_commit.py`.
**Independent Test**: Seam unit tests; no-CLI guard proven; #5699 failing set unchanged; characterization unedited and green.
**Prompt**: `tasks/WP04-planning-commit-seam.md`
**Requirement Refs**: FR-004, FR-012

### Included Subtasks

T015 Verbatim move into coordination/planning_commit.py
T016 Adjust: public renames, re-exports, strict typing, test re-points
T017 Gates: CHURN/TRIO/WRITE_DIR/mid8/meta census/cutover/terminology, no-CLI guard, test_commit_recipes re-key; plants
T018 Seam unit tests test_planning_commit.py
T019 Evidence

### Dependencies

- Depends on WP03.

---

## Work Package WP05: Planning-commit adapter out of the command module (Priority: P1)

**Goal**: Move the printing / transaction adapter into `cli/commands/implement_planning_commit.py`, and `_git_stdout` into `lanes/implement_support.py`.
**Independent Test**: No circular import; characterization, e2e smoke and coord smokes green.
**Prompt**: `tasks/WP05-planning-commit-adapter.md`
**Requirement Refs**: FR-004, FR-012, NFR-005

### Included Subtasks

T020 Verbatim move of the adapter + git_stdout
T021 Adjust: re-exports, the implement_cores shim, strict typing
T022 Re-point test imports and patches (mechanical)
T023 Gates: partition_call_shape _IMPLEMENT, CHURN/TRIO/WRITE_DIR, terminology; plants
T024 Smokes (e2e #3371, wp_integrity) and evidence

### Dependencies

- Depends on WP04.

---

## Work Package WP06: #5232 seam-owned planning placement (B2*) (Priority: P1)

**Goal**: Replace the meta-derived placement fallback with a typed `PlanningPlacement` resolved by the coordination seam (research R-1), with no reachable outcome change.
**Independent Test**: FR-015 rows identical before and after, including lifecycle rows; planted adapter-wiring break; INV-7 re-keyed.
**Prompt**: `tasks/WP06-seam-owned-placement.md`
**Requirement Refs**: FR-008, FR-015, FR-018, SC-004, C-007

### Included Subtasks

T025 FR-015 reachability tests (behavioural rows green on base; new-API unit tests red), committed alone
T026 PlanningPlacement + resolve_planning_placement
T027 Rewire adapter arms on the typed placement; delete the None overload and the meta placement read
T028 One remedy definition; retire the _resolve_placement_ref None contract; reuse or delete _resolve_claim_commit_target
T029 Rewrite the None-path tests; re-key INV-7; re-point the write_intent pin

### Dependencies

- Depends on WP05.

---

## Work Package WP07: Lane selection and allocation preflight into the lanes seam (Priority: P1)

**Goal**: Move lane lookup, origin-preferred base resolution, the repo-root refusal and the VCS-lock decision into `lanes/implement_support.py` with typed errors; the command keeps texts and order.
**Independent Test**: Seam tests; base-flag and refusal suites green with mechanical re-points only.
**Prompt**: `tasks/WP07-lane-selection-seam.md`
**Requirement Refs**: FR-005, FR-012, C-006

### Included Subtasks

T030 Verbatim move into lanes/implement_support.py
T031 Adjust: BaseRefUnresolved caught inline inside the create try; CLI-side _validate_base_ref kept
T032 VCS-lock decision ensure_vcs_locked
T033 Seam unit tests + mechanical re-points
T034 Gates and plants

### Dependencies

- Depends on WP06.

---

## Work Package WP08: Claim recording seam (Priority: P1)

**Goal**: Move claim preflight, status start and the claim commit into `cli/commands/implement_claim.py`; extract the pure `claim_commit_paths` (shapes #5673); dedupe the claim policy metadata into the status facade.
**Independent Test**: Seam tests incl. the propagate/soften table; in-matrix status tests; characterization unedited and green.
**Prompt**: `tasks/WP08-claim-recording-seam.md`
**Requirement Refs**: FR-007, FR-012

### Included Subtasks

T035 Verbatim move into implement_claim.py
T036 Extract claim_commit_paths
T037 Shared claim_policy_metadata (avoid the F823 local-name trap)
T038 Re-point the WS#3 allow-list + twin, the source pin, 610/4665 tests
T039 Seam tests test_implement_claim.py

### Dependencies

- Depends on WP07.

---

## Work Package WP09: Thin command and phase sequence (Priority: P1)

**Goal**: `implement()` becomes Typer parsing plus calls into `implement_phases.py` (phase functions take `repo_root` and context as parameters); `--recover` moves to `implement_recover.py`; `implement.py` ≤ 800 lines.
**Independent Test**: Phase-order test; mandatory bulk-edit, operational-context and presentation tests; characterization, programmatic and JSON suites green; C901 < 15.
**Prompt**: `tasks/WP09-thin-command-and-phases.md`
**Requirement Refs**: FR-001, FR-002, FR-014, NFR-001, NFR-002, SC-001

### Included Subtasks

T040 implement_phases.py: phase values + verbatim phase functions (+ detect_feature_context)
T041 implement_recover.py
T042 Thin implement(); signature and decorators unchanged
T043 Phase-order test + mandatory SC-005 tests; re-point source pins
T044 Quarantine decision, gate widening, wc -l

### Dependencies

- Depends on WP08.

---

## Work Package WP10: Migrate test_implement_command.py onto seams and phases (Priority: P2)

**Goal**: Rewrite the MagicMock-graph orchestration tests into phase or seam tests with real values.
**Independent Test**: The file's family patch sites ≤ 5; every retirement names a green replacement.
**Prompt**: `tasks/WP10-migrate-implement-command-tests.md`
**Requirement Refs**: FR-011, SC-002, SC-005

### Included Subtasks

T045 Per-target reduction plan; context classes
T046 TestImplementCommand migration, one test at a time
T047 Evidence

### Dependencies

- Depends on WP09.

---

## Work Package WP11: Remaining test migration, docs, changelog and closing measurements (Priority: P2)

**Goal**: Migrate the remaining class-A/B files, re-point the docs (including the shipped git-operations matrix), add the CHANGELOG entry and close SC-002 / SC-005 / NFR-003.
**Independent Test**: Counter ≤ 45; SC-005 table; NFR-003 met; docs fresh.
**Prompt**: `tasks/WP11-remaining-migration-docs-measurements.md`
**Requirement Refs**: FR-011, FR-016, SC-002, SC-005, NFR-003, NFR-004, NFR-006

### Included Subtasks

T048 Migrate the remaining class-A/B files
T049 Docs + CHANGELOG
T050 Coverage-breadth baseline + format-exclude entries
T051 Closing measurements

### Dependencies

- Depends on WP10.

---

## Work Package WP12: Issue matrix and follow-ups (Priority: P2)

**Goal**: Record the issue-matrix rows and file the follow-ups (including deferred test-remediation items).
**Independent Test**: Matrix rows with verdicts; follow-up numbers recorded.
**Prompt**: `tasks/WP12-issue-matrix-and-follow-ups.md`
**Requirement Refs**: FR-017

### Included Subtasks

T052 Issue matrix
T053 Draft and file follow-ups

### Dependencies

- Depends on WP11.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → … → WP11 → WP12 (one lane).
- **Parallelization**: within a WP only.
- **MVP scope**: WP01 + WP02 (the safety net).

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| C-006 | WP07 |
| C-007 | WP06 |
| FR-001 | WP09 |
| FR-002 | WP09 |
| FR-003 | WP03 |
| FR-004 | WP04, WP05 |
| FR-005 | WP07 |
| FR-006 | WP03 |
| FR-007 | WP08 |
| FR-008 | WP06 |
| FR-009 | WP02 |
| FR-010 | WP01 |
| FR-011 | WP10, WP11 |
| FR-012 | WP03, WP04, WP05, WP07, WP08 |
| FR-013 | WP01 |
| FR-014 | WP02, WP09 |
| FR-015 | WP06 |
| FR-016 | WP11 |
| FR-017 | WP12 |
| FR-018 | WP06 |
| NFR-001 | WP09 |
| NFR-002 | WP03, WP09 |
| NFR-003 | WP11 |
| NFR-004 | WP11 |
| NFR-005 | WP05 |
| NFR-006 | WP11 |
| SC-001 | WP09 |
| SC-002 | WP10, WP11 |
| SC-003 | WP02 |
| SC-004 | WP06 |
| SC-005 | WP10, WP11 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Generalize the liveness gate to per-family config: package, glob, test pre-filter, attribute rule | WP01 | P0 | No |
| T002 | Dispatch-map liveness hook (skips until WP02 creates the map), unit-tested with a planted dead entry | WP01 | P0 | No |
| T003 | Repair or retire the 4 vacuous tests with planted-break proofs | WP01 | P0 | No |
| T004 | Evidence: counter baseline, gate results, plants | WP01 | P0 | No |
| T005 | Dispatch map + real-git fixture builders | WP02 | P0 | No |
| T006 | Refusal families incl. DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN, CorruptLanesError, bulk-edit, checkout identity, structural, demotion, WRITE_CHECKOUT_*, --base | WP02 | P0 | No |
| T007 | Side-effect order, #4888 messages, claim-commit exception table | WP02 | P0 | No |
| T008 | --json payloads, programmatic call (mirrors workflow.py), --recover | WP02 | P0 | No |
| T009 | Planted-break proofs; activate the dispatch-map gate hook; freeze | WP02 | P0 | No |
| T010 | Verbatim move of the context reads into workspace/context.py | WP03 | P1 | No |
| T011 | Move the claim-precondition decision into core/dependency_graph.py (pure) | WP03 | P1 | No |
| T012 | Adjust: renames (resolve_lane_state_dir, resolve_mission_target_branch), re-exports, allow-list row, strict typing incl. 2 pre-existing errors | WP03 | P1 | No |
| T013 | Seam unit tests (claim preconditions, workspace reads) | WP03 | P1 | No |
| T014 | Re-point tests and gates; no-CLI import guard; plants | WP03 | P1 | No |
| T015 | Verbatim move into coordination/planning_commit.py | WP04 | P1 | No |
| T016 | Adjust: public renames, re-exports, strict typing, test re-points | WP04 | P1 | No |
| T017 | Gates: CHURN/TRIO/WRITE_DIR/mid8/meta census/cutover/terminology, no-CLI guard, test_commit_recipes re-key; plants | WP04 | P1 | No |
| T018 | Seam unit tests test_planning_commit.py | WP04 | P1 | No |
| T019 | Evidence | WP04 | P1 | No |
| T020 | Verbatim move of the adapter + git_stdout | WP05 | P1 | No |
| T021 | Adjust: re-exports, the implement_cores shim, strict typing | WP05 | P1 | No |
| T022 | Re-point test imports and patches (mechanical) | WP05 | P1 | No |
| T023 | Gates: partition_call_shape _IMPLEMENT, CHURN/TRIO/WRITE_DIR, terminology; plants | WP05 | P1 | No |
| T024 | Smokes (e2e #3371, wp_integrity) and evidence | WP05 | P1 | No |
| T025 | FR-015 reachability tests (behavioural rows green on base; new-API unit tests red), committed alone | WP06 | P1 | No |
| T026 | PlanningPlacement + resolve_planning_placement | WP06 | P1 | No |
| T027 | Rewire adapter arms on the typed placement; delete the None overload and the meta placement read | WP06 | P1 | No |
| T028 | One remedy definition; retire the _resolve_placement_ref None contract; reuse or delete _resolve_claim_commit_target | WP06 | P1 | No |
| T029 | Rewrite the None-path tests; re-key INV-7; re-point the write_intent pin | WP06 | P1 | No |
| T030 | Verbatim move into lanes/implement_support.py | WP07 | P1 | No |
| T031 | Adjust: BaseRefUnresolved caught inline inside the create try; CLI-side _validate_base_ref kept | WP07 | P1 | No |
| T032 | VCS-lock decision ensure_vcs_locked | WP07 | P1 | No |
| T033 | Seam unit tests + mechanical re-points | WP07 | P1 | No |
| T034 | Gates and plants | WP07 | P1 | No |
| T035 | Verbatim move into implement_claim.py | WP08 | P1 | No |
| T036 | Extract claim_commit_paths | WP08 | P1 | No |
| T037 | Shared claim_policy_metadata (avoid the F823 local-name trap) | WP08 | P1 | No |
| T038 | Re-point the WS#3 allow-list + twin, the source pin, 610/4665 tests | WP08 | P1 | No |
| T039 | Seam tests test_implement_claim.py | WP08 | P1 | No |
| T040 | implement_phases.py: phase values + verbatim phase functions (+ detect_feature_context) | WP09 | P1 | No |
| T041 | implement_recover.py | WP09 | P1 | No |
| T042 | Thin implement(); signature and decorators unchanged | WP09 | P1 | No |
| T043 | Phase-order test + mandatory SC-005 tests; re-point source pins | WP09 | P1 | No |
| T044 | Quarantine decision, gate widening, wc -l | WP09 | P1 | No |
| T045 | Per-target reduction plan; context classes | WP10 | P2 | No |
| T046 | TestImplementCommand migration, one test at a time | WP10 | P2 | No |
| T047 | Evidence | WP10 | P2 | No |
| T048 | Migrate the remaining class-A/B files | WP11 | P2 | No |
| T049 | Docs + CHANGELOG | WP11 | P2 | No |
| T050 | Coverage-breadth baseline + format-exclude entries | WP11 | P2 | No |
| T051 | Closing measurements | WP11 | P2 | No |
| T052 | Issue matrix | WP12 | P2 | No |
| T053 | Draft and file follow-ups | WP12 | P2 | No |
