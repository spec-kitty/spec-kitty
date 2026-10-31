---
work_package_id: WP01
title: Commit seam refuses a directory request before mutation
dependencies: []
requirement_refs:
- FR-002
- NFR-002
- C-001
- C-002
- SC-003
planning_base_branch: issue-6750-lane-auto-commit-directory-expansion
merge_target_branch: issue-6750-lane-auto-commit-directory-expansion
branch_strategy: Planning artifacts for this mission were generated on issue-6750-lane-auto-commit-directory-expansion. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6750-lane-auto-commit-directory-expansion unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-auto-commit-directory-expansion-01M67HVC
base_commit: 35a56150ad67d9f66f9d1212a295beec6a7d726b
created_at: '2026-10-30T23:25:17.385267+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Commit seam invariant
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- tests/specify_cli/git/test_safe_commit_directory_argument_6750.py
execution_mode: code_change
owned_files:
- src/specify_cli/git/commit_helpers.py
- tests/specify_cli/git/test_safe_commit_directory_argument_6750.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6750'
---

# Work Package Prompt: WP01 – Commit seam refuses a directory request before mutation

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `lane-auto-commit-directory-expansion-01M67HVC`. Read `../spec.md`,
`../plan.md`, `../research.md` and the issue spec-kitty/spec-kitty#6750.

## Objectives & Success Criteria

`safe_commit`'s contract is "commit exactly these file paths". `preflight_commit`
already owns path normalization, the `.worktrees/` policy check and the protection
decision, but it never asks whether a requested path **is a directory**. Git happily
expands a directory pathspec, so the commit carries paths the caller never requested —
and the post-landing guard then reports a superset (see WP02 for the consequence).

This WP makes the invariant structural and total:

1. **A typed refusal.** Add `SafeCommitDirectoryArgument(SafeCommitError)` beside
   `SafeCommitPathPolicyError` in `src/specify_cli/git/commit_helpers.py`:
   - `error_code = "SAFE_COMMIT_DIRECTORY_ARGUMENT"`
   - constructor takes `offending_path: str` and `worktree_root: Path`; `to_dict()`
     adds `offending_path` (mirror `SafeCommitPathPolicyError`)
   - message names the path and states the rule truthfully, for example:
     `safe_commit: refusing directory path '<p>'. safe_commit commits exact file paths;
     expand a directory first (git status --untracked-files=all) and request the files.`
     Say "directory", never "staging area" or "hook".
2. **The check, in `preflight_commit`.** After the absolute→relative normalization loop
   produces `normalized_files` and **before** the `.worktrees/` policy check and the
   protection decision, refuse any requested path that is a directory on disk under
   `worktree_root`:
   - resolve as `worktree_root / normalized_path` (relative paths are already
     worktree-relative; an absolute path outside the worktree stays a file request and
     is not the collector's case);
   - skip it when the path does not exist (a deleted tracked file is a legitimate
     request), and when `is_symlink()` is true (a symlinked directory is a single
     `120000` entry, never a directory to expand — the same rule as
     `safe_commit_cmd._expand_arguments`);
   - raise on the first offending path. No index write, no ref update, no staging — the
     order in `preflight_commit` already guarantees that, so place the check above it
     rather than adding a second preflight pass.
3. **No caller-behaviour change.** The public `spec-kitty safe-commit` CLI expands
   directories in its own layer before calling `safe_commit`
   (`cli/commands/safe_commit_cmd.py::_expand_arguments`, #2739 B11) and is unaffected.
   Do not move or duplicate that expansion; do not add a second expansion helper.
4. **No contract churn.** `SafeCommitUnrequestedPaths`, `SafeCommitIndexResidue`,
   `SafeCommitRecoveryFailed` and their `error_code`s are untouched (C-002). The new
   refusal is a plain `SafeCommitError` (hence a `RuntimeError`), raised before
   mutation, so existing "flatten a plain error into not-committed" callers stay
   correct.

## Context

- `preflight_commit` validation order (numbered comments in the function) is the
  contract; insert the new step where the numbering makes it honest, and update the
  numbering/docstring.
- `safe_commit` calls `preflight_commit` for every path set (including
  `index_deletions`), so the refusal covers all callers without touching `safe_commit`
  itself. Verify that claim rather than assuming it — `index_deletions` paths are
  appended to the same `paths` tuple.
- The docstring of `_assert_committed_paths_requested` currently claims "every caller
  already expands directories to files before `safe_commit`". Keep that claim, but now
  it is enforced: name the enforcement in that docstring (one sentence, no rewrite).

## Tests (new file `tests/specify_cli/git/test_safe_commit_directory_argument_6750.py`)

Write T001 **first**, run it, watch it fail for the right reason (the directory commits
today), then implement.

- **T001 refusal, zero mutation (SC-003, NFR-002)**: build a real git fixture (init,
  user.name/email, `commit.gpgsign=false`, one commit, an untracked directory with two
  files). Record `HEAD`, `git for-each-ref`, and `git status --porcelain -uall`. Call
  `safe_commit(repo_root=..., worktree_root=..., target=CommitTarget(ref=<branch>),
  message=..., paths=(<the directory>,))`. Assert: `SafeCommitDirectoryArgument`
  raised; `error_code == "SAFE_COMMIT_DIRECTORY_ARGUMENT"`; the message names the
  directory and does **not** contain "pre-commit hook"; HEAD, refs and status are
  byte-identical; `git ls-files -- .` shows nothing from the directory.
- **T004 positive control on the same fixture (C-001, C-002)**: the same call with the
  two explicit child paths commits and the commit's path set is exactly those two. On
  the same fixture, `spec-kitty safe-commit` (or its `_expand_arguments` + `safe_commit`
  pair, as the existing CLI tests drive it) with the directory argument still lands the
  same two paths — proving the refusal did not break the public expansion.
- **T003 guard rails**: a **symlinked** directory path is not refused (it commits as a
  `120000` entry), and a **deleted tracked file** path is not refused.

Prefer `pytest.mark.integration` + `pytest.mark.git_repo` markers like the existing
`tests/specify_cli/git/` git-fixture tests. No mocking of git.

## Branch Strategy

- Planning branch / final merge target: `issue-6750-lane-auto-commit-directory-expansion`.
- Execution worktrees are allocated per computed lane from `lanes.json`; never build a
  workspace path or branch name by hand.

## Definition of Done

- T001's test fails before the change and passes after; the positive controls pass.
- `uv run pytest tests/specify_cli/git/test_safe_commit_directory_argument_6750.py -q`
  green; plus the existing safe-commit suites:
  `uv run pytest tests/specify_cli/git -q -k "safe_commit or commit_helpers"` and
  `uv run pytest tests/specify_cli/cli/commands/test_safe_commit_cmd.py -q` (adjust to the
  real paths you find; do not run the full suite).
- `uv run ruff check src/specify_cli/git/commit_helpers.py tests/specify_cli/git/` clean.
- No `# type: ignore`, no `--no-verify`, no weakened assertion.

## Risks

- Placing the check after the protection decision would still be pre-mutation, but it
  would report a protected-branch refusal for a request that is wrong for a different
  reason. Put it before.
- Do not turn this into a general "path must exist" rule: deleted-but-tracked files are
  legitimate, and `index_deletions` deliberately names files removed from the index.
