---
work_package_id: WP05
title: Docs, CHANGELOG, retrieval index
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-006
- NFR-004
planning_base_branch: fix/move-task-approval-ergonomics
merge_target_branch: fix/move-task-approval-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/move-task-approval-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/move-task-approval-ergonomics unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
phase: Phase 2 - Polish
history:
- at: '2026-09-20T19:15:00Z'
  actor: system
  action: Prompt generated for move-task-approval-ergonomics mission
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/development/reference/issue-matrix-verdicts.md
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
- docs/development/reference/issue-matrix-verdicts.md
- docs/development/3-2-docs-retrieval-index.yaml
- docs/development/3-2-page-inventory.yaml
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3469'
---

# Work Package Prompt: WP05 – Docs, CHANGELOG, retrieval index

## ⚡ Do This First: Load Agent Profile

Load the `scribe-sally` profile (role: implementer/documentation) via the profile-load skill first.
Then read `spec.md`, `quickstart.md`, and the landed WP02 ADR + WP03 behavior. Docs mirror SHIPPED
behavior — verify against the merged code, not the spec, before writing.

## Objective

Document the user-facing change (the `not-applicable` verdict, the reference classification, the
move-task aliases) and keep the docs system consistent: CHANGELOG entry, affected CLI docs, a
reference page for the verdict vocabulary, and a regenerated docs retrieval index (an ADR was added).

## Context

- Canonical CHANGELOG: `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink). Use a
  `[Unreleased]` section, bold impact-first lead with the `(#3469)` ref, then before→after.
- CLI docs: `docs/api/cli-commands.md` (move-task flags, issue-verdict verdicts).
- Divio discipline: the new `docs/development/reference/issue-matrix-verdicts.md` is a **Reference**
  page — declare `type: reference` and an `updated: 2026-09-20` freshness date in frontmatter; add
  descriptive alt text to any diagram.
- After adding the ADR + new page, regenerate the retrieval index and run the freshness/terminology
  checks (charter §Docs; driver step 7).

## Subtasks

### T018 — CHANGELOG + CLI docs
Add a `[Unreleased]` CHANGELOG entry: impact-first (agents/operators no longer forced to write false
issue-matrix verdicts; move-task accepts natural flags), `(#3469)`, before→after. Update
`docs/api/cli-commands.md` for the new `move-task` `--actor`/`--reason` aliases, the corrected
`--assignee` semantics, and the `not-applicable` verdict on `issue-verdict`.

### T019 — Verdict reference page
Author `docs/development/reference/issue-matrix-verdicts.md` (Divio Reference): the five verdict
values, which gate at `approved` vs `done`, the classification model (implementation-target /
context-only / PR-ref), the default-gating fail-safe, and the evidence-token rule. Link the WP02 ADR.
Add it to `docs/development/reference/index.md`.

### T020 — Regenerate index + checks
Run `python scripts/docs/docs_index.py --write` (regenerates
`docs/development/3-2-docs-retrieval-index.yaml` + `3-2-page-inventory.yaml` to include the new ADR +
reference page), then `python scripts/docs/check_docs_freshness.py --ci` (errors=0) and
`pytest tests/architectural/test_no_legacy_terminology.py`. Fix any freshness/terminology failure.

## Branch Strategy

Planning base `fix/move-task-approval-ergonomics`; branches after the code WPs; merges back to the
same branch (then upstream `main` via PR). Worktree per computed lane from `lanes.json`.

## Test Strategy

`check_docs_freshness.py --ci` errors=0; `test_no_legacy_terminology.py` green. No product code here.

## Definition of Done

- CHANGELOG `[Unreleased]` entry (impact-first, `(#3469)`, before→after).
- CLI docs updated; Reference page authored + indexed with a freshness date.
- Retrieval index regenerated; freshness `--ci` errors=0; terminology guard green.
- Docs mirror shipped behavior (verified against merged code).

## Reviewer Guidance

Confirm docs match the actually-shipped behavior (not the spec). Confirm the CHANGELOG lead is
impact-first with the issue ref. Confirm the index was regenerated (diff shows the new ADR + page) and
freshness/terminology checks pass.
