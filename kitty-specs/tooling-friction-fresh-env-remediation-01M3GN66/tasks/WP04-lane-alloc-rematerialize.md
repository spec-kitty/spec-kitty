---
work_package_id: "WP04"
title: "Lane-allocation derived-state regeneration (#5160 friction 1)"
task_type: "implement"
execution_mode: "code_change"
phase: "Phase 1 - Remediation"
dependencies:
  - "WP03"
owned_files:
  - "src/specify_cli/lanes/worktree_allocator.py"
  - "tests/lanes/test_worktree_allocator_rematerialize.py"
authoritative_surface: "src/specify_cli/lanes/worktree_allocator.py"
create_intent:
  - "tests/lanes/test_worktree_allocator_rematerialize.py"
subtasks:
  - "T009"
  - "T010"
  - "T011"
planning_base_branch: "claude/tooling-friction-investigation-gpb1yl"
merge_target_branch: "claude/tooling-friction-investigation-gpb1yl"
branch_strategy: "Planning artifacts were generated on claude/tooling-friction-investigation-gpb1yl; completed changes must merge back into claude/tooling-friction-investigation-gpb1yl."
agent_profile: ""
role: "implementer"
agent: "claude"
model: ""
assignee: ""
shell_pid: ""
history:
  - at: "2026-09-27T05:30:00Z"
    actor: "system"
    action: "Prompt generated for the tooling-friction remediation mission"
---

# Work Package Prompt: WP04 – Lane-allocation derived-state regeneration (#5160 friction 1)

## Objectives & Success Criteria

After the allocation merges, regenerate a conflicting derived status.json from the merged log (via the WP03 helper) instead of failing closed. Genuine human-authored conflicts (tasks/WP*.md) still block.

**Requirement Refs**: FR-003

## Context & Constraints

- Mission spec: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`
- Plan + concern map: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/plan.md`
- Manifest: `kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/tasks.md`
- Charter: `.kittify/charter/charter.md` (single canonical authority; canonical sources only; no test skip/disable to green).

## Branch Strategy

- **Planning base branch**: claude/tooling-friction-investigation-gpb1yl
- **Merge target branch**: claude/tooling-friction-investigation-gpb1yl

## Implementation Guidance

Edit `_merge_recorded_planning_commit` and `_merge_dependency_lane_tips`. Red-first with divergent status.json (currently raises PlanningCommitMergeConflictError/DependencyLaneMergeConflictError). Control test: a tasks/WP*.md conflict still fails closed; preserve the #4905 wp_task_conflicts diagnostic. Scope regeneration strictly to derived snapshots.

## Test Strategy

- Red-first regression proving the bug, then green after the fix (no-op passable: no).
- Run the owning module's tests plus blast radius; cross-cutting changes additionally run `tests/architectural/`.
- Lint/type: `ruff check .`, `ruff format --check .`, and mypy on changed files — zero issues.

## Risks & Mitigations

- Honor the constraints in spec.md (C-001..C-004). Keep new/edited functions <=15 complexity (NFR-004).

## Activity Log

- 2026-09-27T05:30:00Z – system – Prompt created.
