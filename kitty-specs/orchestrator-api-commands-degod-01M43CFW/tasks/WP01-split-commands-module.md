---
work_package_id: WP01
title: Split commands.py behind an unchanged contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: claude/funny-cannon-2kiwuz
merge_target_branch: claude/funny-cannon-2kiwuz
branch_strategy: Planning artifacts for this mission were generated on claude/funny-cannon-2kiwuz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/funny-cannon-2kiwuz unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Refactor
history:
- at: '2026-10-04T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/orchestrator_api/
create_intent:
- src/specify_cli/orchestrator_api/_common.py
- src/specify_cli/orchestrator_api/wp_lifecycle.py
- src/specify_cli/orchestrator_api/consolidation.py
- src/specify_cli/orchestrator_api/design_phase.py
- src/specify_cli/orchestrator_api/decision_verbs.py
- src/specify_cli/orchestrator_api/design_status.py
- tests/specify_cli/orchestrator_api/test_command_table.py
execution_mode: code_change
owned_files:
- src/specify_cli/orchestrator_api/**
- tests/**
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/missions/_read_path_resolver.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Split commands.py behind an unchanged contract

## Objective

Split `src/specify_cli/orchestrator_api/commands.py` (4,191 LOC) into `_common.py` plus five concern modules, per [plan.md](../plan.md). Leave `mission-state` and `list-ready` in the façade for #5532.

## Acceptance

- Help snapshot (group + 21 verbs) byte-identical before/after.
- AST of every moved definition equal to the original, modulo `_common.` seam qualification and added `dict[str, Any]` type arguments.
- ruff, ruff format, mypy clean on the new modules (no new ignore entries).
- Blast-radius suite at baseline count; `tests/architectural/` green.
