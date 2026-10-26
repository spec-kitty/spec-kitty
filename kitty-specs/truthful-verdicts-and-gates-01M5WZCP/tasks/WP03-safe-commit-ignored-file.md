---
work_package_id: WP03
title: safe-commit pre-check sees what the helper stages
dependencies: []
requirement_refs:
- FR-011
- FR-012
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-6652-verdict-gate-truthfulness
merge_target_branch: issue-6652-verdict-gate-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6652-verdict-gate-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6652-verdict-gate-truthfulness unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 1 - Defect fixes
history:
- at: '2026-10-26T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/safe_commit_cmd.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/safe_commit_cmd.py
- tests/specify_cli/cli/commands/test_safe_commit_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – safe-commit pre-check sees what the helper stages

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objective

`safe-commit docs-local/a.md`, where `docs-local/` is gitignored and the file is the only changed path, exits 0 with `committed: false`; named beside another changed path it is committed (#6649). The CLI pre-check `_has_candidate_changes` omits `--ignored` while the helper force-stages requested paths. Also pin #5393 (non-ASCII directory expansion, verified fixed on `main`) at the command level.

## Branch Strategy

Planning branch and merge target: `issue-6652-verdict-gate-truthfulness`; worktree per computed lane:

```bash
spec-kitty agent action implement WP03 --agent claude --mission truthful-verdicts-and-gates-01M5WZCP
```

## Subtasks

### T010 — Red-first CLI tests

In `tests/specify_cli/cli/commands/test_safe_commit_cli.py`, next to `test_cli_genuinely_different_file_never_reports_no_changes`, using its repo fixture and runner:

1. Lone new file under an ignored directory, named explicitly, `--json` → `committed: true`, `git show --name-status HEAD` lists it.
2. Same file named with a changed tracked file → committed (control; already green).
3. A tracked unchanged file named alone → still `committed: false` (ratchet).
4. #5393: directory `src/` holding a new `café.py` → committed under its real name (`git ls-tree HEAD src/` contains `src/café.py`).

Confirm case 1 fails on the unchanged code.

### T011 — Count named ignored files

`_has_candidate_changes`: `status_entries(repo_root, untracked="all", ignored=True, pathspecs=rel_paths)`. Directory arguments are expanded to non-ignored changed files before this call, so only explicit file arguments are affected. Update the docstring.

### T012 — Verify neighbouring behaviour

Run the existing safe-commit suites; confirm an ignored *directory* argument still expands to `0 files` (documented rule) and the unknown-path refusal (#4722) is unchanged.

## Validation

```bash
uv run --frozen pytest -q tests/specify_cli/cli/commands/test_safe_commit_cli.py \
  tests/specify_cli/cli/commands/test_cli_git_paths.py tests/git_ops/test_safe_commit_helper_integration.py
```

## Definition of Done

- T010 case 1 red first, green after; all listed suites green.
- ruff/format/mypy clean; no suppressions.
