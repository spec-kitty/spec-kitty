---
work_package_id: WP03
title: Changelog, issue verdict, verification sweep
dependencies:
- WP01
- WP02
requirement_refs:
- FR-006
- NFR-004
- SC-004
planning_base_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
merge_target_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
branch_strategy: Planning artifacts for this mission were generated on issue-7217-retire-stale-issue-matrix-md-driver-row. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7217-retire-stale-issue-matrix-md-driver-row unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retire-stale-issue-matrix-md-driver-row-01M6P3EE
base_commit: 0a0ae6bccac0bbd0aef4fbcbb930bde2620e7e44
created_at: '2026-11-05T15:55:45.800044+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 3 - Hand-off
history:
- at: '2026-11-05T15:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/unreleased/
create_intent: []
execution_mode: code_change
owned_files:
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs:
- '7217'
---

# Work Package Prompt: WP03 – Changelog, issue verdict, verification sweep

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objectives & Success Criteria

The change is operator-visible (`spec-kitty upgrade` stops modifying a tracked file, and heals a
file it previously dirtied), so it needs a changelog fragment, a terminal issue verdict and a
verification sweep over the touched surfaces.

Done when:

- `docs/changelog/unreleased/<pr>.fixed.md` exists with the bold impact-first lead, the `(#7217)`
  reference, and before/after, under 1,200 characters — and `check_changelog_style` +
  `check_spelling` pass.
- The mission's `issue-matrix.json` carries a `fixed` row for #7217 with its evidence refs.
- The targeted suites and linters pass on the branch tip.
- No docs page describes the retired row as current behaviour.

## Context & Constraints

- Fragment rules: `docs/changelog/unreleased/README.md` (name `<pr>.fixed.md`, no heading, do not
  edit `docs/changelog/CHANGELOG.md` — since #6988 the changelog is assembled from fragments and
  the old `[Unreleased]` shape is rejected by `check_changelog_style`).
- The historical #6416 entry in `docs/changelog/CHANGELOG.md` mentions the inert line as the
  *then*-intended behaviour; it is history and stays untouched.
- `spec-kitty agent issue-verdict` sets the matrix verdict; record the test and PR evidence.

## Subtasks & Detailed Guidance

### Subtask T001 – Changelog fragment

- **Steps**: Write `docs/changelog/unreleased/<pr>.fixed.md` (rename to the PR number once it
  exists) in the house style: lead with the operator impact, cite `(#7217)`, then **Before:**
  the first `upgrade` on a fresh clone re-added `kitty-specs/**/issue-matrix.md
  merge=spec-kitty-issue-matrix` and left `.gitattributes` dirty; **After:** the row is retired
  (`3.2.6_gate_artifact_merge_drivers` superseded), an upgrade leaves the file untouched or heals
  it, and the `acceptance-matrix.json` / `issue-matrix.json` drivers are unchanged.
- **Files**: `docs/changelog/unreleased/<pr>.fixed.md`
- **Notes**: no machine-local paths, no personal data. Run
  `uv run --frozen python -m scripts.docs.check_changelog_style` and
  `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

### Subtask T002 – Issue verdict

- **Steps**: Set the #7217 row to `fixed` via the issue-verdict seam
  (`spec-kitty agent issue-verdict ...`, or the mission's `issue-matrix.json` edited through the
  supported writer), with evidence refs to the retirement test and the PR.
- **Files**: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/issue-matrix.json`

### Subtask T003 – Verification sweep

- **Steps**: Run, and record the counts for the PR body:
  - `uv run pytest tests/upgrade/test_issue_matrix_md_row_retirement_7217.py tests/init/test_init_then_upgrade_is_noop.py tests/upgrade/test_dry_run_sequenced_verdict.py tests/upgrade/test_dry_run_sequenced_verdict_cli.py -q`
  - `uv run pytest tests/specify_cli/upgrade/ tests/architectural/test_migration_order_manifest.py tests/architectural/test_merge_reconciliation_class_guard.py -q`
  - `uv run pytest tests/init/ tests/terminus/test_clone_init_installs_merge_drivers.py -q`
  - `uv run ruff check src/specify_cli/upgrade tests/upgrade tests/init`
  - `uv run ruff format --check --force-exclude <touched files>`
  - `uv run mypy src/specify_cli/upgrade` (project-configured invocation)
  - `git diff origin/main -- src/specify_cli/upgrade/migrations/m_3_2_6_gate_artifact_merge_drivers.py src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py` → must be empty (NFR-003)
- Do not run `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION).

### Subtask T004 – Docs check

- **Steps**: `rg -n "issue-matrix.md merge" docs/ site/` — the only hit must be the historical
  changelog entry. Fix any page that states the retired row as current behaviour (there is no
  merge-driver reference page today; add nothing new).

## Test Strategy

This work package adds no behaviour; its tests are the documentation gates (changelog style,
spelling, docs freshness where touched) plus the sweep that proves WP01/WP02 together.

## Risks & Mitigations

- **Editing the root changelog** → forbidden; fragments only.
- **A docs page drifts** → T004 greps and only touches pages describing current behaviour.
- **A pre-existing red mistaken for ours** → reproduce on pristine `origin/main` before claiming
  it, and record it in the PR's `## Deferred`.

## Review Guidance

- Does the fragment read as impact → before → after, with the issue reference?
- Is the issue verdict terminal with evidence?
- Does the sweep cover the retired row *and* the drivers that must survive?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done`.
