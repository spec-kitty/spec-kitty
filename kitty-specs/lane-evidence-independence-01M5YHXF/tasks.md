# Work Packages: Lane evidence and review independence

**Inputs**: Design documents from `kitty-specs/lane-evidence-independence-01M5YHXF/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/refusal-codes.md, quickstart.md

**Tests**: Required. The charter's ATDD-first rule (C-011) and the issue's acceptance demand a
red-first CLI-level regression fixture; each WP commits its failing test before its fix.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: consolidate + orchestrator-api fixtures for the hollow lane/coord/planning-lane WP | WP01 | |
| T002 | `consolidation/wp_evidence.py`: codes, alias table, owned matching, windows, verdict, attestation reader | WP01 | |
| T003 | Generalise the claim-builder axis in `reconciliation.py` to every topology | WP01 | |
| T004 | `orchestrator-api consolidate-mission` and `accept-mission` refusals | WP01 | |
| T005 | Unit tests for the predicate; re-pin affected fixtures | WP01 | |
| T006 | Red-first: attestation tests (record, lift, never independence, reason required) | WP02 | |
| T007 | `consolidation/no_implementation_attestation.py`: validate + record | WP02 | |
| T008 | Exclude the attestation from the approving-actor read and the force discount | WP02 | |
| T009 | `consolidate --attest-no-implementation` wiring and output note | WP02 | |
| T010 | Red-first: move-task + accept CLI fixtures (coord, lanes, single_branch, --force, self-approval) | WP03 | |
| T011 | Move-task evidence gate on every topology (unforced) | WP03 | |
| T012 | Move-task independence gate (unforced, positively-same identity) | WP03 | |
| T013 | Accept preflight refusal + `--attest-no-implementation` on accept | WP03 | |
| T014 | Re-pin move-task / accept fixtures the gates now refuse | WP03 | |
| T015 | ADR `2026-10-04-5` amendment | WP04 | [P] |
| T016 | Changelog `[Unreleased]` entry | WP04 | [P] |
| T017 | Gherkin scenario under `tests/scenarios/mission/` + JDK 25 run | WP04 | |
| T018 | CLAUDE.md consolidation note (only if the charter's canonical-source rule allows) | WP04 | [P] |

---

## Work Package WP01: Shared evidence predicate and the consolidate axis (Priority: P0)

**Goal**: One topology-neutral evidence + independence predicate, applied in the consolidate
claim builder and in `orchestrator-api consolidate-mission` / `accept-mission`.
**Independent Test**: the hollow coord fixture (WP approved with `--force` by a different
reviewer, no owned-file commit) makes `consolidate` refuse `IMPLEMENTATION_MISSING` before any
branch moves, with no "Reconciliation verified" banner; the positive control consolidates.
**Prompt**: `tasks/WP01-shared-evidence-predicate-and-consolidate-axis.md`
**Requirement Refs**: FR-004, FR-005, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002

### Included Subtasks

T001 Red-first: consolidate + orchestrator-api fixtures for the hollow lane/coord/planning-lane WP (WP01)
T002 `consolidation/wp_evidence.py`: codes, alias table, owned matching, windows, verdict, attestation reader (WP01)
T003 Generalise the claim-builder axis in `reconciliation.py` to every topology (WP01)
T004 `orchestrator-api consolidate-mission` and `accept-mission` refusals (WP01)
T005 Unit tests for the predicate; re-pin affected fixtures (WP01)

### Dependencies

- None (starting package).

### Risks & Mitigations

- Existing consolidate fixtures that self-approve or approve hollow WPs go red: judge each test
  (DIRECTIVE_041) and re-pin with a distinct reviewer / a real owned commit; never weaken the gate.

---

## Work Package WP02: No-implementation attestation (Priority: P1)

**Goal**: `--attest-no-implementation <WP> --attest-reason` records a forced operator
self-transition that lifts only `IMPLEMENTATION_MISSING`, and consolidate names it.
**Independent Test**: a hollow docs-only WP refuses without the attestation and consolidates with
it; a self-approved attested WP still refuses `REVIEW_NOT_INDEPENDENT`.
**Prompt**: `tasks/WP02-no-implementation-attestation.md`
**Requirement Refs**: FR-006, C-002, SC-003

### Included Subtasks

T006 Red-first: attestation tests (record, lift, never independence, reason required) (WP02)
T007 `consolidation/no_implementation_attestation.py`: validate + record (WP02)
T008 Exclude the attestation from the approving-actor read and the force discount (WP02)
T009 `consolidate --attest-no-implementation` wiring and output note (WP02)

### Dependencies

- Depends on WP01 (reads the attestation through `wp_evidence`).

---

## Work Package WP03: Move-task and accept gates (Priority: P0)

**Goal**: `move-task` refuses an unforced hollow or self approval on every topology; `accept`
refuses (hard preflight) and can record the attestation.
**Independent Test**: the issue's exact claimed-but-empty coord fixture refuses at approve, at
accept and at consolidate, and nothing lands `done`.
**Prompt**: `tasks/WP03-move-task-and-accept-gates.md`
**Requirement Refs**: FR-001, FR-002, FR-003, C-004, SC-001, SC-002

### Included Subtasks

T010 Red-first: move-task + accept CLI fixtures (coord, lanes, single_branch, --force, self-approval) (WP03)
T011 Move-task evidence gate on every topology (unforced) (WP03)
T012 Move-task independence gate (unforced, positively-same identity) (WP03)
T013 Accept preflight refusal + `--attest-no-implementation` on accept (WP03)
T014 Re-pin move-task / accept fixtures the gates now refuse (WP03)

### Dependencies

- Depends on WP01, WP02.

---

## Work Package WP04: Decision record, changelog and scenario (Priority: P2)

**Goal**: ADR amendment, changelog entry, a Gherkin scenario run on JDK 25, and (if allowed) the
CLAUDE.md consolidation note.
**Independent Test**: the scenario fails on the pre-fix CLI and passes on the fixed one.
**Prompt**: `tasks/WP04-decision-record-changelog-and-scenario.md`
**Requirement Refs**: FR-008, FR-009

### Included Subtasks

T015 [P] ADR `2026-10-04-5` amendment (WP04)
T016 [P] Changelog `[Unreleased]` entry (WP04)
T017 Gherkin scenario under `tests/scenarios/mission/` + JDK 25 run (WP04)
T018 [P] CLAUDE.md consolidation note (only if the charter's canonical-source rule allows) (WP04)

### Dependencies

- Depends on WP03.
