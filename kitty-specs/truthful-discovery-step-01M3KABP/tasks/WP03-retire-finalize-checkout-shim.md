---
work_package_id: WP03
title: Retire the finalize checkout shim
dependencies: []
requirement_refs:
- FR-009
- FR-010
- FR-011
planning_base_branch: claude/project-thread-silj7c
merge_target_branch: claude/project-thread-silj7c
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-silj7c. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-silj7c unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-truthful-discovery-step-01M3KABP
base_commit: f338859f0a6e1cd2647979a2cd6d29efb3fa9206
created_at: '2026-09-28T06:29:13.601834+00:00'
subtasks:
- T011
- T012
- T013
phase: Phase 1 - Implementation
history:
- at: '2026-09-28T06:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission.py
- tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py
- tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py
- tests/specify_cli/cli/commands/review/test_issue_matrix_finalize_lint.py
- tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py
- tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Retire the finalize checkout shim

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `git grep _ensure_branch_checked_out -- src tests` returns nothing (SC-004); no runtime behaviour change (C-005).
- `test_finalize_tasks_validate_only_readonly.py` runs `finalize-tasks --validate-only` with HEAD on a branch that differs from the mission's target branch (the #1861 shape) and asserts HEAD, working tree and index unchanged.
- The dead `patch("specify_cli.status.fire_dossier_sync")` in `test_coord_topology_no_strand.py:103` is gone; the public compat shim in `specify_cli/status/__init__.py` stays (C-004).

## Context & Constraints

- Shim: `src/specify_cli/cli/commands/agent/mission.py:352-354`, zero callers; left by coordination-topology-stabilization WP09 when the real helper was replaced by `advance_branch_ref`. Checkout positioning now goes through `commit_for_mission`, which the patched tests already patch.
- `patch()`/patch dicts raise `AttributeError` on a missing attribute: delete the shim and the three patch lines in ONE commit.

## Subtasks & Detailed Guidance

### Subtask T011 – Delete the shim and its patches
- Remove the function. Remove the patch entries at `tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py:121`, `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py:129`, `tests/specify_cli/cli/commands/review/test_issue_matrix_finalize_lint.py:132`. Red-first here means: first show (Activity Log) that deleting only the shim makes those three tests error, then drop the patches in the same commit.

### Subtask T012 – Honest divergent-branch fixture
- The fixture `_scaffold_coord_mission_on_divergent_branch` (~:110-145) sets `target_branch = _PLANNING_BRANCH` and checks that branch out, so HEAD equals the target. Rebuild it so HEAD is on a different branch from `target_branch` while the mission stays resolvable, then assert `symbolic-ref HEAD`, `status --porcelain` and the staged diff are byte-identical before/after. Non-vacuity: add a same-fixture positive control proving the probe sees a HEAD change (e.g. `git checkout <target>` in the test changes the observed HEAD). Reword the docstring at :19 without the retired helper's name; drop the orphan sync-era comment at ~:175-178.

### Subtask T013 – Dead dossier-sync patch
- Remove `patch("specify_cli.status.fire_dossier_sync")` at `test_coord_topology_no_strand.py:103`; keep the test green.

## Test Strategy

```
pytest tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py tests/specify_cli/cli/commands/review/test_issue_matrix_finalize_lint.py tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py tests/status/test_dossier_sync_compat.py -q
pytest tests/specify_cli/cli/commands/agent/ -q
make test-fast
ruff check src tests && ruff format --check src tests && mypy src/specify_cli/cli/commands/agent/mission.py
```

## Risks & Mitigations

- A divergent-branch fixture that makes finalize fail to resolve the mission would turn the test into a vacuous failure path; assert the command's success exit as well.

## Review Guidance

- Confirm no production diff beyond the deleted function; confirm the read-only test fails if validate-only is made to check out the target branch.

## Post-tasks squad folds (binding)

- Guard against a vacuous read-only test: also assert `--validate-only` exits 0 with the target branch different from HEAD (e.g. target `main`, HEAD on the planning branch), alongside the unchanged-HEAD/tree/index assertions and the same-fixture positive control.

## Branch Strategy

- Planning base branch and merge target: `claude/project-thread-silj7c` (the PR head branch; the PR targets `main`).
- Execution worktrees are allocated per computed lane from `lanes.json`. Use `spec-kitty implement WP03` and work only in the resolved workspace.

## Standing rules

- Charter first: read `.kittify/charter/charter.md`; load `spec-kitty charter context --action implement`.
- Red-first (ADR 2026-07-17-1): the issue-pinned `@pytest.mark.regression` test is committed RED before the fix (show the failing run in the Activity Log), then converted to a focused unit/integration test (no `regression` marker left) once green.
- New code: ruff, `ruff format --check`, mypy clean; no new suppressions; complexity ≤ 15; every new branch tested in the same commit.
- Never edit generated agent copies (`.claude/`, `.agents/`, ...). Never bump the version. Never push to `main`.
- Record exact test commands and pass/fail counts in the Activity Log.

## Activity Log

- 2026-09-28T06:40:00Z – system – Prompt created.
