---
description: "Work packages for residue-safe-migration-sweep-01M5SS0F"
---

# Work Packages: Residue-safe migration sweep and fabricated-identity audit

**Inputs**: Design documents from `kitty-specs/residue-safe-migration-sweep-01M5SS0F/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (no contracts/: `meta.json` records `contracts: none`)

**Tests**: Required. The spec's FRs are acceptance-test shaped (red-first per ADR 2026-07-17-1). Every WP ships its tests in the same commit as the code.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (a different file or component).
- Subtasks are **reference rows**, not checkboxes. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Git-aware residue rule and shared notice (Priority: P0)

**Goal**: The one residue decision becomes git-aware (operator rulings), stays cheap, and owns the one notice text every step prints.
**Independent Test**: `tests/context/test_is_kitty_specs_residue_git_aware.py`. The residue fixtures (tasks, event log, status snapshot, `tasks/<lane>/`, `decisions/`) are residue in a tracked project and Missions in a non-git, an ignored-`kitty-specs/` and a nested-untracked project. A git-call spy holds NFR-003.
**Prompt**: `tasks/WP01-git-aware-residue-rule.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008, NFR-003

### Included Subtasks

T001 Git-aware mode probe: git runs AND `tracked_mission_paths` is non-empty (WP01)
T002 Git-aware branch of `is_kitty_specs_residue` with `repo_root=` / `tracked=` threading (WP01)
T003 `RESIDUE_NOTICE` constant with a working remedy; lifecycle normalization uses it (WP01)
T004 [P] Unit tests for every mode and shape, plus the git-call spy (WP01)
T005 Re-pin the #6627 seam tests to the new semantics (WP01)

### Implementation Notes

- The rule stays in `context/mission_resolver.py`, with no second predicate. Markers on disk and an identity are checked before any git call.

### Parallel Opportunities

- T004 can be written alongside T002 once T001's probe signature is fixed.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Widening residue past the rulings: tests pin the deleted-tracked-`spec.md` case and every fallback mode.

---

## Work Package WP02: Successor plumbing and the 2.0.6 / 3.1.1 successors (Priority: P0)

