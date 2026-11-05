---
work_package_id: WP01
title: Retire the row, keep the drivers
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
planning_base_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
merge_target_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
branch_strategy: Planning artifacts for this mission were generated on issue-7217-retire-stale-issue-matrix-md-driver-row. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7217-retire-stale-issue-matrix-md-driver-row unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retire-stale-issue-matrix-md-driver-row-01M6P3EE
base_commit: 6740cad1e04ebf6212683f565fd9bc5449b4694d
created_at: '2026-11-05T15:02:35.275722+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core change
history:
- at: '2026-11-05T15:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_issue_matrix_md_row_retirement_7217.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_issue_matrix_md_row.py
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/supersession.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_issue_matrix_md_row.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- tests/upgrade/test_issue_matrix_md_row_retirement_7217.py
- tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '7217'
---

# Work Package Prompt: WP01 – Retire the row, keep the drivers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objectives & Success Criteria

`3.2.6_gate_artifact_merge_drivers` re-applies on every fresh clone (its `clone_local_effect`
split means the `git config --local` half never travels) and re-appends
`kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix` to `.gitattributes`. The row is
stale: no canonical path writes `issue-matrix.md`, `_MERGE_DRIVERS` declares only the `.json`
pattern, and the mapped driver parses a JSON `rows` array. A shipped migration cannot be edited
(DIRECTIVE_044), so supersede it and give it a successor that keeps the live halves and removes
the row.

Done when:

- `SUPERSEDED_MIGRATIONS` names the retirement, the registry registers a recorded no-op for
  `3.2.6_gate_artifact_merge_drivers`, and its shipped module is byte-identical to `origin/main`.
- A new `4.0.0rc8_retire_issue_matrix_md_row` migration seeds the `acceptance-matrix.json` and
  `issue-matrix.json` rows and both driver configs with their canonical names, and removes the
  retired `.md` row idempotently.
- An upgrade on a project whose `.gitattributes` is already canonical leaves the file's bytes
  unchanged; an upgrade on a project carrying the row removes exactly that row.
- The new test module fails on the pre-fix tree (captured) and passes after the change.

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/7217>
- Spec: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/spec.md`
- Plan: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/plan.md` (D-001..D-006)
- Research: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/research.md`

Read before editing:

- `src/specify_cli/upgrade/supersession.py` — the table, its docstring and `_CARRIED_ATTRIBUTES`.
- `src/specify_cli/upgrade/migrations/_merge_driver_seeding.py` — `DriverSpec`,
  `MergeDriverSeedingMigration.detect()/apply()` (what you inherit and why it is idempotent).
- `src/specify_cli/upgrade/migrations/m_3_2_6_gate_artifact_merge_drivers.py` and
  `m_3_2_6_issue_matrix_driver_repoint.py` — read only; do not edit either.
- `src/specify_cli/upgrade/migrations/m_4_0_0rc8_narrow_agent_gitignore.py` — the house pattern
  for a retire migration (`_plan()`, `detect()` from the plan, `apply()` reporting each removal,
  `can_apply` carrying the reason).
- `src/specify_cli/lanes/consolidation.py` — `_MERGE_DRIVERS`: the canonical names/commands.
- `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` — the supersession
  table test (`SHIPPED_SUPERSEDED` keys must equal `SUPERSEDED_MIGRATIONS`).
- `tests/init/test_init_then_upgrade_is_noop.py` — the end-to-end fixture style to model T001 on.

Constraints:

- **C-001**: do not edit any `m_*.py` that already shipped (both 3.2.6 modules included).
- **C-002**: `_MERGE_DRIVERS` is the single driver declaration; add nothing and remove nothing.
- **C-003**: `order_manifest.txt` is the ordering authority — add exactly one line, in the
  `4.0.0rc8` slot, with a `# tie:` note like its neighbours.
