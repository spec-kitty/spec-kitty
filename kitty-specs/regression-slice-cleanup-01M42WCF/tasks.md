# Work Packages: Regression-slice test cleanup

**Inputs**: `kitty-specs/regression-slice-cleanup-01M42WCF/` (spec.md, plan.md, research.md, data-model.md, quickstart.md)
**Prerequisites**: plan.md, spec.md

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`), one or two per issue / code domain. Subtask rows are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the `_load_charter_scope_config` unit test (priority, red-first) | WP01 | [P] |
| T002 | Retire or unmark the #4600 CLI replay | WP01 | [P] |
| T003 | RETIRE the #5513 coord-only dirty status-log file | WP01 | [P] |
| T004 | FIX + unmark the #5440 coord status placement file | WP01 | [P] |
| T005 | Validate and record evidence | WP01 | [P] |
| T006 | Add dispatch-mode unit tests for meta corruption | WP02 | [P] |
| T007 | Trim `test_next_meta_corruption.py` to one CLI smoke | WP02 | [P] |
| T008 | SPLIT-BY-KIND `tests/integration/test_single_branch_write_checkout_e2e.py` | WP02 | [P] |
| T009 | Unmark `TestIsReviewRejectionEdge` in the trio characterization file | WP02 | [P] |
| T010 | Validate and record evidence | WP02 | [P] |
| T011 | SPLIT-BY-KIND the four ledger files | WP03 | [P] |
| T012 | MARKER-ONLY two files | WP03 | [P] |
| T013 | SHIFT-LEFT #4962: port case 3, then retire the subprocess file | WP03 | [P] |
| T014 | RETIRE T030 in the status-event row-shape test | WP03 | [P] |
| T015 | Validate and record evidence | WP03 | [P] |
| T016 | MARKER-ONLY batch | WP04 | [P] |
| T017 | Fix wrong tier co-marks on KEEP files | WP04 | [P] |
| T018 | SPLIT-BY-KIND `test_auth_saas_target_cleanup.py` | WP04 | [P] |
| T019 | SPLIT-BY-KIND `test_tasks_move_task_seam.py` | WP04 | [P] |
| T020 | SPLIT-BY-KIND `charter/test_recompile_preserves_mission_4908.py` | WP04 | [P] |
| T021 | Validate and record evidence | WP04 | [P] |
| T022 | Seam units for `_partition_paths_by_primary_kind` | WP05 | [P] |
| T023 | Trim `test_issue_4905_coord_staging.py` to 1–2 e2e | WP05 | [P] |
| T024 | Seam units for `_slugify_feature_input` | WP05 | [P] |
| T025 | Trim `test_specify_json_nonascii.py` to one `--json` e2e | WP05 | [P] |
| T026 | FIX the #2745 oracle | WP05 | [P] |
| T027 | Validate and record evidence | WP05 | [P] |
| T028 | MARKER-ONLY batch | WP06 | [P] |
| T029 | SPLIT-BY-KIND `test_traces_driver_section_union_4894.py` | WP06 | [P] |
| T030 | #5569 units: deleted-branch REFUSE and approved-dependency PASS | WP06 | [P] |
| T031 | Attestation units moved from the mixed-lane fail/attestation e2e | WP06 | [P] |
| T032 | Validate and record evidence | WP06 | [P] |
| T033 | Rollback/abort family: B1–B5 | WP07 | [P] |
| T034 | Claim-refusal ordering: B6 | WP07 | [P] |
| T035 | Canceled-content verdict families: B7, B8 | WP07 | [P] |
| T036 | Lanes families: B9 | WP07 | [P] |
| T037 | Validate, time and record evidence | WP07 | [P] |
| T038 | Reproduce as root | WP08 | [P] |
| T039 | Fix `test_preparation_refuses_broken_required_inputs[unreadable]` | WP08 | [P] |
| T040 | Fix `test_resolve_charter_path_raises_when_directory_not_readable` | WP08 | [P] |
| T041 | Sweep the two files for other chmod-unreadable tests and validate | WP08 | [P] |
| T042 | Reproduce the 16 root failures | WP09 | [P] |
| T043 | Inject the failure at the I/O seam (preferred) | WP09 | [P] |
| T044 | Skip under root only where no single seam exists | WP09 | [P] |
| T045 | Planted breaks and validation | WP09 | [P] |

---

## Work Package WP01: Charter scope-config guard and status/coordination pins (#5620 part 1) (Priority: P1)

**Goal**: Guard the #4600 fix at its seam (the only unguarded fix in the slice), then retire or unmark the CLI replay that cannot guard it, retire the folded #5513 file, and FIX+unmark the #5440 file.
**Independent Test**: Planting `return None` in place of `raise CharterPackConfigError` in `src/charter/activation/scope.py::_load_charter_scope_config` turns the new unit test file red.
**Prompt**: `tasks/WP01-charter-scope-guard-and-status-pins.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008, C-001, C-005

