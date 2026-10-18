---
work_package_id: WP01
title: Op commit policy and operator-facing reporting
dependencies: []
requirement_refs:
- FR-001
- FR-006
- NFR-001
- NFR-002
- C-001
- C-002
- FR-002
- FR-003
- FR-004
- FR-005
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6410-op-record-commit-target
merge_target_branch: issue-6410-op-record-commit-target
branch_strategy: Planning artifacts for this mission were generated on issue-6410-op-record-commit-target. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6410-op-record-commit-target unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-10-18T17:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/invocation/
create_intent:
- src/specify_cli/invocation/op_commit_policy.py
- tests/specify_cli/invocation/test_op_commit_policy.py
execution_mode: code_change
owned_files:
- src/specify_cli/invocation/op_commit_policy.py
- src/specify_cli/invocation/executor.py
- src/specify_cli/cli/commands/profile_invocation.py
- src/specify_cli/doctor/ops.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/state/contract.py
- tests/specify_cli/invocation/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Op commit policy and operator-facing reporting

Load the `python-pedro` profile (`packs/built-in/agent_profiles/python-pedro.agent.yaml`) first.

## Objectives & Success Criteria

- Closing an Op adds no commit when `kitty-ops/` is gitignored for the path being committed. It also adds none when the primary branch, resolved without feature-branch bias, tracks no ULID-shaped Op record (SC-001).
- Repositories that do track Op records commit exactly as before (SC-002).
- No operator output advises `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` (SC-003).

## Context & Constraints

See `spec.md` (Edge Cases) and `plan.md` (Design).

- Do NOT use `core.git_ops.resolve_primary_branch`. Its `bias=False` path falls back to the current branch.
- Reuse the Op-record regex from `coordination/coherence.py` and pin that the two agree in a test.
- Keep the `_commit_op_record` qualname (pinned by `tests/architectural/test_no_worktree_name_guess.py`).
- Do not change the `complete --json` payload shape. Keep complexity ≤15.

## Subtasks

- **T001.** Red-first repro first (`@pytest.mark.regression`, cites #6410), RED on the base. Convert it once green.
- **T002.** Add the policy module: `resolve_primary_refs`, `primary_tracks_op_records`, `is_path_ignored` and `op_commit_skip_reason`.
- **T003.** Wire it into the executor with a cache. Add `OpCommitOutcome.skipped`.
- **T004.** Rendering in `profile_invocation.py` and `doctor.py`, the `doctor/ops.py` value, and the `contract.py` note.
- **T005.** Unit tests and fixture rework, keeping the original commit assertions as the positive control.

## Test commands

- `pytest tests/specify_cli/invocation -q`
- `pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_archive_root_byte_identical.py -q`
- `make test-fast`
- `ruff check`, `ruff format --check --force-exclude` and `mypy` on the touched files
