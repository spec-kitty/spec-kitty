---
work_package_id: WP05
title: init commits what it wrote (#7555)
dependencies: []
requirement_refs:
- FR-007
- C-001
- C-002
planning_base_branch: fix/7545-cli-owns-its-commits
merge_target_branch: fix/7545-cli-owns-its-commits
branch_strategy: Planning artifacts for this mission were generated on fix/7545-cli-owns-its-commits. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7545-cli-owns-its-commits unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
phase: Phase 2 - Commits
history:
- at: '2026-11-11T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/init.py
create_intent:
- tests/init/test_init_commits_its_writes_7555.py
- docs/changelog/unreleased/7555-init-commits-its-writes.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/init.py
- src/specify_cli/upgrade/autocommit.py
- tests/init/test_init_in_existing_repo.py
- tests/init/test_init_commits_its_writes_7555.py
- docs/changelog/unreleased/7555-init-commits-its-writes.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – `init` commits what it wrote (#7555)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` (role `implementer`).

---

## Objectives & Success Criteria

- Inside a git repository, `init` ends with one commit
  (`chore: initialize spec-kitty project`) that holds exactly the paths it wrote. Paths that
  were dirty before `init` ran stay uncommitted (C-001). The tree is clean afterwards.
- `--no-commit` commits nothing.
- Outside a git repository nothing changes. `init` still never runs `git init` and the string
  `Initial commit from Specify template` stays absent.
- Closes #7555.

## Context & Constraints

- **Reversal of a governed decision, flagged for the operator.** Mission
  `079-post-555-release-hardening` FR-002 / FR-007 made `init` commit-free "under any flag
  combination". The dispatch for #7545 and issue #7555 ask for the opposite (commit by default,
  opt-out). This WP follows the dispatch. The PR must name the reversal so the operator can
  overrule it; the fallback is an opt-in `--commit` flag. Decision Moment
  `01M75NY6CET5GK3CZ4QEEBJXGC`.
- Reuse `upgrade/autocommit.py`: `capture_upgrade_baseline(repo)` before the first write and
  `commit_touched_checkout(repo, baseline, ...)` after the last. It already commits only the
  baseline diff, skips ignored paths, and holds the `UPGRADE_BOOKKEEPING` capability, so it
  works on a protected `main` without a new capability holder (`test_guard_capability_call_sites.py`).
  Add an optional keyword `message: str | None = None` so init's commit is not titled
  "apply spec-kitty upgrade changes".
- Unborn HEAD: a fresh `git init` with no commit has a branch name (`git branch
  --show-current`) but no HEAD commit. Verify `safe_commit` handles it; if it does not, fall
  back to a warning with the commit recipe (never `git commit` raw).
- Home-directory guard: `is_upgrade_commit_eligible` already refuses root files when the
  checkout is `$HOME`.

## Branch Strategy

- **Strategy**: single_branch, direct in the repository root checkout
- **Planning base branch**: fix/7545-cli-owns-its-commits
- **Merge target branch**: fix/7545-cli-owns-its-commits

## Subtasks & Detailed Guidance

### Subtask T016 – Red test

- `tests/init/test_init_commits_its_writes_7555.py`, using the `_make_app` / CliRunner pattern
  from `tests/init/test_init_in_existing_repo.py`:
  - a repository with one commit → `init --ai claude --non-interactive` → exactly one new
    commit, `git status --porcelain` empty, and the commit holds `.kittify/config.yaml`,
    `.gitignore`, `.gitattributes`;
  - a pre-existing dirty `notes.txt` and a modified tracked `.gitignore` stay out of the commit;
  - `--no-commit` → no new commit;
  - an unborn repository (no commits) → one commit.

### Subtask T017 – Baseline + commit

- In `init.py`, when `_is_inside_git_work_tree(project_path)`, capture the baseline before the
  first write and commit at the end, after the ledger seed and config saves. Print one line:
  `Committed spec-kitty project files (<n> files) on <branch>`, or the warning returned by
  `commit_touched_checkout`. Keep `init` ≤ 15 complexity by putting this in a helper.
- Rewrite the comment `T001: No git initialization. init is file-creation-only.` to say what is
  true now.

### Subtask T018 – `--no-commit`; re-pin

- Add `--no-commit` (typer option, help text "Do not commit the files init writes (inside a git
  repository)").
- `tests/init/test_init_in_existing_repo.py::test_init_does_not_touch_git_state_in_existing_repo`
  asserts no commit. Re-pin it to run with `--no-commit`, and keep its "no tracked file
  modified" assertion. The new behaviour is pinned in the T016 file.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/init -q
.venv/bin/python -m pytest tests/specify_cli/upgrade -q -k autocommit
.venv/bin/python -m pytest tests/architectural/test_guard_capability_call_sites.py tests/architectural/test_commit_scope_owner.py -q
```

## Risks & Mitigations

- A user's staged changes: `safe_commit` commits only the requested paths and preserves other
  staged content. Assert this in a test.

## Review Guidance

- The reversal is named in the PR; no new capability holder; red first.
