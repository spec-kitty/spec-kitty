---
work_package_id: WP03
title: Changelog fragment and docs closeout
dependencies:
- WP01
- WP02
requirement_refs:
- C-003
planning_base_branch: issue-6954-upgrade-empty-home-command-migrations
merge_target_branch: issue-6954-upgrade-empty-home-command-migrations
branch_strategy: Planning artifacts for this mission were generated on issue-6954-upgrade-empty-home-command-migrations. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6954-upgrade-empty-home-command-migrations unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
phase: Phase 3 - Closeout
history:
- at: '2026-11-02T17:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/unreleased/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/unreleased/*.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Changelog fragment and docs closeout

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` from the frontmatter before parsing the rest of this prompt.

## Objectives & Success Criteria

A per-PR changelog fragment under `docs/changelog/unreleased/` in the shape that
`check_changelog_style` accepts, describing the user-visible behaviour change of #6954 and
the trade-off it accepts. No `[Unreleased]` entry is added to
`docs/changelog/CHANGELOG.md` (since #6988 the changelog is assembled from fragments).

## Context & Constraints

- Read `docs/changelog/unreleased/README.md` first; the required shape and the accepted
  file names (`.fixed.md` for user-facing fixes) are defined there, not here.
- The filename uses the **PR** number, so this WP runs after the draft PR exists.
- The fragment must say what changes for an operator, before/after, and what to do
  (nothing), within the length the style gate allows.
- Name the accepted trade-off: on a machine that has never had the global command tree, a
  stamped project's generated project-local command files are now removed by the migration
  anyway; the CLI installs the global copies at the next spec-kitty command.

## Files

- Create: `docs/changelog/unreleased/<pr>.fixed.md`
- Read: `docs/changelog/unreleased/README.md`, `docs/changelog/CHANGELOG.md` (read only)

## Subtasks

- **T012** Write the fragment.
- **T013** Run the changelog style gate and
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`); confirm
  `git diff --stat docs/changelog/CHANGELOG.md` is empty.

## Definition of Done

- The changelog style check passes on the fragment.
- `docs/changelog/CHANGELOG.md` is untouched.
- `check_docs_freshness --ci` reports `errors=0`.
