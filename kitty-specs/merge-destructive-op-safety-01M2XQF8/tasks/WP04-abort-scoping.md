---
work_package_id: WP04
title: Scope `merge --abort` to spec-kitty merge state (#4754)
dependencies: []
requirement_refs:
- FR-005
- FR-006
- NFR-002
- NFR-004
planning_base_branch: fix/merge-destructive-op-safety
merge_target_branch: fix/merge-destructive-op-safety
branch_strategy: Planning artifacts for this mission were generated on fix/merge-destructive-op-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/merge-destructive-op-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-destructive-op-safety-01M2XQF8
base_commit: d8288b6a09b0a07dca1a4265803519bca3621d91
created_at: '2026-09-19T21:59:31.922844+00:00'
subtasks:
- T015
- T016
- T017
phase: Phase 1 - Implementation
history:
- at: '2026-09-19T21:10:00Z'
  actor: system
  action: Prompt generated for merge-destructive-op-safety mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/integration/test_merge_abort_scope.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/state.py
- src/specify_cli/cli/commands/merge.py
- tests/integration/test_merge_abort_scope.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4754'
---

# Work Package Prompt: WP04 – Scope `merge --abort` to spec-kitty state

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
before anything else. Then read `spec.md` (US3), `plan.md`, and `quickstart.md`.

## Objective

Stop `spec-kitty merge --abort` from aborting the operator's OWN in-progress git
merge. It must only run `git merge --abort` when active spec-kitty merge state
exists, and only within spec-kitty-owned scope — never against the bare
`repo_root`. Fix the contradictory "No active merge state to abort." followed by
"Aborted in-progress git merge." (#4754).

## Context (grounding — file:line, current main)

- `src/specify_cli/merge/state.py` `abort_git_merge(repo_root)` (`:455`) — runs
  `git merge --abort` in `repo_root` gated only by `detect_git_merge_state`
  (MERGE_HEAD presence, `:444`), NOT by any spec-kitty merge state.
- `src/specify_cli/cli/commands/merge.py` `_dispatch_abort` (`:373`) — calls
  `abort_git_merge(repo_root)` at `:420`, UNGATED, even after the `else` branch
  printed "No active merge state to abort." (`:404`).
- The merge pipeline runs `git merge` ONLY in detached temp worktrees
  (`lanes/merge.py`, `cwd=tmp_path`) — so a `MERGE_HEAD` in `repo_root` is ALWAYS
  the user's own. There is no legitimate reason to abort it.

## Subtasks

### T015 — Gate + scope `abort_git_merge`
Condition the git-merge abort on active spec-kitty merge state existing, and scope
it to the spec-kitty merge workspace (`get_merge_workspace_path(...)`), never
`repo_root`. Preferred per the issue's suggested fix: remove the
`abort_git_merge(repo_root)` call from the no-state path entirely, or gate it on
active state + workspace scope. Preserve the state-clearing behavior (runtime dir,
lock, workspace) when active spec-kitty state DOES exist.

### T016 — Fix `_dispatch_abort` messaging
Ensure the command never prints "Aborted in-progress git merge." after "No active
merge state to abort." — the success line must reflect what actually happened
(FR-006). Internally consistent output for both the active-state and no-state
paths.

### T017 — Red-first #4754 (`tests/integration/test_merge_abort_scope.py`)
Create a repo with a genuine in-progress user merge (`MERGE_HEAD` in `repo_root`)
and NO spec-kitty merge state; run the `_dispatch_abort` path. Assert RED pre-fix
(user's `MERGE_HEAD`/resolution destroyed) and GREEN post-fix (preserved; no abort
on `repo_root`; consistent messaging). Add an active-state parity case asserting
the normal abort still clears spec-kitty state. `@pytest.mark.regression`,
reference #4754.

## Branch Strategy

Planning base: `fix/merge-destructive-op-safety`. Final merge target: `main`.
Enter the lane workspace `spec-kitty implement WP04` prepares. This WP has no
dependencies and can run in parallel with WP01/WP02/WP03.

## Test Strategy (ATDD)

Commit T017 FIRST (red — bare abort destroys the user's merge), then implement
T015–T016 to green. Targeted:
`.venv/bin/python -m pytest tests/integration/test_merge_abort_scope.py tests/merge/ -q`.

## Definition of Done

- `git merge --abort` runs only with active spec-kitty merge state, scoped to the
  merge workspace, never `repo_root`.
- The user's own in-progress merge is preserved (red-first repro green).
- Active-state abort still clears spec-kitty state (parity, NFR-002).
- Messaging is internally consistent (FR-006).
- `ruff`/`mypy` clean; complexity ≤15; no suppressions.

## Risks

- **Regressing the legitimate abort** — the active-state parity case guards it.
- **Scope creep** — this WP owns only `merge/state.py` + `cli/commands/merge.py`;
  do not touch the executor/preflight (WP03's surface).

## Reviewer Guidance

Verify: no `git merge --abort` on `repo_root` without active spec-kitty state;
messaging consistency; the parity case proves the normal abort path is intact.