- **C-004**: the driver keeps merging `issue-matrix.json`; never repoint it at Markdown.
- **C-005**: do not relax the architectural merge-driver guard or the supersession table test.
- Complexity ceiling 15 (`ruff` `C901`).

## Branch Strategy

- Single checkout on `issue-7217-retire-stale-issue-matrix-md-driver-row`; completed changes stay
  on that branch, which is the PR head.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first test module

- **Purpose**: Prove the defect through the production entry point before changing `src/`.
- **Steps**: Create `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` with:
  1. **No-op upgrade** (`spec-kitty upgrade --yes` through the typer command, `CliRunner`,
     `catch_exceptions=False`, as `tests/init/test_init_then_upgrade_is_noop.py` does): commit a
     project whose `.gitattributes` carries the canonical merge-driver lines (no `.md` row),
     record the file's bytes, upgrade, assert the bytes and `git status --porcelain` are
     unchanged. **This is the red-first proof**: on the pre-fix tree the upgrade appends the row.
  2. **Second upgrade changes nothing** (NFR-002): upgrade again, same bytes.
  3. **Healing** (FR-003): seed the retired row into the committed file, upgrade, assert the row
     is gone, every other line keeps its content and order, and the removal is reported in the
     upgrade output.
  4. **No driver lost** (FR-002, positive control on the same fixture): after an upgrade on a
     project with no gate-artifact state, both rows are present and
     `git config --local merge.spec-kitty-acceptance-matrix.driver` /
     `merge.spec-kitty-issue-matrix.driver` carry the canonical commands, with
     `merge.spec-kitty-issue-matrix.name` == `Spec Kitty issue matrix row-aware merge`.
  5. **Superseded, not applied** (FR-001): the upgrade records
     `3.2.6_gate_artifact_merge_drivers` as `skipped` in the clone-local ledger partition.
  6. **Unit** (FR-003 idempotence): the successor's `detect()` is True with the row present and
     False after `apply()`; a second `apply()` reports no change; `apply(dry_run=True)` writes
     nothing.
- **Files**: `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` (new)
- **Notes**: run it on the pre-fix tree and save the failure output for the PR body. Use the
  repo's existing fixtures/helpers where they fit (`tests/init/test_init_then_upgrade_is_noop.py`
  builds a committed `init` project); a minimal hand-built project (git repo + `.kittify/
  metadata.yaml` + `.gitattributes`) is acceptable if it stays honest about the production path.

### Subtask T002 – Supersede the historical migration

- **Steps**: In `supersession.py`, add
  `"3.2.6_gate_artifact_merge_drivers": "4.0.0rc8_retire_issue_matrix_md_row",` with a comment in
  the table's house style: it re-applies its stale `issue-matrix.md` row on every fresh clone
  (`clone_local_effect`), the successor keeps the two live rows and removes the retired one, and
  a shipped module is never edited (DIRECTIVE_044).
- **Files**: `src/specify_cli/upgrade/supersession.py`
- **Notes**: keep the docstring's existing explanation; add the new case to it if it enumerates.
  Do not change `_CARRIED_ATTRIBUTES`.

### Subtask T003 – The successor migration

- **Steps**: Create `m_4_0_0rc8_retire_issue_matrix_md_row.py`:

  ```python
  RETIRED_ENTRY = "kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix"

  _DRIVERS = (
      DriverSpec(config_key="spec-kitty-acceptance-matrix",
                 name="Spec Kitty acceptance matrix filled-side merge",
                 command="spec-kitty merge-driver-acceptance-matrix %O %A %B",
                 pattern="kitty-specs/**/acceptance-matrix.json"),
      DriverSpec(config_key="spec-kitty-issue-matrix",
                 name="Spec Kitty issue matrix row-aware merge",
                 command="spec-kitty merge-driver-issue-matrix %O %A %B",
                 pattern="kitty-specs/**/issue-matrix.json"),
  )

  @MigrationRegistry.register
  class RetireIssueMatrixMdRowMigration(MergeDriverSeedingMigration):
      migration_id = "4.0.0rc8_retire_issue_matrix_md_row"
      target_version = "4.0.0rc8"
      drivers = _DRIVERS
  ```

  with `detect()` = `super().detect(...) or retired row present`, and `apply()` = seed (call
  `super().apply()`), then remove every line whose stripped text equals `RETIRED_ENTRY`, reporting
  `Removed .gitattributes entry: ...` (or `Would remove ...` under `dry_run`). Report a no-change
  line when nothing was removed and nothing was seeded.
