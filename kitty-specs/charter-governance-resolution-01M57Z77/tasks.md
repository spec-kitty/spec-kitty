# Work Packages: Charter governance resolution

**Inputs**: Design documents from `kitty-specs/charter-governance-resolution-01M57Z77/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: required by the spec (red-first, ADR 2026-07-17-1; non-vacuity per tactic `acceptance-criteria-non-vacuity`).

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Capture NFR-004 default in-force golden snapshot | WP01 | |
| T002 | Red tests for the identity index | WP01 | |
| T003 | Implement `IdentityIndex` and export it | WP01 | |
| T004 | Declared-id fallback for every kind in `resolve_artifact_urn` | WP01 | |
| T005 | Scan-count probe (NFR-003) | WP01 | |
| T006 | Fixture org pack + red tests for governance identity | WP02 | |
| T007 | Directive base and selection validation through the index | WP02 | |
| T008 | Paradigm validation and remediation texts | WP02 | |
| T009 | Service getters for every kind | WP02 | |
| T010 | Diagnostics in compact and JSON context | WP02 | |
| T011 | Verify WP02 | WP02 | |
| T012 | Red tests for identity surfaces | WP03 | |
| T013 | Action bundle and activation filter | WP03 | |
| T014 | `--include` and selection block | WP03 | |
| T015 | Preset application and `charter list` | WP03 | |
| T016 | Verify WP03 | WP03 | |
| T017 | Red tests for the synthesized tactic edge | WP04 | [P] |
| T018 | Emission: directive suggests tactic | WP04 | |
| T019 | `edge_owner` and reconcile call sites | WP04 | |
| T020 | Legacy `applies` strip | WP04 | |
| T021 | Relation prose in lockstep and legacy-shape fixtures | WP04 | |
| T022 | Red tests for synthesized tactic delivery | WP05 | |
| T023 | `reach_only_tactic_ids` | WP05 | |
| T024 | Subtract reach-only tactics from seeds | WP05 | |
| T025 | Activation append in synthesize | WP05 | |
| T026 | Red tests for `--only` | WP06 | [P] |
| T027 | Engine `narrow_base` and frozen-list warnings | WP06 | |
| T028 | `org_required_stems` | WP06 | |
| T029 | Manager `only=` | WP06 | |
| T030 | CLI `--only` | WP06 | |
| T031 | Red tests for interview narrow mode | WP07 | |
| T032 | `--narrow-activation` | WP07 | |
| T033 | Contract text | WP07 | |
| T034 | Pack gates | WP07 | |
| T035 | Red tests for stack detection | WP08 | [P] |
| T036 | Scan restructuring | WP08 | |
| T037 | Root-first `_detect_language` | WP08 | |
| T038 | Neutrality slug components | WP08 | |

---

## Work Package WP01: Identity index and default in-force snapshot (Priority: P1)

**Goal**: one per-invocation, layer-aware stem ↔ declared-id authority for every activatable kind; golden snapshot of today's default in-force sets.
**Independent Test**: `tests/charter/activation/test_identity_index.py` passes; snapshot committed on unmodified code.
**Prompt**: `tasks/WP01-identity-index.md`
**Requirement Refs**: FR-006, NFR-003, NFR-004, C-002, C-007

### Included Subtasks

T001 Capture NFR-004 default in-force golden snapshot (WP01)
T002 Red tests for the identity index (WP01)
T003 Implement `IdentityIndex` and export it (WP01)
T004 Declared-id fallback for every kind in `resolve_artifact_urn` (WP01)
T005 Scan-count probe (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Import cycles → index never imports `resolver`/`profile_resolution`.

---

## Work Package WP02: Governance resolution identity (Priority: P1)

**Goal**: declared ids in the governance base (#6406), layer-aware selections with unknown ids dropped and diagnosed (#6407), every service getter delivers stem ≠ id artifacts, JSON `diagnostics`.
**Independent Test**: fixture org pack (`qa-003-no-fake-green` → `QA_003`) shows `QA_003`; `[QA_003, NOPE_999]` keeps governance and reports `NOPE_999`.
**Prompt**: `tasks/WP02-governance-resolution-identity.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-010, FR-011, NFR-004

### Included Subtasks

T006 Fixture org pack + red tests (WP02)
T007 Directive base and selection validation through the index (WP02)
T008 Paradigm validation and remediation texts (WP02)
T009 Service getters for every kind (WP02)
T010 Diagnostics in compact and JSON context (WP02)
T011 Verify (WP02)

