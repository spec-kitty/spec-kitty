---
work_package_id: WP01
title: Resolver authority + red-first repro
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-005
planning_base_branch: claude/project-thread-5t7sqy
merge_target_branch: claude/project-thread-5t7sqy
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-5t7sqy. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-5t7sqy unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-state-read-dir-dedup-01M3HNNV
base_commit: 9e1f3e7d599ae3083bbdfcef4b863446379fb689
created_at: '2026-09-27T14:59:09.471819+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Authority
history:
- at: '2026-09-27T15:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/missions/
create_intent:
- tests/specify_cli/missions/test_partition_read_dir.py
- tests/agent/test_status_state_phantom_degrade.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/missions/_read_path_resolver.py
- tests/specify_cli/missions/test_partition_read_dir.py
- tests/agent/test_status_state_phantom_degrade.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Resolver authority + red-first repro

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- An issue-pinned `@pytest.mark.regression` test reproduces #5180 RED on the pre-fix code:
  under the #154 ambient-ancestor layout, `workflow_cores.latest_review_feedback_reference`
  returns `(None, None, None)` and `tasks_verdict_persistence._resolve_verdict_read_feature_dir`
  resolves a non-existent directory, although the handed mission dir holds the rejection.
- `specify_cli.missions._read_path_resolver.resolve_partition_read_dir(feature_dir, kind)`
  exists with the exact semantics of today's
  `post_merge/review_artifact_consistency.py::_resolve_partition_read_dir` (see plan.md).
- Unit tests cover: no workspace root → handed dir; phantom resolved + existing handed dir →
  handed dir; phantom resolved + missing handed dir → resolved path; materialised coord →
  coord dir; flat topology → primary dir; `CoordinationBranchDeleted` propagates.

## Context & Constraints

- Spec: FR-001, FR-003, FR-005, C-002, C-003. Plan: "The one resolver".
- Keep `from mission_runtime import resolve_artifact_surface` **lazy** inside the function
  (mission_runtime.resolution imports this module).
- Complexity ≤ 15; no suppressions; new public name needs non-test callers — WP02 adds them,
  so land WP01 + WP02 in one PR.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: claude/project-thread-5t7sqy
- **Merge target branch**: claude/project-thread-5t7sqy

## Subtasks

### T001 — Red-first repro
Create `tests/agent/test_status_state_phantom_degrade.py`, marked `regression` + `git_repo`,
modelled on `tests/review/test_artifacts.py::test_gate_reads_handed_mission_dir_when_anchor_is_a_foreign_repo`.
Commit it RED before T002 lands.

### T002 — Resolver
Add `resolve_partition_read_dir` to `_read_path_resolver.py`; docstring carries the #154/#5180
rationale once (the consumers' docstrings will point here).

### T003 — Unit tests
`tests/specify_cli/missions/test_partition_read_dir.py`; use `tests.integration.coord_topology_fixture`
for the materialised-coord leg.

## Definition of Done
- Repro committed RED first; resolver + unit tests green; ruff/format/mypy clean.

## Reviewer Guidance
- Verify the RED commit precedes the fix and fails for the stated reason.
