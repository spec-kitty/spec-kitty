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

## Work Package WP02: Successor plumbing: selection-view settled check and residue walk (Priority: P0)

**Goal**: Give the four successors one shared, tested copy of the selection-view "predecessor settled" check, the residue partition walk and the notice list. Register no migration, so no registry gate changes state.
**Independent Test**: `tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py`. `settled_in_selection_view` equals "not selected by `get_applicable`" for every ledger state and for pending adoption.
**Prompt**: `tasks/WP02-successors-2-0-6-and-3-1-1.md`
**Requirement Refs**: FR-007, C-002

### Included Subtasks

T006 `registry.settled_in_selection_view` sharing one predicate with `get_applicable` (WP02)
T007 `_residue_successor.py`: `predecessor_settled`, `partition_kitty_specs`, `residue_warnings` with project-relative paths (WP02)
T008 [P] Plumbing tests: selection equivalence, partition in both modes, notice paths, no registration on import (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Drift between the helper and `get_applicable`: one shared private expression and an equivalence test.

---

## Work Package WP03: Four residue-aware successors and their registry gates (Priority: P0)

**Goal**: Supersede `0.9.0_frontmatter_only_lanes`, `0.9.1_complete_migration`, `2.0.6_consistency_sweep` and `3.1.1_normalize_status_json` with residue-aware successors in their slots, and leave every registry gate they touch green in the same WP.
**Independent Test**: `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py`, driven through `MigrationRegistry` and the runner. Real Missions are repaired as before (parity with the frozen classes), residue is untouched under main and worktree `kitty-specs/`, nothing re-sweeps after a settled predecessor, and dry-run and live runs agree.
**Prompt**: `tasks/WP03-lane-migration-successors.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, FR-013, NFR-001, C-002, C-006

### Included Subtasks

T009 `2.0.6_residue_safe_consistency_sweep` over the frozen 2.0.6 helpers (WP03)
T010 `3.1.1_residue_safe_normalize_status_json` (same snapshot bytes; write-site gates run early) (WP03)
T011 `0.9.0` / `0.9.1` subclass successors via a module-alias import (rediscovery trap) (WP03)
T012 Supersession entries and `# tie:` order-manifest slots for all four (WP03)
T013 `test_no_dead_modules` ratchet: add the successors, drop shipped modules that gained a caller (WP03)
T014 Walker inventory reclassified under the new rule; `_SUPERSEDED` label; `_GUARDED_IDENTITY_ONLY` removed (WP03)
T015 [P] Registry/runner tests: substitution + rediscovery, repair parity, residue untouched, fallback repair, settled gate, dry-run at exactly 2.0.6, worktree ledger, superseded record, C-006, order; parametrized #6589 pins (WP03)

### Implementation Notes

- Never edit a shipped `m_*.py` (NFR-001). Import helpers, or the shipped module under an alias; never the shipped class by name.

### Dependencies

- Depends on WP02 (plumbing) and WP05 (shared walkers, so the inventory labels are true when written).

### Risks & Mitigations

- A missed 0.9.1 walker: an AST check pins that every per-folder entry point is overridden.
- Write-site gates keyed on module paths: run them in T010 and add a rationale entry only if one fires.

---

## Work Package WP04: Collapse residue notices in the upgrade runner (Priority: P1)

**Goal**: Name each residue folder at most once per upgrade run, however many steps skip it.
**Independent Test**: `tests/upgrade/test_residue_notice_collapse.py`. Three steps warning about the same folder produce one line; other warnings pass through unchanged.
**Prompt**: `tasks/WP04-residue-notice-collapse.md`
**Requirement Refs**: FR-008

### Included Subtasks

T016 Locate the warning collection path in `upgrade/runner.py` (main and worktree loops) (WP04)
T017 Collapse residue notices keyed on the resolved folder path, one seen-set shared by the main and worktree loops (WP04)
T018 [P] Tests: collapse, pass-through of other warnings, main-vs-worktree same folder, same slug in two checkouts, `--json` (WP04)

### Dependencies

- Depends on WP01.

---

## Work Package WP05: Shared migration walkers skip residue (Priority: P1)

**Goal**: Route the two shared migration walkers through the rule, reporting each skip without a second naming during upgrade.
**Independent Test**: `tests/specify_cli/migration/test_residue_shared_walkers_6669.py`.
**Prompt**: `tasks/WP05-shared-walkers-and-gate.md`
**Requirement Refs**: FR-003

### Included Subtasks

T019 `backfill_runtime_state._mission_dirs` skips residue (WP05)
T020 `migration/runner._move_derived_files` skips residue (WP05)
T021 [P] Behaviour tests for both walkers, plus a non-git control (WP05)

### Dependencies

- Depends on WP01.

---

## Work Package WP06: Fabricated-identity doctor finding (Priority: P2)

**Goal**: `doctor mission-state --audit` reports a WARNING for a folder whose identity an earlier upgrade fabricated, when all three signals hold. It never deletes and never blocks. The `RESIDUE_DIRECTORY` remedy text becomes accurate.
**Independent Test**: `tests/audit/test_fabricated_identity_finding.py`. 1 of 1 planted folders is found, no folder meeting only two signals is, and none of this repository's `kitty-specs/` children are.
**Prompt**: `tasks/WP06-fabricated-identity-finding.md`
**Requirement Refs**: FR-010, FR-011, FR-012, NFR-002, C-001

### Included Subtasks

T023 Extract `baseline_slug_fields()` into the stdlib-only `specify_cli/mission_metadata.py`, used by `build_baseline_feature_meta` (WP06)
T024 `audit/classifiers/fabricated_identity.py`: the three signals (WP06)
T025 `FABRICATED_IDENTITY_SUSPECTED` (WARNING, not a blocker); call from `_scan_missions`; fix the `RESIDUE_DIRECTORY` remedy; wire new modules into the audit routing pin (WP06)
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

T027 Extend the reproduction to 5 shapes plus a real-Mission and a committed-legacy-Mission control; remove the `p0_repro` marker (WP07)
T028 ADR 2026-10-17-1 Amendment: new-migration successors with a ledger-gated `detect()`; accepted residual C-006 (WP07)
T029 CHANGELOG `[Unreleased]` entries for #6669 and #6668 (WP07)
T030 Validate `quickstart.md`; NFR-001 and C-003/C-004 checks; list this Mission in `LIVE_COORDINATION_SKIPS`; trace SC-003/SC-004; record test commands and counts (WP07)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → {WP02, WP05, WP04} → WP03 (needs WP02 and WP05) → WP07. WP06 is independent and can run any time.
- **Parallelization**: WP06 alongside everything; WP02, WP04 and WP05 in parallel after WP01.
- **Green tree per WP**: no WP registers a migration without also updating every registry gate it touches (that is WP03), so each WP leaves the tree green.
- **MVP scope**: WP01 + WP02 + WP03 + WP07. They close the identity fabrication and the residue writers.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01, WP05 |
| FR-004 | WP03 |
| FR-005 | WP03 |
| FR-006 | WP03 |
| FR-007 | WP02, WP03 |
| FR-008 | WP01, WP04 |
| FR-009 | WP07 |
| FR-010 | WP06 |
| FR-011 | WP06 |
| FR-012 | WP06 |
| FR-013 | WP03 |
| NFR-001 | WP03, WP07 |
| NFR-002 | WP06 |
| NFR-003 | WP01 |
| NFR-004 | WP07 |
| C-001 | WP06 |
| C-002 | WP02 |
| C-003, C-004, C-005 | WP07 |
| C-006 | WP03 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Git-aware mode probe | WP01 | P0 | No |
| T002 | Git-aware rule + threading | WP01 | P0 | No |
| T003 | RESIDUE_NOTICE + path parser | WP01 | P0 | No |
| T004 | Rule unit tests + git-call spy | WP01 | P0 | Yes |
| T005 | Re-pin #6627 seam tests | WP01 | P0 | No |
| T006 | settled_in_selection_view | WP02 | P0 | No |
| T007 | _residue_successor.py | WP02 | P0 | No |
| T008 | Plumbing tests | WP02 | P0 | Yes |
| T009 | 2.0.6 successor | WP03 | P0 | No |
| T010 | 3.1.1 successor | WP03 | P0 | No |
| T011 | 0.9.0 / 0.9.1 successors | WP03 | P0 | No |
| T012 | Supersession + manifest ties | WP03 | P0 | No |
| T013 | Dead-modules ratchet | WP03 | P0 | No |
| T014 | Walker inventory reclassification | WP03 | P0 | No |
| T015 | Successor tests | WP03 | P0 | Yes |
| T016 | Locate warning collection | WP04 | P1 | No |
| T017 | Path-keyed notice collapse | WP04 | P1 | No |
| T018 | Collapse tests | WP04 | P1 | Yes |
| T019 | backfill_runtime_state walker | WP05 | P1 | No |
| T020 | runner derived-files walker | WP05 | P1 | No |
| T021 | Shared walker tests | WP05 | P1 | Yes |
| T023 | baseline_slug_fields | WP06 | P2 | No |
| T024 | Fabricated-identity classifier | WP06 | P2 | No |
| T025 | Code, severity, wiring, remedy | WP06 | P2 | No |
| T026 | Audit finding tests | WP06 | P2 | Yes |
| T027 | Guard: 5 shapes + controls, drop marker | WP07 | P0 | No |
| T028 | ADR amendment | WP07 | P0 | No |
| T029 | CHANGELOG | WP07 | P0 | No |
| T030 | Validate and record | WP07 | P0 | No |

T022 was retired in the post-tasks re-cut (its walker-gate work moved into T014).
