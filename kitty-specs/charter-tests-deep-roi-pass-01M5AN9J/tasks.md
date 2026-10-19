# Tasks: Deep ROI pass over the large tests/charter suites

**Mission**: `charter-tests-deep-roi-pass-01M5AN9J` · **Branch**: `feat/6485-charter-tests-deep-roi-pass` · **Issue**: #6485

All six work packages own disjoint file sets and have no dependencies, so they run as parallel lanes (cap: 4 concurrent agents).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Review `test_context.py` (1266 lines) | WP01 | [P] |
| T002 | Review `test_context_selection_render.py` (989 lines) | WP01 | [P] |
| T003 | Review the seams family and `test_context_profile_lineage_parity.py` | WP01 | [P] |
| T004 | Resolve cluster 2: `activation/test_context_identity_reuse.py` ↔ `activation/test_context_org_root_identity.py` | WP01 | [P] |
| T005 | Validate the WP and finish the ledger | WP01 | [P] |
| T006 | Review `synthesizer/test_synthesize_reconcile.py` (987 lines) | WP02 | [P] |
| T007 | Review `synthesizer/test_orchestrator_resynthesize.py` (935 lines) | WP02 | [P] |
| T008 | Review `synthesizer/test_bundle_validate_extension.py` (803) and `synthesizer/test_manifest.py` (788) | WP02 | [P] |
| T009 | Resolve cluster 1: `test_synthesize_path_parity.py` ↔ `test_orchestrator_synthesize.py` | WP02 | [P] |
| T010 | Validate the WP and finish the ledger | WP02 | [P] |
| T011 | Review `packs/test_pack_validator.py` (1485 lines, 129 s summed — 4th heaviest) | WP03 | [P] |
| T012 | Review `activation/test_org_charter.py` (1125) and `activation/test_org_charter_merge_parity.py` (76) | WP03 | [P] |
| T013 | Review `test_org_drg_loader.py` (783) and `test_pack_manager.py` (769) | WP03 | [P] |
| T014 | Resolve cluster 6: `test_retired_pack_fields.py` ↔ `test_retired_accompanies_doctrine_pack.py` | WP03 | [P] |
| T015 | Validate the WP and finish the ledger | WP03 | [P] |
| T016 | Review `test_resolver.py` (1021) and `test_resolver_activation_parity.py` (257) | WP04 | [P] |
| T017 | Review `test_cascade.py` (948) | WP04 | [P] |
| T018 | Review `test_compiler.py` (932; contains a 21 s test) | WP04 | [P] |
| T019 | Review `test_mission_type_profiles.py` (1249) and `test_mission_type_activations_seed_read_parity.py` (131) | WP04 | [P] |
| T020 | Resolve cluster 3: `activation/test_effective_set.py` ↔ `activation/test_effective_set_chain.py` | WP04 | [P] |
| T021 | Validate the WP and finish the ledger | WP04 | [P] |
| T022 | Review the six `*_parity.py` files | WP05 | [P] |
| T023 | Resolve cluster 5: `test_schemas.py`, `test_schemas_additive_fields.py`, `test_schemas_selection.py` | WP05 | [P] |
| T024 | Resolve cluster 4: `test_charter_cwd_isolation.py` ↔ `test_charter_cwd_tripwire.py` | WP05 | [P] |
| T025 | Resolve cluster 7: `test_sync_paths.py` ↔ `test_sync.py` | WP05 | [P] |
| T026 | Validate the WP and finish the ledger | WP05 | [P] |
| T027 | Profile each heavy file | WP06 | [P] |
| T028 | Cut cost in the charter-generate files | WP06 | [P] |
| T029 | Cut cost in the context-load files | WP06 | [P] |
| T030 | Review `test_retrospective_governance_emit.py` (47 s) and `test_activation_preserves_effective_4253.py` (35 s) | WP06 | [P] |
| T031 | Validate the WP and finish the ledger | WP06 | [P] |

## WP01 — Context family ROI pass

**Prompt**: `tasks/WP01-context-family.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

**Goal**: per-function ROI verdicts for 8 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T001 Review `test_context.py` (1266 lines) (WP01)
T002 Review `test_context_selection_render.py` (989 lines) (WP01)
T003 Review the seams family and `test_context_profile_lineage_parity.py` (WP01)
T004 Resolve cluster 2: `activation/test_context_identity_reuse.py` ↔ `activation/test_context_org_root_identity.py` (WP01)
T005 Validate the WP and finish the ledger (WP01)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## WP02 — Synthesizer suites ROI pass

**Prompt**: `tasks/WP02-synthesizer.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

