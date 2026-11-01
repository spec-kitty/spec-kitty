# Work Packages: `upgrade --dry-run` names its migration list for what it is

**Inputs**: Design documents from `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/`
**Prerequisites**: spec.md, plan.md, research.md, quickstart.md
**Governing issue**: [#6234](https://github.com/spec-kitty/spec-kitty/issues/6234)

**Organization**: Two work packages. WP01 is the renderer decision plus the red-first
correction of the two dry-run assertions; WP02 is the operator-facing documentation and the
changelog the change needs.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files/components).
- Subtasks are reference rows; completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The mode-dependent heading and its corrected goldens (Priority: P0)

**Goal**: A dry run heads its migration list `Migrations that would be applied:` with a
non-success marker, chosen once from `result.dry_run`; a real run keeps `Migrations applied:`
with `✓` byte for byte; every dry-run assertion in the suite asserts the corrected text.
**Independent Test**: `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py
-k golden_applied -q` passes with the new dry-run golden and an unedited `_GOLDEN_APPLIED`.
**Prompt**: `tasks/WP01-mode-dependent-heading.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-005

### Included Subtasks

- T001 Red-first: add the corrected dry-run assertions to the golden module and watch them fail
  on the current renderer (they fail today because the output says `Migrations applied:`/`✓`)
- T002 `_display_upgrade_results`: choose the heading and the entry marker once, from `result.dry_run`
- T003 Update `_GOLDEN_APPLIED_DRY_RUN` and its comment/docstring to the corrected text, citing #6234;
  leave `_GOLDEN_APPLIED` unedited as the mode control
- T004 Update `tests/upgrade/test_dry_run_sequenced_verdict_cli.py` to assert the dry-run heading
  and add the negative assertion that the real-run heading is absent
- T005 Reword the `_print_predicted_verdicts` docstring so it names neither mode's literal heading
- T006 Targeted suites, `ruff check`, `ruff format --check`, `mypy` for the touched files

### Implementation Notes

- `_display_upgrade_results` already branches on `result.dry_run` for the panel; extend that
  branch, do not add a second one elsewhere.
- `_print_upgrade_section` returns early on an empty list: the heading must stay selected, never
  force-printed, so a dry run with nothing applicable still prints no heading.
- Marker choice: `→` (yellow) for the preview, `✓` (green) for the real run, `○` (dim) stays the
  skip marker. `→` is already the CLI's consequence arrow on the auto-commit line.
- No assertion may be deleted, skipped or xfailed: each existing dry-run assertion is retargeted
  to the corrected text, and the real-run goldens stay untouched (C-004).
- Keep `_display_upgrade_results` under the cyclomatic ceiling of 15; it gains one `if/else`.

### Parallel Opportunities

- T003, T004 and T005 touch different files and can follow T002 independently.

### Dependencies

- None (starting package). WP02 depends on this.

### Risks & Mitigations

- Renaming the heading in both modes → `_GOLDEN_APPLIED` (unedited) fails, so the positive
  control catches it.
- "Helpfully" cleaning the skipped heading too → out of scope (research D5); the review checks
  the diff for it.
- A golden edit that also "tidies" unrelated lines → keep the golden diff to the two changed
  lines so the pair stays readable.

---

## Work Package WP02: The operator docs and the changelog (Priority: P1)

**Goal**: Tell an operator what the preview's list is called, and record the change in the
unreleased changelog as a fragment.
**Independent Test**: the how-to page names the dry-run heading and the real-run heading, and
`docs/changelog/unreleased/6234.fixed.md` passes `scripts.docs.check_changelog_style` and
`scripts.docs.check_spelling --pass unreleased`.
**Prompt**: `tasks/WP02-operator-docs-and-changelog.md`
**Requirement Refs**: FR-004, SC-001, SC-002, SC-003, SC-004
**Dependencies**: WP01

### Included Subtasks

- T007 One sentence in `docs/guides/how-to/installation/upgrade-project.md` naming both headings
  and the `→` marker, next to the existing `--dry-run` invocation
- T008 `docs/changelog/unreleased/6234.fixed.md`: impact-first lead with `(#6234)`, before/after,
  under 1,200 characters, US spelling
- T009 Changelog style, spelling and docs-freshness checks for the touched surface

### Implementation Notes

- The changelog is a fragment under `docs/changelog/unreleased/` (the repository's stated
  convention), **not** an edit to `docs/changelog/CHANGELOG.md`.
- Do not rewrite a sample output block: the how-to page carries none, so one sentence is the
  whole docs change.
- Machine paths and personal data never enter a doc or commit.

### Parallel Opportunities

- T007 and T008 are independent files.

### Dependencies

- Depends on WP01 (the docs must describe the shipped wording).

### Risks & Mitigations

- A docs-index rebuild reads the installed CLI's shared global cache on this host → touch no
  indexed page inventory, and verify with `check_docs_freshness --ci` (errors=0) instead of
  trusting a rebuild.
