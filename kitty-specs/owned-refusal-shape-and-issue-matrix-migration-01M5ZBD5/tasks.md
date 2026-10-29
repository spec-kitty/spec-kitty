# Work Packages: Owned-checkout issue-verdict cleanup

**Inputs**: Design documents from `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/owned-refusal-envelope.md, quickstart.md

**Tests**: Required. The charter mandates ATDD / red-first: every WP opens with a failing acceptance test through the real CLI entry point, committed before the implementation.

**Organization**: Subtasks (`Txxx`) roll up into four work packages in a strict chain
(WP01 → WP02 → WP03 → WP04). The chain is deliberate. Several shape-pinning test files
cover many commands at once, and the renderer signature change must land atomically with
every caller. A strict order keeps every intermediate commit importable and green, and
no two lanes edit the same file.

Subtasks are **reference rows**, not checkboxes: record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Owned-aware legacy issue-matrix migration (Priority: P1) 🎯 MVP

**Goal**: An owned Mission's legacy `issue-matrix.md` migrates into its owned checkout when an issue verdict is recorded (issue #6354).
**Independent Test**: `agent issue-verdict --owned-checkout <P> --json` on an owned-only Mission whose owned checkout holds a legacy `issue-matrix.md` exits 0, and `P`'s `issue-matrix.json` holds the legacy row and the new verdict; the repository root checkout gets nothing.
**Prompt**: `tasks/WP01-owned-legacy-issue-matrix-migration.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-004, C-003

### Included Subtasks

T001 Red-first integration test: owned legacy `.md` migration via explicit flag and flagless adoption (WP01)
T002 Non-owned positive control and forwarding unit test (WP01)
T003 Thread keyword-only `owned` through `migrate_issue_matrix_to_json` into `write_issue_matrix` (WP01)
T004 Forward the validated owned fact from `issue_verdict._migrate_if_needed` (WP01)
T005 Blast-radius run incl. the issue-matrix terminality tests and the malformed-legacy edge (WP01)

### Dependencies

- None (starting package).

### Risks & Mitigations

- The bulk `issue-matrix migrate` command must keep `owned=None` (repository root by design). Do not touch it.
- The `checkouts` fixture is slow (~170 s); keep the new tests in one module.

---

## Work Package WP02: One C2 owned refusal through the shared renderer (Priority: P1)

**Goal**: The shared owned-checkout renderer prints exactly `{ok:false, error:{code,message}}` (+ optional `context`, + optional `spec_kitty_version`), and every renderer caller uses it (issue #6353).
**Independent Test**: For each renderer caller with `--json`, an owned refusal prints the C2 core with no top-level `error_code`, exit 1; human mode is unchanged; success payloads are unchanged.
**Prompt**: `tasks/WP02-c2-owned-refusal-renderer-and-callers.md`
**Requirement Refs**: FR-004, FR-005, FR-007, FR-008, FR-009, FR-010, FR-011, FR-014, C-001, C-002, C-004, NFR-002, NFR-003

### Included Subtasks

T006 Red-first tests: renderer unit tests for the C2 payload and an issue-verdict owned refusal integration assertion (WP02)
T007 Renderer core: `owned_refusal_payload`, new `emit_owned_refusal` / `resolve_owned_or_refuse` signatures, Op-root refusal, delete the four envelope builders (WP02)
T008 ADR `2026-10-27-2` superseding the "keeps each command's existing JSON envelope keys" contract line; rewrite the module docstring's envelope rule (WP02)
T009 Agent mission family call sites: issue-verdict, acceptance-verdict, context resolve, setup-plan, finalize-tasks, check-prerequisites, record-analysis (WP02)
T010 Tasks family call sites: move-task, map-requirements, tasks status, mark-status (edge refusal and in-command owned failure) (WP02)
T011 Top-level call sites: next, accept, spec-commit, charter generate, research, agent action implement/review, decision repair-runtime-lock and the decision verbs' owned resolution (stdout) (WP02)
T012 Re-pin every stale owned-refusal shape assertion across the suite (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Signature change must be atomic with every caller; run `mypy` on every touched module.
- Decision verbs: tell the owned refusal apart at the resolution call, not by code, so non-owned resolver errors stay on stderr.

---

## Work Package WP03: orchestrator-api reads the C2 host refusal; contract 1.19.0 (Priority: P2)

**Goal**: `orchestrator-api check-prerequisites` and `next` classify the new host owned refusal correctly, and `contract_version` is `1.19.0` with a documented change note.
**Independent Test**: A host check-prerequisites C2 owned refusal yields an orchestrator envelope whose `error_code` is the host code (translated for `MISSION_CONTEXT_UNRESOLVED`) and whose message is plain text; every envelope reports `1.19.0`.
**Prompt**: `tasks/WP03-orchestrator-api-c2-host-refusal.md`
**Requirement Refs**: FR-012, FR-013

### Included Subtasks

T013 Red-first classifier tests with a C2 host payload and a string-error host payload (WP03)
T014 `_classify_check_prerequisites_error` reads `error.code` / `error.message` when `error` is a mapping (WP03)
T015 `CONTRACT_VERSION = "1.19.0"`; re-pin the version tests; confirm `runtime_next` refusal handling (WP03)
T016 `docs/api/orchestrator-api.md` version and change note (WP03)

### Dependencies

- Depends on WP02.

---

## Work Package WP04: Off-renderer owned refusals, cross-command pin, changelog (Priority: P2)

**Goal**: `agent mission create` and the move-task owned catch-all emit the same C2 refusal; one parametrized test pins every owned refusal path; the change is in the changelog.
**Independent Test**: The cross-command test drives one owned refusal per in-scope `--json` command and passes, with a same-fixture success control proving the success payloads did not move.
**Prompt**: `tasks/WP04-off-renderer-refusals-and-cross-command-pin.md`
**Requirement Refs**: FR-006, FR-015, NFR-001

### Included Subtasks

T017 `agent mission create` owned refusal → C2 + version stamp; re-pin its tests (WP04)
T018 move-task owned catch-all → C2 via the non-validating builder; re-pin its tests (WP04)
T019 Cross-command shape pin test with same-fixture success control (WP04)
T020 C2 enumeration gate: record the owned refusal cases the gate's structure supports (WP04)
T021 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (WP04)

### Dependencies

- Depends on WP03.

---

## Subtask Index (reference)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red owned legacy-md integration test | WP01 | |
| T002 | Non-owned control + forwarding unit test | WP01 | [P] |
| T003 | `owned` param on the migration | WP01 | |
| T004 | Forward from `_migrate_if_needed` | WP01 | |
| T005 | Blast-radius run | WP01 | |
| T006 | Red renderer + issue-verdict refusal tests | WP02 | |
| T007 | Renderer core | WP02 | |
| T008 | ADR + docstring | WP02 | [P] |
| T009 | Agent mission family call sites | WP02 | |
| T010 | Tasks family call sites | WP02 | |
| T011 | Top-level call sites | WP02 | |
| T012 | Re-pin stale shape tests | WP02 | |
| T013 | Red classifier tests | WP03 | |
| T014 | Classifier reads C2 | WP03 | |
| T015 | Contract 1.19.0 | WP03 | |
| T016 | orchestrator-api docs | WP03 | [P] |
| T017 | mission create C2 | WP04 | |
| T018 | move-task catch-all C2 | WP04 | |
| T019 | Cross-command pin | WP04 | |
| T020 | C2 gate entries | WP04 | |
| T021 | CHANGELOG | WP04 | [P] |