**Goal**: per-function ROI verdicts for 6 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T006 Review `synthesizer/test_synthesize_reconcile.py` (987 lines) (WP02)
T007 Review `synthesizer/test_orchestrator_resynthesize.py` (935 lines) (WP02)
T008 Review `synthesizer/test_bundle_validate_extension.py` (803) and `synthesizer/test_manifest.py` (788) (WP02)
T009 Resolve cluster 1: `test_synthesize_path_parity.py` ↔ `test_orchestrator_synthesize.py` (WP02)
T010 Validate the WP and finish the ledger (WP02)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## WP03 — Packs and org-charter suites ROI pass

**Prompt**: `tasks/WP03-packs-and-org.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

**Goal**: per-function ROI verdicts for 7 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T011 Review `packs/test_pack_validator.py` (1485 lines, 129 s summed — 4th heaviest) (WP03)
T012 Review `activation/test_org_charter.py` (1125) and `activation/test_org_charter_merge_parity.py` (76) (WP03)
T013 Review `test_org_drg_loader.py` (783) and `test_pack_manager.py` (769) (WP03)
T014 Resolve cluster 6: `test_retired_pack_fields.py` ↔ `test_retired_accompanies_doctrine_pack.py` (WP03)
T015 Validate the WP and finish the ledger (WP03)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## WP04 — Resolver, cascade, compiler and mission-type suites ROI pass

**Prompt**: `tasks/WP04-resolver-activation-compiler.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

**Goal**: per-function ROI verdicts for 8 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T016 Review `test_resolver.py` (1021) and `test_resolver_activation_parity.py` (257) (WP04)
T017 Review `test_cascade.py` (948) (WP04)
T018 Review `test_compiler.py` (932; contains a 21 s test) (WP04)
T019 Review `test_mission_type_profiles.py` (1249) and `test_mission_type_activations_seed_read_parity.py` (131) (WP04)
T020 Resolve cluster 3: `activation/test_effective_set.py` ↔ `activation/test_effective_set_chain.py` (WP04)
T021 Validate the WP and finish the ledger (WP04)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## WP05 — Remaining parity, schema, cwd and sync files ROI pass

**Prompt**: `tasks/WP05-parity-schemas-cwd-sync.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

**Goal**: per-function ROI verdicts for 13 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T022 Review the six `*_parity.py` files (WP05)
T023 Resolve cluster 5: `test_schemas.py`, `test_schemas_additive_fields.py`, `test_schemas_selection.py` (WP05)
T024 Resolve cluster 4: `test_charter_cwd_isolation.py` ↔ `test_charter_cwd_tripwire.py` (WP05)
T025 Resolve cluster 7: `test_sync_paths.py` ↔ `test_sync.py` (WP05)
T026 Validate the WP and finish the ledger (WP05)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## WP06 — Heavy charter tests: cost and ROI pass

**Prompt**: `tasks/WP06-heavy-tests.md` · **Priority**: P1 · **Dependencies**: none · **Requirements**: FR-001, FR-002, FR-005, FR-006, FR-007

**Goal**: per-function ROI verdicts for 8 files; ledger written.

**Independent test**: owned files and `tests/charter_offering/` green; ledger rows match the diff.

**Subtasks**:

T027 Profile each heavy file (WP06)
T028 Cut cost in the charter-generate files (WP06)
T029 Cut cost in the context-load files (WP06)
T030 Review `test_retrospective_governance_emit.py` (47 s) and `test_activation_preserves_effective_4253.py` (35 s) (WP06)
T031 Validate the WP and finish the ledger (WP06)

**Risks**: false covering tests; shared fixtures; over-deleting contract tests.


## Orchestrator steps (not a WP)

- Before consolidation: extract every covering-test node id from all six ledgers and run `pytest --collect-only` on them; every cited test must still exist (circular-deletion guard).
- Commit each WP ledger into `roi-ledger/WP0N.md` before its review.
- After all lanes are consolidated: re-run the baseline command from `research.md`, record after-coverage, test count and wall clock (NFR-002, NFR-003, SC-003/SC-004).

