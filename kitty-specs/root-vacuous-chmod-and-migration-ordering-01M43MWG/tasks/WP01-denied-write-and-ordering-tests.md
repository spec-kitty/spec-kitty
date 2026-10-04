---
work_package_id: WP01
title: Make the denied-write and ordering tests bite
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- SC-001
- SC-002
- SC-003
planning_base_branch: claude/happy-rubin-aq1qc6
merge_target_branch: claude/happy-rubin-aq1qc6
branch_strategy: Planning artifacts for this mission were generated on claude/happy-rubin-aq1qc6. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-rubin-aq1qc6 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/gitignore_manager.py
- tests/cross_cutting/test_gitignore_manager_unit.py
- tests/specify_cli/readiness/test_upgrade_ux_migration.py
- tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py
tags: []
tracker_refs:
- '#5654'
- '#5186'
---
# WP01 — Make the denied-write and ordering tests bite

See plan.md design decisions 1–3. Run as root. Every planted break is reverted and never committed (C-002).

## Validation

- `tests/cross_cutting/test_gitignore_manager_unit.py`
- `tests/init/test_init_flow_integration.py`
- `tests/cross_cutting/encoding/test_encoding_validation_functional.py`
- `tests/missions/test_mission_v1_events_unit.py`
- `tests/specify_cli/readiness/test_upgrade_ux_migration.py`
- `tests/specify_cli/upgrade/migrations/`
- `make test-fast`