- **Files**: `src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_issue_matrix_md_row.py` (new)
- **Notes**: line-exact removal, no re-sorting, no blank-line collapsing, keep the file's
  trailing newline behaviour. The module docstring must record *which side was wrong* (the row,
  not the driver) and why the acceptance half is re-seeded. `clone_local_effect` is inherited
  and must stay True.

### Subtask T004 – Manifest slot

- **Steps**: Add `4.0.0rc8_retire_issue_matrix_md_row  # tie: shares target_version 4.0.0rc8
  with 4.0.0rc8_retire_antigravity_workflows; runs after 3.2.6_issue_matrix_driver_repoint so it
  removes the row the historical seeding migration writes` in the `4.0.0rc8` block (after
  `4.0.0rc8_retire_antigravity_workflows`, before `4.0.0rc8_retire_stale_mission_template_forks`
  — the auto-discovery order for the new filename).
- **Files**: `src/specify_cli/upgrade/migrations/order_manifest.txt`

### Subtask T005 – Extend the supersession table test

- **Steps**: Add `GateArtifactMergeDriverMigration` to `SHIPPED_SUPERSEDED` in
  `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` (its keys must equal
  `SUPERSEDED_MIGRATIONS`) and update the comment listing the covered families.
- **Files**: `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`

### Subtask T006 – Verification

- `uv run pytest tests/upgrade/test_issue_matrix_md_row_retirement_7217.py -q`
- `uv run pytest tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py tests/architectural/test_migration_order_manifest.py tests/architectural/test_merge_reconciliation_class_guard.py -q`
- `uv run pytest tests/upgrade/test_clone_local_migration_idempotent.py -q`
- `uv run ruff check src/specify_cli/upgrade tests/upgrade/test_issue_matrix_md_row_retirement_7217.py`
- `uv run ruff format --check --force-exclude <touched files>`
- `uv run mypy src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_issue_matrix_md_row.py`
- Do not run `make test-full`. Record commands and pass/fail counts for the PR body.

## Test Strategy

Red-first (DIRECTIVE_034): T001 case 1 goes red on the pre-fix tree (the row is appended).
Case 4 is the positive control that the retirement did not take the drivers with it. Case 3 must
go red if only the removal is reverted; case 1 must go red if only the supersession entry is
reverted (`acceptance-criteria-non-vacuity`, "prove compound fixes half by half").

## Risks & Mitigations

- **The acceptance half is lost** → case 4 fails; the fixture starts with no gate-artifact state.
- **The removal rewrites the file** → case 3 diffs line by line.
- **The successor never settles** → `detect()` must be False after `apply()`; case 6 pins it.
- **A shipped module is edited by accident** → `git diff origin/main -- src/specify_cli/upgrade/migrations/m_3_2_6_*.py` must be empty.

## Review Guidance

- Does the successor's `detect()` go False after `apply()` on every fixture (including a
  non-git project and an absent `.gitattributes`)?
- Is the retired row the *only* thing removed, and is the removal reported?
- Are the canonical driver names/commands identical to `_MERGE_DRIVERS` (no second truth)?
- Are the 3.2.6 modules byte-identical to `origin/main`?
- Is the manifest line in the right slot and does the order gate pass?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done` and add
history notes as you go (`spec-kitty agent tasks add-history WP01 --note "..."`).
