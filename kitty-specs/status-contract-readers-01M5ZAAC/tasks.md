# Work Packages: Status contract readers

**Inputs**: Design documents from `kitty-specs/status-contract-readers-01M5ZAAC/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/status-actor.md, quickstart.md

**Tests**: Required. The charter's ATDD-first rule applies: every WP opens with a failing test through the pre-existing entry point, committed before the implementation commits.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first derivation and parity tests for the lane constants | WP01 | |
| T002 | Derive `PACKAGE_LANES`, `NON_AUTHORABLE_LANES`, `CANONICAL_LANES` from the package | WP01 | |
| T003 | Pin the authorable-lane consumers (frontmatter validation, transition validation, merge order) | WP01 | [P] |
| T004 | Docstrings and cold-import note for the lane module | WP01 | [P] |
| T005 | Red-first unit tests for the actor value, decoder and identity rule | WP02 | |
| T006 | New `status/actor.py`: `ProfileSource`, `role_for_hop`, `resolve_profile`, `build_status_actor`, `planned_profile_for_wp` | WP02 | |
| T007 | Widen `decode_actor` to the 5-key shape without loosening it | WP02 | [P] |
| T008 | `actor_full_identity` drops a `wp_frontmatter` profile | WP02 | [P] |
| T009 | `ResolvedBinding.profile_source` stamped by `_resolve_dispatch_binding` | WP02 | |
| T010 | `build_resolved_actor` / `build_self_asserting_actor` delegate to the new builder; exports | WP02 | |
| T011 | Red-first CLI tests for every move-task hop and the verdict note | WP03 | |
| T012 | move-task transitions always carry the structured actor | WP03 | |
| T013 | move-task paired note carries its hop's structured actor | WP03 | |
| T014 | Verdict annotation carries a reviewer actor | WP03 | [P] |
| T015 | Re-run move-task / review-role / claim suites; fix only real regressions | WP03 | |
| T016 | Red-first CLI tests for mark-status, add-history and action implement/review annotations | WP04 | |
| T017 | mark-status `--agent` option and structured actor | WP04 | |
| T018 | add-history structured actor (role from the WP's current lane) | WP04 | [P] |
| T019 | action implement/review annotations carry the structured actor | WP04 | |
| T020 | Red-first tests for `agent status emit` and orchestrator-api transitions | WP05 | |
| T021 | `agent status emit` writes the structured actor | WP05 | |
| T022 | orchestrator-api lifecycle transitions write the structured actor | WP05 | |
| T023 | Docs: status-model actor section; changelog `[Unreleased]` entry; changelog #101/#102 citation (#6271) | WP05 | [P] |
| T024 | Red-first test: a structured `migration:` actor is skipped by the timestamp-continuity check | WP06 | |
| T025 | Route the seed check through `is_migration_actor` | WP06 | |
| T026 | Correct the events #101/#102 citations in code and test docstrings | WP06 | [P] |

---

## Work Package WP01: Lanes derived from the events package (Priority: P2)

**Goal**: `status_lanes.py` holds no hand-typed lane list; the authorable lanes are an explicit, ordered subset of `spec_kitty_events.status.Lane`.
**Independent Test**: `pytest tests/status/test_status_lanes_derivation.py` plus the existing lane-consumer tests.
**Prompt**: `tasks/WP01-lanes-derived-from-events-package.md`
**Requirement Refs**: FR-001, FR-002, FR-003, SC-004

### Included Subtasks

T001 Red-first derivation and parity tests for the lane constants (WP01)
T002 Derive `PACKAGE_LANES`, `NON_AUTHORABLE_LANES`, `CANONICAL_LANES` from the package (WP01)
T003 [P] Pin the authorable-lane consumers (WP01)
T004 [P] Docstrings and cold-import note for the lane module (WP01)

### Implementation Notes

- Keep the name `CANONICAL_LANES` (8 importers, public in `status.__all__`); add the two new names.
- `spec_kitty_events` is already loaded by every CLI invocation (even `--version`), so the import adds no CLI cost.

### Dependencies

- None.

### Risks & Mitigations

- Import cycle: `status_lanes` imports only `spec_kitty_events.status`. The cold-import gate (`tests/architectural/test_cold_import_status_boundary.py`) forbids `specify_cli.status*`, not the events package; run it.

---

## Work Package WP02: Actor value, provenance and readers (Priority: P1)

**Goal**: one pure builder for `{tool, role, profile, profile_source, model}`, a decoder that reads every shape, and an identity rule that ignores planned (frontmatter) profiles.
**Independent Test**: `pytest tests/status/test_status_actor.py` plus `tests/status/test_actor_identity_reconciliation_4665.py`, `tests/unit/status/test_review_roles.py`.
**Prompt**: `tasks/WP02-actor-value-provenance-and-readers.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-012, FR-013, FR-014, NFR-001, NFR-002, NFR-003

