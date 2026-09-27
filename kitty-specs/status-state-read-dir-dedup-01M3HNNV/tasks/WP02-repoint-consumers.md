---
work_package_id: WP02
title: Repoint consumers + structural guard
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
planning_base_branch: claude/project-thread-5t7sqy
merge_target_branch: claude/project-thread-5t7sqy
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-5t7sqy. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-5t7sqy unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-state-read-dir-dedup-01M3HNNV
base_commit: 9e1f3e7d599ae3083bbdfcef4b863446379fb689
created_at: '2026-09-27T15:24:33.730159+00:00'
subtasks:
- T004
- T005
- T006
phase: Phase 2 - Consumers
history:
- at: '2026-09-27T15:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/architectural/test_status_state_read_dir_single_authority.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_cores.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- src/specify_cli/post_merge/review_artifact_consistency.py
- tests/architectural/test_status_state_read_dir_single_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Repoint consumers + structural guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `review_artifact_consistency._resolve_lane_state_read_dir`, `workflow_cores.latest_review_feedback_reference`,
  `workflow_cores.has_prior_rejection` and `tasks_verdict_persistence._resolve_verdict_read_feature_dir`
  all resolve STATUS_STATE through `resolve_partition_read_dir`.
- `_resolve_partition_read_dir` (post_merge) and `_resolve_status_state_read_dir` (workflow_cores) are deleted.
- WP01's repro is green; then converted to focused tests without the `regression` marker (ADR 2026-07-17-1 flow).
- A structural test with a poison arm fails if any of the three modules resolves STATUS_STATE through
  `resolve_artifact_surface` / `placement_seam(...).read_dir` directly.

## Context & Constraints

- C-001: the render path's artifact-pointer resolution (`review_feedback_root`,
  `resolve_review_feedback_pointer`, `_resolve_review_cycle_sub_artifact_dir`) stays on PRIMARY.
- `workflow_cores.py` is a trio file: `tests/architectural/test_trio_seam_only.py` allowlists which
  `_read_path_resolver` names it may import — add `resolve_partition_read_dir` with a rationale comment.
- Keep `_resolve_verdict_read_feature_dir` and `_resolve_lane_state_read_dir` as one-line
  adapters (tests import them).
- Update `tests/architectural/untrusted_path_audit/inventory.md` / characterization baselines only if
  their gates actually go red, and say why.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: claude/project-thread-5t7sqy
- **Merge target branch**: claude/project-thread-5t7sqy

## Subtasks

### T004 — Repoint
Swap the three bodies for delegation; shrink docstrings to a pointer at the authority.

### T005 — Guard
AST scan of the three module sources; poison arm feeds a synthetic source that re-introduces the copy.

### T006 — Convert repro
Drop `@pytest.mark.regression`; keep the tests as focused unit tests of the render/verdict reads.

## Definition of Done
- Targeted tests listed in tasks.md green; ruff/format/mypy clean; complexity ≤ 15.

## Reviewer Guidance
- Confirm the materialised-coord render tests in `tests/agent/test_workflow_review_cycle_pointer.py` still pass unchanged.
