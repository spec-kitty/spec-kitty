---
work_package_id: WP01
title: Red-first reproduction and the ledger-shape regression suite
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-6547-upgrade-cutover-preserves-retired-commands
merge_target_branch: issue-6547-upgrade-cutover-preserves-retired-commands
branch_strategy: Planning artifacts for this mission were generated on issue-6547-upgrade-cutover-preserves-retired-commands. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6547-upgrade-cutover-preserves-retired-commands unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-cutover-preserves-retired-commands-01M68J8W
base_commit: c84c5dc24f04f4211c2c9e6cc72d20dbd4c9eb2c
created_at: '2026-10-31T08:50:54.059592+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Red
history:
- timestamp: '2026-10-31T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/upgrade/
create_intent:
- tests/specify_cli/upgrade/test_retired_command_writers_6547.py
execution_mode: code_change
owned_files:
- tests/specify_cli/upgrade/test_retired_command_writers_6547.py
tags: []
tracker_refs: []
---

# WP01 — Red-first reproduction and the ledger-shape regression suite

## Goal

Reproduce #6547 through `MigrationRunner.upgrade` (the production entry point) and pin the post-fix
contract for every ledger shape.

## Files

- `tests/specify_cli/upgrade/test_retired_command_writers_6547.py` (new)

## Steps

1. Build the post-cutover fixture: git repo, `.kittify/metadata.yaml` at `4.0.0rc7`, agent config
   `claude`, `.claude/commands/my-command.md`, and a tracked ledger that settles
   `4.0.0rc8_backfill_migration_ledger`, `3.1.2_globalize_commands`, `3.2.0a4_safe_globalize_commands`.
2. Assert the reproduction: `2.1.4_enforce_command_file_state` appears in `migrations_applied` and
   `.claude/commands/` gains 14 `spec-kitty.*` files. Run it; it must pass on current `HEAD` (that is
   the red proof), then stay in the file as a regression that flips when WP02 lands — invert it into
   the post-fix contract (see 3) once WP02 is applied; keep the pre-fix shape documented in the
   module docstring so the proof is not lost.
3. Post-fix contract: three consecutive upgrades leave exactly `my-command.md`; neither writer is
   applied; both ledger records carry a `superseded_by` note and never `success`.
4. Parametrise the ledger shapes: pre-ledger (version floor settles both writers), ledger-era fully
   settled, post-cutover without the floor — same final directory contents.
5. Legacy fixture: generated local command files carrying a version marker are still removed by the
   retire path; `spec-kitty.custom.md` without a marker is preserved (positive control).
6. `upgrade --dry-run` lists no write to a project-local command file.

## Constraints

- Do not call a writer's `apply()` directly; the defect is in selection and registration.
- `MigrationRegistry.clear()` + `auto_discover_migrations()` in an autouse fixture.
- No network, no second CLI build, no dependency on the machine's `~`.