**Goal**: Supersede `2.0.6_consistency_sweep` and `3.1.1_normalize_status_json` with residue-aware successors in their slots, gated off where the predecessor is already settled.
**Independent Test**: `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py`, driven through `MigrationRegistry` and the runner. Repairs land on Missions and never on residue, there is no re-sweep after a settled predecessor, and dry-run and live runs agree.
**Prompt**: `tasks/WP02-successors-2-0-6-and-3-1-1.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, NFR-001, C-002, C-006

### Included Subtasks

T006 `_residue_successor.py`: predecessor-settled view (ledger + pending adoption), residue filter, notice helper (WP02)
T007 `2.0.6_residue_safe_consistency_sweep` successor over the frozen 2.0.6 helpers (WP02)
T008 `3.1.1_residue_safe_normalize_status_json` successor (own snapshot write, with a gate rationale if one fires) (WP02)
T009 Supersession entries and order-manifest ties for both (WP02)
T010 [P] Registry- and runner-driven tests: repair parity, residue untouched, settled gate, dry-run parity, worktree ledger (WP02)
T011 Extend the #6589 supersession pins (byte-identical hash, carried attributes, successor-after) to the new ids (WP02)

### Implementation Notes

- Never edit `m_2_0_6_*.py` or `m_3_1_1_normalize_status_json.py`. Import their helpers.

### Parallel Opportunities

- T007 and T008 can proceed in parallel after T006.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Write-site gates keyed on module paths: run them early (T008) and add a rationale entry only if one fires.

---

## Work Package WP03: Lane-migration successors (0.9.0 / 0.9.1) (Priority: P1)

**Goal**: Supersede `0.9.0_frontmatter_only_lanes` and `0.9.1_complete_migration` with subclass successors that skip residue in every walker, including `.worktrees/*/kitty-specs`.
**Independent Test**: `tests/specify_cli/upgrade/test_residue_safe_lane_successors_6669.py`. A residue folder holding `tasks/doing/WP01-x.md` is untouched; a real legacy Mission's lane files are migrated exactly as before.
**Prompt**: `tasks/WP03-lane-migration-successors.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007

### Included Subtasks

T012 `0.9.0_residue_safe_frontmatter_only_lanes`: subclass, override the per-folder predicate (WP03)
T013 `0.9.1_residue_safe_complete_migration`: subclass, override every per-folder walker (WP03)
T014 Supersession entries and manifest ties for both (a sequential, out-of-map edit after WP02) (WP03)
T015 [P] Registry-driven tests for main and worktree `kitty-specs/`, plus the settled gate (WP03)

### Dependencies

- Depends on WP02 (shared plumbing, supersession table, manifest).

### Risks & Mitigations

- 0.9.1 has several walkers (`detect`, `_find_features_with_lanes`, `_normalize_all_frontmatter`, worktree cleanup). An AST check in the test pins that every per-folder entry point is overridden.

---

## Work Package WP04: Collapse residue notices in the upgrade runner (Priority: P1)

**Goal**: Name each residue folder at most once per upgrade run, however many steps skip it.
**Independent Test**: `tests/upgrade/test_residue_notice_collapse.py`. Three steps warning about the same folder produce one line; other warnings pass through unchanged.
**Prompt**: `tasks/WP04-residue-notice-collapse.md`
**Requirement Refs**: FR-008

### Included Subtasks

T016 Locate the warning collection path in `upgrade/runner.py` (main and worktree loops) (WP04)
T017 Collapse exact `RESIDUE_NOTICE` lines per folder per run (WP04)
T018 [P] Tests: collapse, pass-through of other warnings, worktree prefixes (WP04)

### Dependencies

- Depends on WP01.

---

## Work Package WP05: Shared walkers and an honest walker gate (Priority: P1)

**Goal**: Route the remaining shared walkers through the rule and reclassify the walker inventory under the new definition.
**Independent Test**: `tests/architectural/test_migration_walkers_use_mission_predicate.py` plus `tests/specify_cli/migration/test_residue_shared_walkers_6669.py`.
**Prompt**: `tasks/WP05-shared-walkers-and-gate.md`
**Requirement Refs**: FR-003, FR-013

### Included Subtasks

T019 `backfill_runtime_state._mission_dirs` skips residue (WP05)
T020 `migration/runner._move_derived_files` skips residue (WP05)
T021 Reclassify the walker inventory; successors as `_FILTERS`; drop `_GUARDED_IDENTITY_ONLY` (WP05)
T022 [P] Behaviour tests for both walkers (WP05)

### Dependencies

- Depends on WP01, WP02, WP03.

---

## Work Package WP06: Fabricated-identity doctor finding (Priority: P2)

**Goal**: `doctor mission-state --audit` reports a WARNING for a folder whose identity an earlier upgrade fabricated, when all three signals hold. It never deletes and never blocks. The `RESIDUE_DIRECTORY` remedy text becomes accurate.
**Independent Test**: `tests/audit/test_fabricated_identity_finding.py`. 1 of 1 planted folders is found, no folder meeting only two signals is, and none of this repository's `kitty-specs/` children are.
**Prompt**: `tasks/WP06-fabricated-identity-finding.md`
**Requirement Refs**: FR-010, FR-011, FR-012, NFR-002, C-001

### Included Subtasks

T023 Extract `baseline_slug_fields()` from `build_baseline_feature_meta` (WP06)
T024 `audit/classifiers/fabricated_identity.py`: the three signals (WP06)
T025 `FABRICATED_IDENTITY_SUSPECTED` (WARNING, not a blocker); call from `_scan_missions`; fix the `RESIDUE_DIRECTORY` remedy (WP06)
T026 [P] Tests: positive, two-signal negatives, `--fail-on` contract, outside-git, corpus zero (WP06)

### Dependencies

- None (independent of WP01..WP05).

---

## Work Package WP07: Red-first guard, ADR amendment, changelog (Priority: P0)

**Goal**: The #6669 reproduction covers all five leftover shapes, loses its `p0_repro` marker and runs per PR; the decisions are recorded.
**Independent Test**: `tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py` and the #6627 guard pass through the real `spec-kitty upgrade` CLI.
**Prompt**: `tasks/WP07-red-first-guard-and-docs.md`
**Requirement Refs**: FR-009, NFR-004, C-003, C-004, C-005, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T027 Extend the reproduction to 5 shapes plus a real-Mission control; remove the `p0_repro` marker (WP07)
T028 ADR 2026-10-17-1 Amendment: new-migration successors with a ledger-gated `detect()`; accepted residual C-006 (WP07)
T029 CHANGELOG `[Unreleased]` entries for #6669 and #6668 (WP07)
T030 Validate `quickstart.md`; NFR-001 byte-identity check; record test commands and counts (WP07)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → (WP02 → WP03), WP04 → WP05 → WP07. WP06 is independent and can run any time.
- **Parallelization**: WP06 alongside everything; WP04 alongside WP02/WP03 after WP01.
- **MVP scope**: WP01 + WP02 + WP07. They close the identity fabrication and the 2.0.6 writers.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01, WP05 |
| FR-004 | WP02, WP03 |
| FR-005 | WP02, WP03 |
| FR-006 | WP02, WP03 |
| FR-007 | WP02, WP03 |
| FR-008 | WP01, WP04 |
| FR-009 | WP07 |
| FR-010 | WP06 |
| FR-011 | WP06 |
| FR-012 | WP06 |
| FR-013 | WP05 |
| NFR-001 | WP02 |
| NFR-002 | WP06 |
| NFR-003 | WP01 |
| NFR-004 | WP07 |
| C-001 | WP06 |
| C-002 | WP02 |
| C-003, C-004, C-005 | WP07 |
| C-006 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Git-aware mode probe | WP01 | P0 | No |
| T002 | Git-aware rule + threading | WP01 | P0 | No |
| T003 | RESIDUE_NOTICE | WP01 | P0 | No |
| T004 | Rule unit tests + git-call spy | WP01 | P0 | Yes |
| T005 | Re-pin #6627 seam tests | WP01 | P0 | No |
| T006 | Successor plumbing | WP02 | P0 | No |
| T007 | 2.0.6 successor | WP02 | P0 | Yes |
| T008 | 3.1.1 successor | WP02 | P0 | Yes |
| T009 | Supersession + manifest (2.0.6, 3.1.1) | WP02 | P0 | No |
| T010 | Successor tests | WP02 | P0 | Yes |
| T011 | Supersession pins | WP02 | P0 | No |
| T012 | 0.9.0 successor | WP03 | P1 | Yes |
| T013 | 0.9.1 successor | WP03 | P1 | Yes |
| T014 | Supersession + manifest (0.9.x) | WP03 | P1 | No |
| T015 | Lane-successor tests | WP03 | P1 | Yes |
| T016 | Locate warning path | WP04 | P1 | No |
| T017 | Collapse residue notices | WP04 | P1 | No |
| T018 | Collapse tests | WP04 | P1 | Yes |
| T019 | backfill_runtime_state walker | WP05 | P1 | No |
| T020 | _move_derived_files walker | WP05 | P1 | No |
| T021 | Walker gate reclassification | WP05 | P1 | No |
| T022 | Walker behaviour tests | WP05 | P1 | Yes |
| T023 | baseline_slug_fields | WP06 | P2 | No |
| T024 | Fabricated-identity classifier | WP06 | P2 | No |
| T025 | Finding code + engine wiring | WP06 | P2 | No |
| T026 | Finding tests | WP06 | P2 | Yes |
| T027 | Extend red-first guard | WP07 | P0 | No |
| T028 | ADR amendment | WP07 | P0 | Yes |
| T029 | CHANGELOG | WP07 | P0 | Yes |
| T030 | Quickstart + NFR-001 + test record | WP07 | P0 | No |
