---
work_package_id: WP03
title: Changelog and upgrade reference
dependencies:
- WP02
requirement_refs:
- FR-007
planning_base_branch: issue-6547-upgrade-cutover-preserves-retired-commands
merge_target_branch: issue-6547-upgrade-cutover-preserves-retired-commands
branch_strategy: Planning artifacts for this mission were generated on issue-6547-upgrade-cutover-preserves-retired-commands. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6547-upgrade-cutover-preserves-retired-commands unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-cutover-preserves-retired-commands-01M68J8W
base_commit: c84c5dc24f04f4211c2c9e6cc72d20dbd4c9eb2c
created_at: '2026-10-31T09:47:33.558703+00:00'
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Docs
history:
- timestamp: '2026-10-31T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
- docs/api/upgrade-lifecycle.md
tags: []
tracker_refs: []
---

# WP03 — Changelog and upgrade reference

## Goal

Tell a project owner that an upgrade no longer reintroduces project-local command files, and that no
local action is needed.

## Files

- `docs/changelog/CHANGELOG.md` (edit, `[Unreleased]`)
- the upgrade reference page that documents global command installation (edit)

## Steps

1. `[Unreleased]` entry: bold impact-first lead with `(#6547)`, then before and after, under 1,200
   characters.
2. One paragraph where the upgrade docs describe command installation: commands are global since
   3.1.2; the pre-globalize writers are superseded so an adopted ledger cannot reintroduce them.
3. `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0) if an index surface changed.

## Constraints

- Edit `docs/changelog/CHANGELOG.md`; the root `CHANGELOG.md` is a symlink.
- Regenerate only the docs surface the diff changes (shared CLI cache is not race-safe).
