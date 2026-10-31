---
description: "Work packages for upgrade-cutover-preserves-retired-commands-01M68J8W"
---

# Work Packages: The ledger cutover preserves the retired project command files it inherits

**Inputs**: Design documents from `kitty-specs/upgrade-cutover-preserves-retired-commands-01M68J8W/`
**Prerequisites**: plan.md, spec.md (no contracts: this is an internal migration-selection change with no API surface)

**Tests**: Required, red-first. The reproduction is written and observed failing through
`MigrationRunner.upgrade` before the declaration that fixes it exists (DIRECTIVE_034,
`test-first-bug-fixing`). Every WP ships its tests in the same commit as the code.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is
independently deliverable and testable.

**Prompt Files**: Each work package references a prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (a different file or component).
- Subtasks are **reference rows**, not checkboxes. Record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Red-first reproduction and the ledger-shape regression suite (Priority: P1)

**Goal**: A regression module that reproduces #6547 through the production entry point and pins the
post-fix contract for every ledger shape, every user-file case, and the legacy retire path.
**Independent Test**: `uv run pytest tests/specify_cli/upgrade/test_retired_command_writers_6547.py -q`
— red on `HEAD` before WP02 lands (the post-cutover fixture gains 14 files), green after.
**Prompt**: `tasks/WP01-red-first-reproduction.md`
**Requirement Refs**: FR-001, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, SC-001, SC-002

### Included Subtasks

T001 Post-cutover fixture: metadata at rc7, a ledger settling `4.0.0rc8_backfill_migration_ledger`,
`3.1.2_globalize_commands` and `3.2.0a4_safe_globalize_commands`, one user-authored command file (WP01)
T002 Red assertion: `2.1.4_enforce_command_file_state` applies and 14 `spec-kitty.*` files appear (WP01)
T003 Green contract: three consecutive upgrades leave exactly the user file; neither writer applies;
both are recorded with a `superseded_by` note (WP01)
T004 [P] Parametrised ledger shapes: pre-ledger (floor settles both writers), ledger-era settled, and
post-cutover-without-floor — same final directory contents (WP01)
T005 [P] Legacy fixture: generated local command files with version markers are still retired by the
retire path; a `spec-kitty.custom.md` without a marker is never touched (positive control) (WP01)
T006 [P] Dry-run assertion: `upgrade --dry-run` lists no write to a project-local command file (WP01)

### Implementation Notes

- Drive `MigrationRunner(project).upgrade("4.0.0rc8", include_worktrees=False)`; never call
  `2.1.4`'s `apply()` directly, because the defect is in selection plus registration, not in `apply()`.
- Build fixtures without touching the machine's `~` state beyond `tmp_path`; do not assert on the
  presence of `~/.kittify` or `~/.claude`. The retire path's "generated, no global equivalent" branch
  is the stable, machine-independent one.
- Call `MigrationRegistry.clear()` + `auto_discover_migrations()` in an autouse fixture, as the
  neighbouring supersession test does, so the real registry (with supersession applied) is under test.

### Dependencies

- None (starting package). It must be authored and seen red before WP02.

### Risks & Mitigations

- A test that only asserts absence cannot tell "nothing written" from "probe sees nothing": T005 adds
  the same-fixture positive control (a file the probe must observe).
- Writing command files can be refused by a read-only generated file left by an earlier test on the
  same fixture; use a fresh `tmp_path` per case.

---

## Work Package WP02: Declare both pre-globalize writers superseded (Priority: P1)

**Goal**: Make `2.1.4_enforce_command_file_state` and `3.0.2_restore_prompt_commands` recorded no-ops
through the registry supersession table, and extend the table's invariant tests to cover them.
**Independent Test**: `uv run pytest tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py
tests/specify_cli/upgrade/test_retired_command_writers_6547.py -q` — WP01's module flips to green and
the table invariants (identity, `content_hash`, manifest order, direct import) hold for the new entries.
**Prompt**: `tasks/WP02-supersede-the-writers.md`
**Requirement Refs**: FR-002, FR-006, C-001, C-002, C-003, SC-003, SC-004

### Included Subtasks

T007 Add both entries to `SUPERSEDED_MIGRATIONS`, successor `3.2.0a4_safe_globalize_commands`, with the
comment naming #6547 and why the retirement supersedes the writes (WP02)
T008 Extend `SHIPPED_SUPERSEDED` in the `#6589` invariant test with the two shipped classes (WP02)
T009 Confirm the shipped modules are byte-identical (`git diff --stat origin/main -- src/specify_cli/upgrade/migrations/`)
and that `compute_content_hash` of each substitute equals the shipped class's (WP02)

### Implementation Notes

- Declare once, in `src/specify_cli/upgrade/supersession.py`. Do not add a branch to
  `get_applicable`, the runner, or the backfill (C-001).
- Do not edit `m_2_1_4_enforce_command_file_state.py`, `m_3_0_2_restore_prompt_commands.py`,
  `m_3_1_2_globalize_commands.py` or `m_3_2_0a4_safe_globalize_commands.py` (C-002, DIRECTIVE_044).
  The stale version-window sentence in the 3.1.2 docstring is a shipped-module comment; if a docs
  correction is wanted, it belongs in the upgrade reference page, not in the module.

### Dependencies

- WP01 (the red-first module must exist and have been seen red).

### Risks & Mitigations

- Silencing the writers removes the refresh-before-retire step for a pre-3.1.2 project. WP01 T005 pins
  that the retire path still removes marked local files, so FR-004 cannot regress silently.

---

## Work Package WP03: Changelog and upgrade reference (Priority: P2)

**Goal**: Tell a project owner that an upgrade no longer reintroduces the retired project-local
commands, and that no local action is needed.
**Independent Test**: the `[Unreleased]` entry validates (bold impact-first lead, `(#6547)`,
before/after, under 1,200 characters); the upgrade reference names the same behaviour.
**Prompt**: `tasks/WP03-changelog-and-docs.md`
**Requirement Refs**: FR-007, SC-004

### Included Subtasks

T010 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry referencing #6547 (WP03)
T011 One paragraph in the upgrade reference doc that describes the global command install and the
retirement of project-local copies (WP03)
T012 `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0) when a regenerated index is
touched; otherwise confirm no index surface changed (WP03)

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the target only.
- Keep the entry user-facing: what an operator sees before and after, not the table internals.

### Dependencies

- WP02 (the behaviour it documents must exist).

### Risks & Mitigations

- A docs-index rebuild reads the shared installed-CLI cache (shared machine state). Regenerate only the
  surface the diff changes and verify with `check_docs_freshness --ci` rather than a full rebuild.
