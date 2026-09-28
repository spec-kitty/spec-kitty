---
work_package_id: WP02
title: '#5110 dry-run fail-closed'
dependencies: []
requirement_refs:
- FR-004
planning_base_branch: issue-5111-honest-consolidation-txn-start
merge_target_branch: issue-5111-honest-consolidation-txn-start
branch_strategy: Planning artifacts for this mission were generated on issue-5111-honest-consolidation-txn-start. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5111-honest-consolidation-txn-start unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-honest-consolidation-txn-start-01M3M0YW
base_commit: 337213d98a651ad0aeae9da6af01eb0febe6d673
created_at: '2026-09-28T13:10:52.373614+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 1 - Product fixes
history:
- at: '2026-09-28T13:02:22Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/forecast.py
create_intent:
- tests/consolidation/test_issue_5110_dry_run_unmaterialized_coord.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/forecast.py
- tests/consolidation/test_issue_5110_dry_run_unmaterialized_coord.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – #5110 dry-run fail-closed

Load the `python-pedro` profile first.

**Objective**: FR-004. Mirror the real path's handling of `CoordinationWorktreeUnmaterialized` and `CoordinationBranchDeleted` (`executor.py`, STATUS_STATE read) in `run_dry_run_forecast`. Exit 1, render the exception's own remediation, and keep `--json` valid with a stable `error_code`.

**Red-first evidence**: `tests/consolidation/test_issue_5110_dry_run_unmaterialized_coord.py` fails on `af847be7` with a raw `CoordinationWorktreeUnmaterialized`.