### Included Subtasks

T001 Add the `_load_charter_scope_config` unit test (priority, red-first) (WP01)
T002 Retire or unmark the #4600 CLI replay (WP01)
T003 RETIRE the #5513 coord-only dirty status-log file (WP01)
T004 FIX + unmark the #5440 coord status placement file (WP01)
T005 Validate and record evidence (WP01)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~270 lines

---

## Work Package WP02: next meta-corruption shift-left, single-branch e2e split, trio unmark (#5620 part 2) (Priority: P2)

**Goal**: Move the #4642 meta-corruption pins to stub-level units at the `next_cmd` dispatch seams, split the single-branch write-checkout e2e to its non-redundant core, and unmark a pure truth table.
**Independent Test**: Removing both `except MissionMetaReadError` arms in `src/specify_cli/cli/commands/next_cmd.py` turns the new unit file red.
**Prompt**: `tasks/WP02-next-meta-shift-left-and-single-branch-split.md`
**Requirement Refs**: FR-003, FR-008, NFR-001, NFR-002, C-001, C-005

### Included Subtasks

T006 Add dispatch-mode unit tests for meta corruption (WP02)
T007 Trim `test_next_meta_corruption.py` to one CLI smoke (WP02)
T008 SPLIT-BY-KIND `tests/integration/test_single_branch_write_checkout_e2e.py` (WP02)
T009 Unmark `TestIsReviewRejectionEdge` in the trio characterization file (WP02)
T010 Validate and record evidence (WP02)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~270 lines

---

## Work Package WP03: Migration/upgrade/charter marker splits, #4962 port, T030 retire (#5621) (Priority: P2)

**Goal**: Stop the stale module-level `regression` marker (the dead '#2957 main-push collection' reason) from spreading onto non-pins; port the one non-redundant #4962 subprocess case to the migration unit file and retire the subprocess file; retire T030.
**Independent Test**: `pytest <the 9 files> -m regression --collect-only` drops from 66 to only the ledger-named pins; the #4962 tie-break planted break reds the migration unit file.
**Prompt**: `tasks/WP03-migration-upgrade-charter-markers.md`
**Requirement Refs**: FR-004, FR-008, C-001, C-004, C-005

### Included Subtasks

T011 SPLIT-BY-KIND the four ledger files (WP03)
T012 MARKER-ONLY two files (WP03)
T013 SHIFT-LEFT #4962: port case 3, then retire the subprocess file (WP03)
T014 RETIRE T030 in the status-event row-shape test (WP03)
T015 Validate and record evidence (WP03)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~270 lines

---

## Work Package WP04: CLI marker-only batch and SPLIT-BY-KIND files (#5619 part 1) (Priority: P2)

**Goal**: Remove the `regression` mislabel from CLI unit/component/contract tests and split mixed files, per the #5619 ledger.
**Independent Test**: `--collect-only -m regression` over the owned files selects only the ledger KEEP pins; the 4 AST pins of `test_auth_saas_target_cleanup.py` are retired with planted break B re-proved.
**Prompt**: `tasks/WP04-cli-marker-only-and-splits.md`
**Requirement Refs**: FR-005, FR-008, C-001, C-004

### Included Subtasks

T016 MARKER-ONLY batch (WP04)
T017 Fix wrong tier co-marks on KEEP files (WP04)
T018 SPLIT-BY-KIND `test_auth_saas_target_cleanup.py` (WP04)
T019 SPLIT-BY-KIND `test_tasks_move_task_seam.py` (WP04)
T020 SPLIT-BY-KIND `charter/test_recompile_preserves_mission_4908.py` (WP04)
T021 Validate and record evidence (WP04)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~300 lines

---

## Work Package WP05: CLI seam units, 4905/non-ASCII shift-left, 2745 oracle fix (#5619 part 2) (Priority: P2)

**Goal**: Add the missing seam unit tests for `workflow._partition_paths_by_primary_kind` and `lifecycle._slugify_feature_input`, then trim the 210 s #4905 file and the non-ASCII e2e to their smokes, and tighten the #2745 disjunctive oracle.
**Independent Test**: Planted break D (skip the partition) reds the new partition unit file; a slug break reds the new slug unit file; the tightened #2745 oracle goes red when the MissingLanes refusal is replaced by any other error mentioning 'required'.
**Prompt**: `tasks/WP05-cli-seam-units-4905-nonascii-2745.md`
**Requirement Refs**: FR-005, FR-008, NFR-001, NFR-002, C-001, C-005

### Included Subtasks

