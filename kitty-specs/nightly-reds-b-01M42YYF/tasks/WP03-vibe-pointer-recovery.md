---
work_package_id: WP03
title: Vibe pointer recovery in agent config sync
dependencies: []
requirement_refs:
- FR-005
- NFR-002
planning_base_branch: kitty/nightly-reds-b-2026-10-04
merge_target_branch: kitty/nightly-reds-b-2026-10-04
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-b-2026-10-04. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-b-2026-10-04 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-b-01M42YYF
base_commit: 1b0046328e450dea7aa0516bdb10113e134574a8
created_at: '2026-10-04T08:09:06.469331+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 1 - Nightly red repair
history:
- at: '2026-10-04T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/config.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/config.py
- tests/specify_cli/cli/commands/test_agent_config.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Vibe pointer recovery in `agent config sync`

## Objectives & Success Criteria

- `tests/init/test_init_idempotent.py::test_initialized_clone_vibe_pointer_recovery_and_repeat` passes (red on base: `.vibe/config.toml` is not recreated).
- `tests/specify_cli/cli/commands/test_agent_config.py` still passes (manifest-pinning behavior from `f4a2e63ed` unchanged).
- Requirement refs: FR-005, NFR-002.

## Context & Constraints

- `init` recommends `spec-kitty agent config sync --create-missing --keep-orphaned` to recover a missing vibe skill-path pointer. Since `f4a2e63ed` ("stop a normal sync rewriting pinned manifests"), `_check_or_create_configured_agent_dirs` in `src/specify_cli/cli/commands/agent/config.py` hits `continue` for a skill agent that `_skill_agent_already_installed`, so `_register_skill_agent` (the only writer of the pointer) never runs.
- The pointer `.vibe/config.toml` is gitignored and is not part of the command-skill manifest, so restoring it does not conflict with the manifest-pinning contract.
- Red-first: the failing test already exists on the base; it is the red-first test. Record its red run on the planning base before your fix commit.

## Subtasks & Detailed Guidance

### Subtask T007 – Red evidence

- Run the init node id on the planning base and record the failure.

### Subtask T008 – Restore the pointer

- In the already-installed branch, for `agent_key == "vibe"`, restore the pointer when it is not configured, through the existing helpers in `specify_cli.skills.vibe_config` (`skill_path_configured`, `ensure_project_skill_path` — read that module first and use its real API), print a one-line confirmation, and mark `changes_made` so the command reports a change. A repeat run must report no change.
- Keep the change small (a helper function); stay at complexity ≤ 15.

### Subtask T009 – Tests

- Add one focused unit test in `tests/specify_cli/cli/commands/test_agent_config.py` that covers the new branch: installed vibe agent, pointer missing → restored, manifest bytes unchanged; pointer present → no change.
- Run the init node id, the whole `tests/specify_cli/cli/commands/test_agent_config.py`, and `tests/init/test_init_idempotent.py`. Run `mypy` on `config.py` the way the repo's CI does if available (`uv run --frozen mypy src/specify_cli/cli/commands/agent/config.py`).

## Review Guidance

- The manifest is never rewritten; only the gitignored pointer is.

## Branch Strategy

- **Strategy**: lanes_with_coord
- **Planning base branch**: kitty/nightly-reds-b-2026-10-04
- **Merge target branch**: kitty/nightly-reds-b-2026-10-04

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Binding rules for this WP

- Commits: author AND committer are `Stijn Dejongh <stijn.dejongh@sddevelopment.be>`; set `git config user.name "Stijn Dejongh"` and `git config user.email "stijn.dejongh@sddevelopment.be"` in the lane worktree before committing. End every commit message you write with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests foreground by named node id or file only: `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" <ids>`. Never a directory, never `make test-full`.
- No retries, skips, xfails, deselections, timeout or budget changes; keep every assertion except the stale literal named below.
- Do not touch any file outside `owned_files`.
- `ruff check` and `uv run --frozen ruff format --check --force-exclude` on every touched Python file.

## Activity Log

- 2026-10-04T08:10:00Z – system – Prompt created.
