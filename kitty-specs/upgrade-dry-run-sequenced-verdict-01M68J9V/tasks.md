# Work Packages: Upgrade dry-run reports the sequenced verdict a real run reaches

**Inputs**: Design documents from `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, quickstart.md
**Governing issue**: [#6552](https://github.com/spec-kitty/spec-kitty/issues/6552)

**Organization**: Two work packages. WP01 is the sequencing decision and its red-first tests;
WP02 is the operator-surface witness and the documentation the change needs.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files/components).
- Subtasks are reference rows; completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The one sequencing decision (Priority: P0)

**Goal**: The dry run decides each migration on the sequenced view the real runner produces —
a declared predecessor's application makes its dependent apply — and an unpredicted dry-run
skip stops claiming target state.
**Independent Test**: On a fixture project holding the reported 3.2.6 pair, `dry_run=True`
and `dry_run=False` runs report the same `migrations_applied`; an undeclared ordering pair
is reported `not needed on the current tree`; the dry run leaves the tree and both ledger
partitions unchanged.
**Prompt**: `tasks/WP01-sequencing-decision.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

- T001 Red-first: the new test module fails on the pre-fix tree (parity, wording, `can_apply`, no-writes)
- T002 `BaseMigration.sequenced_after`: the detect-input declaration
- T003 Runner: the run's applied set, the prediction branch, the dry-run skip wording
- T004 `3.2.6_issue_matrix_driver_repoint` declares `3.2.6_gate_artifact_merge_drivers`
- T005 Targeted suites, ruff, format, mypy for the touched modules

### Implementation Notes

- The prediction reuses the existing `can_apply` gate; do not duplicate its exception handling.
- `_apply_migration` stays at or below the cyclomatic ceiling of 15 (extract helpers if not).
- The real-run (`dry_run=False`) paths, messages and records must not change.

### Parallel Opportunities

- T002 and T004 are small and independent of T003's mechanics, but the test in T001 pins all three.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A real-run branch added by accident → C-002 tests assert the real-run wording and applied set.
- `not needed` wording pinned by two existing tests → both keep the substring `not needed`.

---

## Work Package WP02: The operator witness and the docs (Priority: P1)

**Goal**: Prove the fix through the CLI surface an operator actually uses, and document the
new declaration and the changed wording.
**Independent Test**: `spec-kitty upgrade --dry-run` on the fixture prints the predicted
migration under `Migrations applied:` with its `dry-run: would apply after ...` line, and the
changelog/docs describe the change.
**Prompt**: `tasks/WP02-operator-witness-and-docs.md`
**Requirement Refs**: FR-006, SC-001, SC-002, SC-003, SC-004, C-004
**Dependencies**: WP01

### Included Subtasks

- T006 CLI-level dry-run witness through the `upgrade` typer command
- T007 `migrations/README.md`: when and how to declare `sequenced_after`
- T008 `[Unreleased]` changelog entry for #6552
- T009 Targeted suites, format/lint, docs freshness check

### Implementation Notes

- The CLI test must assert rendered output, not a helper, or it is vacuous
  (`acceptance-criteria-non-vacuity`).
- The changelog entry is impact-first, under 1,200 characters, with `(#6552)`.

### Parallel Opportunities

- T007 and T008 are independent of T006.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- A docs-freshness rebuild reads a shared global cache on this host → regenerate only what the diff introduces and verify with `check_docs_freshness --ci` (errors=0).