T022 Seam units for `_partition_paths_by_primary_kind` (WP05)
T023 Trim `test_issue_4905_coord_staging.py` to 1–2 e2e (WP05)
T024 Seam units for `_slugify_feature_input` (WP05)
T025 Trim `test_specify_json_nonascii.py` to one `--json` e2e (WP05)
T026 FIX the #2745 oracle (WP05)
T027 Validate and record evidence (WP05)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~300 lines

---

## Work Package WP06: Consolidation/lanes marker fixes and #5569 seam units (#5618 part 1) (Priority: P2)

**Goal**: Drop the mislabel from the 8 MARKER-ONLY files, split the #4894 file, add the #5569 deleted-branch REFUSE and approved-dependency PASS units, and move the 3 attestation-level tests of the mixed-lane fail/attestation e2e into `test_canceled_attestation.py`.
**Independent Test**: Planted break B8 (`never_exempt` no longer subtracted) reds ≥2 tests in `tests/consolidation/test_canceled_dependency_lane.py` instead of 1.
**Prompt**: `tasks/WP06-consolidation-markers-and-5569-units.md`
**Requirement Refs**: FR-006, FR-008, C-001, C-004, C-005

### Included Subtasks

T028 MARKER-ONLY batch (WP06)
T029 SPLIT-BY-KIND `test_traces_driver_section_union_4894.py` (WP06)
T030 #5569 units: deleted-branch REFUSE and approved-dependency PASS (WP06)
T031 Attestation units moved from the mixed-lane fail/attestation e2e (WP06)
T032 Validate and record evidence (WP06)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~270 lines

---

## Work Package WP07: Terminus/lanes SHIFT-LEFT trims to one smoke per family (#5618 part 2) (Priority: P2)

**Goal**: Cut ≈820 s of summed per-PR runtime by trimming the slow consolidate/abort replays to one smoke per behaviour family, after re-proving each covering seam guard with the ledger's planted breaks B1–B9.
**Independent Test**: For each trimmed family the named seam guard goes RED on the matching planted break (B1–B9) and the kept smoke passes on the clean tree.
**Prompt**: `tasks/WP07-terminus-lanes-shift-left-trims.md`
**Requirement Refs**: FR-006, FR-008, NFR-001, C-001, C-002, C-005

### Included Subtasks

T033 Rollback/abort family: B1–B5 (WP07)
T034 Claim-refusal ordering: B6 (WP07)
T035 Canceled-content verdict families: B7, B8 (WP07)
T036 Lanes families: B9 (WP07)
T037 Validate, time and record evidence (WP07)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- Depends on WP06 (its seam units must exist before the trims).

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~270 lines

---

## Work Package WP08: Root-independent unreadable-path tests (#5622) (Priority: P3)

**Goal**: Make the chmod-based unreadable-path tests give the same verdict as root and non-root, and apply the same guard to any other chmod-unreadable test in these files.
**Independent Test**: Run as root (this container is uid 0): `tests/charter/test_pack_manager.py::test_preparation_refuses_broken_required_inputs[unreadable]` and `tests/cli/commands/test_charter_io.py::test_resolve_charter_path_raises_when_directory_not_readable` fail before and do not fail after.
**Prompt**: `tasks/WP08-root-independent-permission-tests.md`
**Requirement Refs**: FR-007, C-001

### Included Subtasks

T038 Reproduce as root (WP08)
T039 Fix `test_preparation_refuses_broken_required_inputs[unreadable]` (WP08)
T040 Fix `test_resolve_charter_path_raises_when_directory_not_readable` (WP08)
T041 Sweep the two files for other chmod-unreadable tests and validate (WP08)

### Implementation Notes

- Seam tests first (own commit), planted break proven RED, revert, then marker edits / trims.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- Covering guard stays green → keep the test (KEEP), record it.

**Estimated prompt size**: ~240 lines
---

## Work Package WP09: Root-independent sweep of the other chmod-unreadable tests (#5622) (Priority: P3)

**Goal**: #5622 asks to add the same guard to any other chmod-based unreadable-path test. A root run on the base found 16 such tests in 8 files failing under uid 0; make them root-independent. Added after first finalization when WP08's sweep surfaced the list.
**Independent Test**: the 8 files run as uid 0 with 0 failures (base: 16 failed).
**Prompt**: `tasks/WP09-root-independent-chmod-sweep.md`
**Requirement Refs**: FR-007, NFR-003, C-001, SC-004

### Included Subtasks

T042 Reproduce the 16 root failures (WP09)
T043 Inject the failure at the I/O seam (preferred) (WP09)
T044 Skip under root only where no single seam exists (WP09)
T045 Planted breaks and validation (WP09)

### Implementation Notes

- Same seam-injection pattern as WP08.

### Parallel Opportunities

- Owns disjoint files from every other WP; runs in its own lane.

### Dependencies

- None.

### Risks & Mitigations

- A global Path monkeypatch leaking to other paths: delegate to the original for non-target paths.

**Estimated prompt size**: ~240 lines
