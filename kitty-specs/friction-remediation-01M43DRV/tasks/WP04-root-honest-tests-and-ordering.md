---
work_package_id: WP04
title: Root-honest permission tests and isolated TestOrdering (sequenced on PR 5656)
dependencies: []
requirement_refs:
- FR-009
planning_base_branch: issue-5552-friction-remediation
merge_target_branch: issue-5552-friction-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5552-friction-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5552-friction-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 2 - Sequenced
history:
- at: '2026-10-04T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/gitignore_manager.py
- tests/cross_cutting/test_gitignore_manager_unit.py
- tests/cross_cutting/encoding/test_encoding_validation_functional.py
- tests/missions/test_mission_v1_events_unit.py
- tests/specify_cli/readiness/test_upgrade_ux_migration.py
- tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5654'
- '#5186'
---
# Work Package Prompt: WP04 – Root-honest permission tests and isolated TestOrdering

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile and follow it, together with the test-suite-quality-assessment procedure.

## Gate (binding)

T014: run `git fetch origin main` and check whether PR #5656 is merged.
- If it is NOT merged: do not start. Cancel this WP with the rationale "deferred: waits on PR #5656 (eacces helpers, test_provision_kitty_env edits)", and leave #5654 and #5186 open (`Refs`).
- If it IS merged: merge origin/main into the branch first.

## Objective

- **T015**: Inject `PermissionError` at the seam in the encoding sanitize-write test, the mission-v1 events-open test and the upgrade-ux history-db-open test, using the `tests/_support/eacces.py` helpers. Prove each with a planted break.
- **T016**:
  - Planted break: remove `gitignore_manager.write_gitignore_text`'s mode check, show the three named sites go red as root, then revert.
  - Delete the caller-less `GitignoreManager._atomic_write` and fix the :468 test docstring.
- **T017**:
  - Add a class-scoped autouse fixture calling `auto_discover_migrations()` for `TestOrdering`. Keep the count==1 asserts.
  - File a follow-up issue listing the about 30 other root-skipped chmod tests.