### Included Subtasks

T005 Red-first unit tests for the actor value, decoder and identity rule (WP02)
T006 New `status/actor.py` (WP02)
T007 [P] Widen `decode_actor` (WP02)
T008 [P] `actor_full_identity` drops a `wp_frontmatter` profile (WP02)
T009 `ResolvedBinding.profile_source` stamped by `_resolve_dispatch_binding` (WP02)
T010 Existing builders delegate; exports (WP02)

### Dependencies

- None.

### Risks & Mitigations

- `decode_actor`'s exact-key check guards against silent corruption (FR-015 of an earlier mission); widen to exactly two accepted key sets, never "any superset".

---

## Work Package WP03: move-task and verdict writers (Priority: P1)

**Goal**: every `move-task` hop, its paired note and the verdict note write the structured actor.
**Independent Test**: `pytest tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py`.
**Prompt**: `tasks/WP03-move-task-and-verdict-writers.md`
**Requirement Refs**: FR-006, FR-007, FR-010, SC-001, SC-002, C-004

### Included Subtasks

T011 Red-first CLI tests for every move-task hop and the verdict note (WP03)
T012 move-task transitions always carry the structured actor (WP03)
T013 move-task paired note carries its hop's structured actor (WP03)
T014 [P] Verdict annotation carries a reviewer actor (WP03)
T015 Re-run move-task / review-role / claim suites (WP03)

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- #6715 edits `tasks_move_task.py`; keep edits to actor construction and rebase after it if it lands first.

---

## Work Package WP04: mark-status, add-history and action writers (Priority: P1)

**Goal**: subtask marks, history notes and the implement/review annotations write the structured actor; mark-status gains `--agent`.
**Independent Test**: `pytest tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py`.
**Prompt**: `tasks/WP04-mark-status-add-history-and-action-writers.md`
**Requirement Refs**: FR-008, FR-009, SC-001, SC-002

### Included Subtasks

T016 Red-first CLI tests (WP04)
T017 mark-status `--agent` option and structured actor (WP04)
T018 [P] add-history structured actor (WP04)
T019 action implement/review annotations carry the structured actor (WP04)

### Dependencies

- Depends on WP02.

---

## Work Package WP05: status emit, orchestrator-api and docs (Priority: P2)

**Goal**: the remaining named writers carry the actor; docs and changelog describe the shape.
**Independent Test**: `pytest tests/status/test_status_emit_structured_actor_6400.py tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py`.
**Prompt**: `tasks/WP05-status-emit-orchestrator-api-and-docs.md`
**Requirement Refs**: FR-011, C-001, C-003, C-005

### Included Subtasks

T020 Red-first tests (WP05)
T021 `agent status emit` writes the structured actor (WP05)
T022 orchestrator-api lifecycle transitions write the structured actor (WP05)
T023 [P] Docs and changelog (WP05)

### Dependencies

- Depends on WP02.

---

## Work Package WP06: #6271 landing follow-ups (Priority: P3)

**Goal**: `status validate`'s timestamp-continuity check uses the shared seed predicate; code and test docstrings cite the diary-reducer fix as spec-kitty-events PR #102 (issue #101).
**Independent Test**: `pytest tests/status/test_validate_seed_predicate_6271.py`.
**Prompt**: `tasks/WP06-6271-landing-follow-ups.md`
**Requirement Refs**: FR-015, FR-016

### Included Subtasks

T024 Red-first test for a structured `migration:` actor (WP06)
T025 Route the seed check through `is_migration_actor` (WP06)
T026 [P] Correct the events #101/#102 citations (WP06)

### Dependencies

- None.

---

## Dependency & Execution Summary

- WP01, WP02 and WP06 start in parallel. WP03, WP04, WP05 follow WP02 and can run in parallel (disjoint files).
- MVP: WP02 + WP03 (the move-task path is where the issue was observed).
