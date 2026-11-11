---
work_package_id: WP04
title: setup-plan and mark-status commit their writes (#3933)
dependencies: []
requirement_refs:
- FR-005
- FR-006
planning_base_branch: fix/7545-cli-owns-its-commits
merge_target_branch: fix/7545-cli-owns-its-commits
branch_strategy: Planning artifacts for this mission were generated on fix/7545-cli-owns-its-commits. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7545-cli-owns-its-commits unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 2 - Commits
history:
- at: '2026-11-11T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/mission_setup_plan.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py
- tests/specify_cli/cli/commands/agent/test_mark_status_commits_coordination_3933.py
- docs/changelog/unreleased/3933-setup-plan-mark-status-commit-their-writes.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py
- tests/specify_cli/cli/commands/agent/test_mark_status_commits_coordination_3933.py
- docs/changelog/unreleased/3933-setup-plan-mark-status-commit-their-writes.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – setup-plan and mark-status commit their writes (#3933)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` (role `implementer`).

---

## Objectives & Success Criteria

- `setup-plan` on a substantive plan commits `plan.md` and this Mission's lifecycle log
  (`status.events.jsonl`, carrying SpecifyCompleted, PlanStarted and PlanCompleted) in one
  commit. The JSON `commit_hash` names that commit, and `git status` is clean afterwards (FR-005).
- `mark-status` commits its subtask annotation under auto-commit on every topology, not only on
  single_branch (FR-006). On a coordination Mission the coordination worktree is clean afterwards.
- `move-task` was observed clean on both topologies (`research.md`), so it needs no change.
  The red tests here are the regression guard for the half of #3933 that still reproduced.
- Closes #3933 together with the observations in `research.md`.

## Context & Constraints

- `_commit_plan_if_substantive` (`mission_setup_plan.py:789`) commits `plan_file` alone through
  `_mission._commit_to_branch`, then emits PlanCompleted. `_emit_spec_plan_phase_events`
  (`:743`) appends SpecifyCompleted and PlanStarted earlier in the same command.
- `_commit_to_branch(file_path, ...)` wraps `commit_for_mission(files=(file_path,), kind=...)`.
  Extend it with an optional `extra_files: tuple[Path, ...] = ()`, keeping the patch seam
  `mission._commit_to_branch` working; do not add a second commit path.
- `status.events.jsonl` is a STATUS_STATE kind. For single_branch and lanes it is PRIMARY. On
  a coordination topology the lifecycle events are still appended to the PRIMARY copy
  (#3933 comment), and the router partitions by kind. Test both topologies, and if the
  coordination case routes the primary events file wrongly, restrict `extra_files` to
  missions whose STATUS_STATE resolves PRIMARY and record the residual.
- `mark-status`: `commit_annotation = st.resolved_auto_commit and is_single_branch(...)`
  (`tasks_mark_status.py:609`, #5655). Drop the topology condition, so the selector
  `emit_runtime_annotation` decides, exactly as `move-task --note` does.

## Branch Strategy

- **Strategy**: single_branch, direct in the repository root checkout
- **Planning base branch**: fix/7545-cli-owns-its-commits
- **Merge target branch**: fix/7545-cli-owns-its-commits

## Subtasks & Detailed Guidance

### Subtask T012 – Red test: setup-plan

- `tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py`: a real
  single_branch Mission on an unprotected branch, a committed substantive spec, and a
  substantive `plan.md`. Run `setup-plan --json`. Assert `git status --porcelain` is empty,
  the JSON `commit_hash` equals `git rev-parse HEAD`, and that commit contains both `plan.md`
  and `status.events.jsonl`. Reuse fixtures from
  `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py` where they fit.

### Subtask T013 – Commit plan + lifecycle log together

- Move the PlanCompleted emission before the commit, then call `_commit_to_branch(plan_file,
  ..., extra_files=(events_file,))` when the events file exists and is dirty.

### Subtask T014 – Red test: mark-status on a coordination Mission

- `tests/specify_cli/cli/commands/agent/test_mark_status_commits_coordination_3933.py`: a
  coordination Mission (finalize, record-analysis, implement WP01), then `mark-status T001
  --status done`. Assert the coordination worktree is clean. Add a control: with
  `--no-auto-commit` the pair stays modified.

### Subtask T015 – Commit on every topology

- Drop the `is_single_branch` condition; update the comment (#5655 → #3933). If
  `--no-auto-commit` exists on mark-status, it keeps its meaning.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_setup_plan_commits_lifecycle_3933.py tests/specify_cli/cli/commands/agent/test_mark_status_commits_coordination_3933.py tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py tests/specify_cli/cli/commands/agent/test_setup_plan_read_surface.py tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent -q -k "mark_status or setup_plan"
```

## Risks & Mitigations

- The coordination topology's primary lifecycle log: covered by the topology note above.

## Review Guidance

- One commit for one phase transition; red tests first; the `--no-auto-commit` control.
