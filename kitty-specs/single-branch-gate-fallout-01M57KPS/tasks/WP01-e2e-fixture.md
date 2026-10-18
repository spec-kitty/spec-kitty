---
work_package_id: WP01
title: Complete the single_branch e2e fixture (#6370)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-001
planning_base_branch: issue-6370-single-branch-gate-fallout
merge_target_branch: issue-6370-single-branch-gate-fallout
branch_strategy: Planning artifacts for this mission were generated on issue-6370-single-branch-gate-fallout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6370-single-branch-gate-fallout unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
phase: Phase 1 - Fallout fixes
history:
- at: '2026-10-18T13:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/specify_cli/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/test_specify_topology_flag.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Complete the single_branch e2e fixture (#6370)

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (`packs/built-in/agent_profiles/implementer-ivan.agent.yaml`) and follow its guidance.

## Objectives & Success Criteria

`tests/specify_cli/test_specify_topology_flag.py::test_single_branch_mission_survives_implement_and_merge_end_to_end` passes under the unchanged #5939 gate (FR-001, FR-002, SC-001).

## Context & Constraints

- Red on main: `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` at claim time (`consolidation/reconciliation.py::_single_branch_evidence_refusal`), because `_finalize_single_branch_lanes` passes `planning_commit_sha=None`.
- After that is fixed: `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT`, because `_seed_wp_approved` records `seed` for both the implementing hops and the approval (`preflight._independent_reviewer_confirmed`).
- C-001: no product change. The sibling fixture fix `1803d146` (terminus) is the precedent.

## Subtasks & Detailed Guidance

### Subtask T001 – Record the planning commit

- Pass `planning_commit_sha=<repo HEAD>` to `compute_and_write_lanes`. This is the tip finalize-tasks captures (`mission_finalize_planning_pin._preserve_or_capture_planning_commit_sha`), and it precedes both WP code commits.

### Subtask T002 – Distinct seed actors

- Implementing hops (`claimed`, `in_progress`, `for_review`) use `implementer-ivan`. `in_review` and `approved` use `reviewer-renata`, which also names the reviewer in the evidence and the `ReviewResult`.

## Test Strategy

- `.venv/bin/python -m pytest tests/specify_cli/test_specify_topology_flag.py -q -p no:cacheprovider`
- `ruff check`, `ruff format --check --force-exclude` and `mypy` on the file.

## Risks & Mitigations

- Vacuity: confirm that each half alone still refuses (planning commit only → REVIEW_NOT_INDEPENDENT; observed during diagnosis).

## Review Guidance

- No `src/` change. Gate codes unchanged. Each half is needed.