### Dependencies

- Depends on WP01.

---

## Work Package WP03: Identity surfaces (Priority: P1)

**Goal**: action bundle, activation filter, `--include`, selection block, preset application and `charter list` use the index.
**Independent Test**: both spellings resolve in `--include`; org tactic with stem ≠ id delivered and listed as activated.
**Prompt**: `tasks/WP03-identity-surfaces.md`
**Requirement Refs**: FR-007, FR-008, FR-017, NFR-003

### Included Subtasks

T012 Red tests (WP03)
T013 Action bundle and activation filter (WP03)
T014 `--include` and selection block (WP03)
T015 Preset application and `charter list` (WP03)
T016 Verify (WP03)

### Dependencies

- Depends on WP02.

---

## Work Package WP04: Synthesized tactic edge and reconcile ownership (Priority: P1)

**Goal**: `directive --suggests--> tactic` emission, owner-based reconcile, prune of touching edges, legacy `applies` strip, relation prose (#6404).
**Independent Test**: second synthesize leaves exactly one suggests edge; legacy `applies` stripped.
**Prompt**: `tasks/WP04-synthesized-tactic-edge.md`
**Requirement Refs**: FR-001, FR-004, FR-005, C-004

### Included Subtasks

T017 Red tests (WP04)
T018 Emission (WP04)
T019 `edge_owner` and reconcile call sites (WP04)
T020 Legacy `applies` strip (WP04)
T021 Relation prose and fixtures (WP04)

### Dependencies

- None (parallel with WP01-WP03).

---

## Work Package WP05: Synthesized tactic delivery and activation append (Priority: P1)

**Goal**: edge-carrying synthesized tactics are not roots; synthesize appends its tactic ids to an explicit `activated_tactics`.
**Independent Test**: directive active → tactic delivered; edge removed or directive deactivated → not delivered.
**Prompt**: `tasks/WP05-synthesized-tactic-delivery.md`
**Requirement Refs**: FR-002, FR-003, C-001

### Included Subtasks

T022 Red tests (WP05)
T023 `reach_only_tactic_ids` (WP05)
T024 Subtract reach-only tactics from seeds (WP05)
T025 Activation append in synthesize (WP05)

### Dependencies

- Depends on WP03, WP04.

---

## Work Package WP06: Opt-in narrow activation (Priority: P2)

**Goal**: `charter activate <kind> <id> --only`; frozen-list warnings (#6408).
**Independent Test**: fresh `--only` writes one entry and lists what stopped being in force.
**Prompt**: `tasks/WP06-narrow-activation-only.md`
**Requirement Refs**: FR-012, FR-014, C-001

### Included Subtasks

T026 Red tests (WP06)
T027 Engine `narrow_base` and warnings (WP06)
T028 `org_required_stems` (WP06)
T029 Manager `only=` (WP06)
T030 CLI `--only` (WP06)

### Dependencies

- None (parallel).

---

## Work Package WP07: Interview narrow activation and contract text (Priority: P2)

**Goal**: `charter interview --narrow-activation`; `/spec-kitty.charter` contract text.
**Independent Test**: narrow interview writes selection + org-required only; JSON `narrowed`.
**Prompt**: `tasks/WP07-interview-narrow-and-contract.md`
**Requirement Refs**: FR-013, FR-014, C-003

### Included Subtasks

T031 Red tests (WP07)
T032 `--narrow-activation` (WP07)
T033 Contract text (WP07)
T034 Pack gates (WP07)

### Dependencies

- Depends on WP06.

---

## Work Package WP08: Root-first stack detection (Priority: P2)

**Goal**: root-first indicators, JVM indicators, count tie-break; neutrality slug components (#6405).
**Independent Test**: Gradle + `site/` fixture → `java`; docs-only control → `typescript`.
**Prompt**: `tasks/WP08-root-first-stack-detection.md`
**Requirement Refs**: FR-015, FR-016, C-006

### Included Subtasks

T035 Red tests (WP08)
T036 Scan restructuring (WP08)
T037 Root-first `_detect_language` (WP08)
T038 Neutrality slug components (WP08)

### Dependencies

- None (parallel).

---

## Parallel Opportunities

WP01, WP04, WP06 and WP08 can start immediately; WP02 → WP03 → WP05 and WP06 → WP07 are the chains.

## MVP

WP01 + WP02 (the identity root behind #6406, #6407 and the sibling defect).
