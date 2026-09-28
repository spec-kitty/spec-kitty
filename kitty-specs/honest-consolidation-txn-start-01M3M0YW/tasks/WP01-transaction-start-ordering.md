---
work_package_id: WP01
title: '#5111 transaction-start ordering'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: issue-5111-honest-consolidation-txn-start
merge_target_branch: issue-5111-honest-consolidation-txn-start
branch_strategy: Planning artifacts for this mission were generated on issue-5111-honest-consolidation-txn-start. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5111-honest-consolidation-txn-start unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-honest-consolidation-txn-start-01M3M0YW
base_commit: 337213d98a651ad0aeae9da6af01eb0febe6d673
created_at: '2026-09-28T13:04:18.836731+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Product fixes
history:
- at: '2026-09-28T13:02:22Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_issue_5111_fresh_gate_failure_rerun.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/state.py
- src/specify_cli/consolidation/resolve.py
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/test_issue_5111_fresh_gate_failure_rerun.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – #5111 transaction-start ordering

Load the `python-pedro` profile first.

**Objective**: FR-001–FR-003. A fresh transaction's `state.json` is never on disk without the `reconciliation.post-fix` marker, and `clear_state(repo, mission_id)` removes the marker with the state.

**Red-first evidence**: `tests/consolidation/test_issue_5111_fresh_gate_failure_rerun.py` fails on `af847be7`. The re-run is refused with "pre-fix in-flight merge state".

**Steps**: T001–T004 in `tasks.md`. Keep FR-012 intact: never stamp a *loaded* or *legacy-migrated* state.
