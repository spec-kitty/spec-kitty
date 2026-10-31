---
work_package_id: WP02
title: Declare both pre-globalize writers superseded
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-006
planning_base_branch: issue-6547-upgrade-cutover-preserves-retired-commands
merge_target_branch: issue-6547-upgrade-cutover-preserves-retired-commands
branch_strategy: Planning artifacts for this mission were generated on issue-6547-upgrade-cutover-preserves-retired-commands. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6547-upgrade-cutover-preserves-retired-commands unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-cutover-preserves-retired-commands-01M68J8W
base_commit: c84c5dc24f04f4211c2c9e6cc72d20dbd4c9eb2c
created_at: '2026-10-31T09:09:12.992308+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Fix
history:
- timestamp: '2026-10-31T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/supersession.py
- tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py
tags: []
tracker_refs: []
---

# WP02 — Declare both pre-globalize writers superseded

## Goal

Make `2.1.4_enforce_command_file_state` and `3.0.2_restore_prompt_commands` recorded no-ops through
the one supersession table, with successor `3.2.0a4_safe_globalize_commands`.

## Files

- `src/specify_cli/upgrade/supersession.py` (edit: two entries + comment)
- `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` (edit: enumeration)

## Steps

1. Add both entries to `SUPERSEDED_MIGRATIONS`, with a comment naming #6547 and the reason: the
   retire migration removes exactly what the writer writes, and after 3.1.2 the missing state is the
   correct state.
2. Add the two shipped classes to the `SHIPPED_SUPERSEDED` enumeration in the `#6589` invariant test
   (an extension of the coverage assertion, never a relaxation).
3. Verify: shipped modules byte-identical to `origin/main`; substitute `content_hash` equals the
   shipped class's; manifest order holds; direct import still yields the shipped class.
4. Run WP01's module: it flips green.

## Constraints

- No change to `get_applicable`, the runner, the backfill or the adoption baseline.
- No shipped migration module is edited (DIRECTIVE_044).
