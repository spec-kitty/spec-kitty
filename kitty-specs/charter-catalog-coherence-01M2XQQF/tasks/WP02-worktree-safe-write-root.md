---
work_package_id: WP02
title: Worktree-safe charter-write root helper
dependencies: []
requirement_refs:
- C-002
- C-003
- FR-006
- NFR-003
- NFR-004
planning_base_branch: issue-4785-charter-catalog-coherence
merge_target_branch: issue-4785-charter-catalog-coherence
branch_strategy: Planning artifacts for this mission were generated on issue-4785-charter-catalog-coherence. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4785-charter-catalog-coherence unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-catalog-coherence-01M2XQQF
base_commit: ba02af2d372493d6730cf7b37c4f039a1f300532
created_at: '2026-09-19T21:48:07.493892+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 1 - Foundation
history:
- at: '2026-09-19T21:23:09Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- src/specify_cli/cli/commands/charter/_charter_write_root.py
- tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/charter/_charter_write_root.py
- tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Worktree-safe charter-write root helper

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Provide the ONE shared, tested authority for charter-write checkout safety (issue #4785,
Finding 3). Every charter write command (wired up in WP03/WP04) will call it.

Done when:
- A new helper resolves the charter-write root and **fails closed** (raises a clear, actionable
  error) when invoked from inside a **linked git worktree**, so no charter write silently lands in
  the PRIMARY checkout (FR-006).
- Detection uses the kernel `git_topology` probe (git-dir vs git-common-dir), NOT a `.worktrees/`
  path-substring match (NFR-003, C-003).
- Git-absent / non-repo invocation degrades safely (treated as not-a-linked-worktree; no crash).
- The shared `find_repo_root` / `get_main_repo_root` are **not** modified (C-002).

## Context & Constraints

- Read: `research.md` (Finding 3), `contracts/behavior-contracts.md` (C3), `data-model.md`
  (checkout topology table).
- **Do NOT** change `src/specify_cli/task_utils/support.py:find_repo_root` or
  `src/specify_cli/core/paths.py:get_main_repo_root` — they are shared far beyond charter and must
  keep their follow-to-primary behavior.
- Reuse `src/kernel/git_topology.py` (the canonical probe; ~20 other consumers). Do not add a fourth
  root-resolution authority.
- The error message must name the remedy: "use a repository-root checkout or dedicated clone for
  charter authoring" and the command must exit non-zero (the CLI wiring in WP03/WP04 maps the raised
  error to a non-zero exit).

## Branch Strategy

- **Strategy**: rebase-merge to `main` via non-draft PR (operator merges)
- **Planning base branch**: `issue-4785-charter-catalog-coherence`
- **Merge target branch**: `main`
- Implement command: `spec-kitty agent action implement WP02 --agent claude`

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first repro (RED before fix)
- **Purpose**: Pin the cross-checkout-write hazard at the helper level.
- **Steps**: In `tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py`, add
  `@pytest.mark.regression` (#4785) tests that construct a primary checkout + a linked worktree
  (tmp git repos) and assert the helper raises the fail-closed error from the linked worktree while
  returning the checkout root from the primary. RED before the helper exists.
- **Files**: test file (new).

### Subtask T009 – Implement `_charter_write_root.py`
- **Purpose**: The shared worktree-safe resolver.
- **Steps**: Add `resolve_charter_write_root(start: Path) -> Path`. Kernel `git_topology` exposes only
  `git_toplevel(path)` (`:152`) and `git_common_dir(path)` (`:121`) — there is no direct `--git-dir`
  accessor. **Linked-worktree detection (model on `src/specify_cli/core/checkout_ownership.py:110-167`)**:
  primary checkout ⇒ `git_common_dir(p).parent == git_toplevel(p)`; linked worktree ⇒ they differ →
  raise a dedicated typed error with the message "use a repository-root checkout or dedicated clone for
  charter authoring". **git-absent / not-a-repo**: `git_topology` raises `GitTopologyUnavailableError`
  / `NotAGitRepositoryError` (both subclass `GitTopologyError`, `:59/:69/:81`) — **catch these and
  DEGRADE SAFELY (return the resolved root, no raise)**, i.e. treat as not-a-linked-worktree. Never use
  a `.worktrees/` path-substring match.
- **Files**: `src/specify_cli/cli/commands/charter/_charter_write_root.py` (new).

### Subtask T010 – Unit tests (make T008 green + cover branches)
- **Purpose**: Prove all branches.
- **Steps**: Cover: primary checkout → returns root; linked worktree → raises with the remedy
  message; git-absent → safe; simulate the topology via monkeypatch for a cross-platform-style path
  (per the `os.replace`/monkeypatch pattern in the repo memory — do not rely on OS-specific paths).
- **Files**: test file.

## Test Strategy

- `PYTHONPATH=src python -m pytest tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py -q`
- Record RED-before / GREEN-after in the Activity Log.

## Risks & Mitigations

- **Over-broad refusal**: only refuse for a *linked* worktree (git-dir != git-common-dir), never for
  a normal primary checkout. Test both.
- **git_topology API drift**: confirm the exact function names in `src/kernel/git_topology.py`
  (`git_toplevel` + common-dir helpers) before wiring.

## Review Guidance

- Verify `find_repo_root`/`get_main_repo_root` are untouched (C-002).
- Verify detection is topology-based, not path-substring (NFR-003).
- Verify the error message names the remedy and the resolver is pure/testable.

## Activity Log

- 2026-09-19T21:23:09Z – system – Prompt created.
