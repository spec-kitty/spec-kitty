# Work Packages: Reconcile the migration-ledger ADR visibility wording

**Inputs**: Design documents from `/kitty-specs/ledger-adr-visibility-wording-01M68ZKY/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required — this is a documentation defect. A docs guard that binds the ADR's current
visibility decision to the live Typer surface is written and shown red against the unfixed ADR
before the wording changes (DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package must be independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `docs/`, `tests/docs/`

---

## Work Package WP01: Reconcile ADR §5/#E and add the visibility guard (Priority: P1) 🎯 MVP

**Goal**: The ADR's current visibility decision names `spec-kitty migrate ledger [--json]` and its
single pending source, keeps the rejected `doctor migrations` / `upgrade --list-applied` proposal
as marked history, and a docs guard fails if the current decision ever names an unregistered
command path again.
**Independent Test**: Run the new guard against the pre-fix ADR (red: `doctor migrations` is not a
registered path), then against the reconciled ADR (green, with `migrate ledger` named in both §5
and #E). `check_docs_freshness --ci` reports errors=0 and the ADR/docs structural tests pass.
**Prompt**: `/tasks/WP01-reconcile-adr-and-guard.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-004

### Included Subtasks

T001 Write the docs guard `tests/docs/test_migration_ledger_adr_visibility.py` and prove it fails on the current ADR
T002 Rewrite §5: name `spec-kitty migrate ledger [--json]` and the single pending source; mark the doctor/flag proposal historical, with the reason it was not built
T003 Rewrite the #E deliverable bullet to the shipped command, and re-frame the closeout note so it records the decision instead of a live divergence
T004 Rename the §5 heading's "two read surfaces" claim and keep partition / pending / audit-only drift wording aligned with `migrate_ledger`'s tokens
T005 Regenerate the page's derived surfaces (`docs_index --write`, `freshen_adr_inventory`) and confirm the diff is confined to this page
T006 Run the guard green plus the ADR/docs tests and the page-level lint, and record the results

### Implementation Notes

- The guard must be red **before** any ADR edit: it is the red-first proof quoted in the PR.
- Scan only §5's body and the #E bullet. Do not build a tree-wide "every command in every ADR
  exists" gate: other ADRs legitimately record proposals that never shipped (research D4).
- Keep the rejected names as bare prose (no `spec-kitty …` snippet), or the guard would flag the
  historical paragraph.
- §5's semantics must match `migrate_cmd.py`: states `in-place` / `recorded-elsewhere` /
  `pending`, two partitions tracked + clone-local, drift reported only (never re-applied). The
  words change only where the command identity was wrong.
- Set `SPEC_KITTY_ENABLE_SAAS_SYNC` / `SPEC_KITTY_NO_UPGRADE_CHECK` before importing
  `specify_cli` in the guard, mirroring the existing tests/architectural parity test.

### Parallel Opportunities

- T002 and T003 are separate sections of one file; do them in one pass to keep the §5/#E voice
  consistent.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Heading rename drifts the committed retrieval index → regenerate with
  `uv run python -m scripts.docs.docs_index --write` and confirm the diff touches only this page's
  anchors (the freshness gate reports `DOCS-INDEX-DRIFT` otherwise).
- Over-editing → the change is the visibility decision, not a rewrite of the ADR; leave §1–§4, §6
  and the amendments untouched.

---

## Work Package WP02: Changelog and docs gates (Priority: P2)

**Goal**: The user-facing decision-record change is recorded under `[Unreleased]` with before/after,
and the docs gates for the edited page pass.
**Independent Test**: `docs/changelog/CHANGELOG.md` carries the `[Unreleased]` entry with the
`(#6362)` reference; `check_docs_freshness --ci` reports errors=0; the ADR spelling/structural
checks pass for `docs/adr/**` with no new allowlist entries.
**Prompt**: `/tasks/WP02-changelog-and-docs-gates.md`
**Requirement Refs**: NFR-001, NFR-002, SC-003

### Included Subtasks

T007 Add the `[Unreleased]` changelog entry (impact-first lead, `(#6362)`, before/after, under 1,200 characters)
T008 Run the docs gates for the edited page (freshness, spelling, ADR structural) and record the results

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file, never replace
  the symlink.
- Only touch the docs surface this change affects (shared machine state: do not rebuild the whole
  CLI reference).

### Parallel Opportunities

- None meaningful; T008 verifies T007's page too.

### Dependencies

- Depends on WP01 (the changelog must describe the reconciled ADR).

### Risks & Mitigations

- Docs index drift → `check_docs_freshness --ci` (expect errors=0); cite any pre-existing red in
  the PR `## Deferred` rather than papering over it.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none; WP02 records and verifies what WP01 ships.
- **MVP Scope**: WP01.
