---
work_package_id: WP01
title: One owner for the ownership-refusal predicate
dependencies: []
requirement_refs:
- C-005
- FR-005
planning_base_branch: issue-7131-tracked-meta-unanswerable-git
merge_target_branch: issue-7131-tracked-meta-unanswerable-git
branch_strategy: Planning artifacts for this mission were generated on issue-7131-tracked-meta-unanswerable-git. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7131-tracked-meta-unanswerable-git unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tracked-meta-unanswerable-git-01M6GRFF
base_commit: 1a9fcafd13c855851b723e6d95199d93e6565587
created_at: '2026-11-03T13:15:22.075668+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundational
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/git/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/kernel/git/runner.py
- src/kernel/git/__init__.py
- src/specify_cli/core/git_preflight.py
- tests/git_ops/test_git_preflight.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One owner for the ownership-refusal predicate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- One function classifies git's ownership refusal, in `src/kernel/git/runner.py`, next to the
  `GitCommandError` type that already classifies git failures (`not_run`, `timed_out`).
- `src/specify_cli/core/git_preflight.py` uses that function instead of its own private copy.
- No behaviour changes anywhere: `run_git_preflight` reports the same codes, messages and
  remediation commands, and its suite is green without a single relaxed assertion.
- `src/kernel/git/__init__.py` re-exports the function so consumer modules import it from the package
  (the convention `mission_metadata` already follows for `run_git`, `blob_at`, `is_tracked`).

Success criteria: `uv run pytest -q -p no:randomly tests/git_ops/test_git_preflight.py` green with the
new cases; `ruff check`, `ruff format --check --force-exclude` and `mypy` clean on the touched files.

## Context & Constraints

- Read `.kittify/charter/charter.md` (single canonical authority) and
  `kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/plan.md` (IC-02).
- **Why this lands first**: WP02 classifies git's ownership refusal while reading a Mission's tracked
  `meta.json`. The predicate already exists privately in `git_preflight.py`
  (`_is_dubious_ownership`), and adding a second copy in `specify_cli.mission_metadata` would create
  exactly the duplicate-authority problem this repository's charter forbids (C-005).
- **Hard constraint (C-003)**: this WP reads git's refusal. It must not write git config, must not
  add `safe.directory`, and must not suggest a wildcard trust anywhere.
- Do not touch `src/specify_cli/core/git_preflight.py`'s issue codes, message text or remediation
  commands — other tests depend on them verbatim.

## Branch Strategy

- **Strategy**: coordination-branch mission; execution worktrees are allocated per computed lane from
  `lanes.json` by `spec-kitty agent action implement WP01 --agent pi --mission tracked-meta-unanswerable-git-01M6GRFF`.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Add the shared predicate to `src/kernel/git/runner.py`

- **Purpose**: one owner for "git refused this checkout's ownership".
- **Steps**:
  1. Below `GitCommandError` (and its `not_run` property), add
     `def refuses_ownership(stderr: str) -> bool:`.
  2. Body: lowercase the text and return `"dubious ownership" in text or "safe.directory" in text`
     — byte-identical semantics to the private helper being replaced.
  3. Docstring: say that git's message text is the only signal it gives for this refusal, that the
     function is a *classifier* (never a policy decision), and that callers must not treat a `True`
     answer as permission to change trust configuration — the operator decides.
- **Files**: `src/kernel/git/runner.py`
- **Validation**: `uv run --frozen mypy src/kernel/git/runner.py`

### Subtask T002 – Re-export from `src/kernel/git/__init__.py`

- **Purpose**: consumers import from `kernel.git`, as they already do for `run_git`/`blob_at`.
- **Steps**: add `refuses_ownership` to the `from kernel.git.runner import (...)` tuple and to
  `__all__`, keeping the module's existing ordering convention (`__all__` is
  case-then-alpha; the import tuple is alpha).
- **Files**: `src/kernel/git/__init__.py`
- **Validation**: `uv run --frozen python -c "from kernel.git import refuses_ownership; print(refuses_ownership('fatal: detected dubious ownership'))"`

### Subtask T003 – Use it in `src/specify_cli/core/git_preflight.py`

- **Purpose**: delete the private copy so a second authority cannot drift.
- **Steps**:
  1. Import `refuses_ownership` from `kernel.git`.
  2. Delete `_is_dubious_ownership`.
  3. Update its two call sites to the shared name. Keep `_safe_directory_command` and everything the
     preflight *emits* unchanged (this WP changes no remediation text).
- **Files**: `src/specify_cli/core/git_preflight.py`
- **Validation**: `uv run --frozen pytest -q -p no:randomly tests/git_ops/test_git_preflight.py`

### Subtask T004 – Cover the predicate directly

- **Purpose**: the relocation must be witnessed, not assumed, and the kernel function needs its own
  new-code coverage.
- **Steps**: in `tests/git_ops/test_git_preflight.py`, add one parametrized test over the shared
  predicate: git's real dubious-ownership line → `True`; a `safe.directory` line → `True`;
  `fatal: not a git repository (or any of the parent directories): .git` → `False`; an empty string
  → `False`. Keep the module's existing `patch(...)`-based tests untouched.
- **Files**: `tests/git_ops/test_git_preflight.py`
- **Validation**: `uv run --frozen pytest -q -p no:randomly tests/git_ops/test_git_preflight.py`

## Definition of Done

- [ ] `refuses_ownership` lives in `kernel.git.runner`, is re-exported, and is the only definition.
- [ ] `git_preflight` imports it; `_is_dubious_ownership` no longer exists.
- [ ] `tests/git_ops/test_git_preflight.py` passes, with the new predicate cases and no relaxed assert.
- [ ] `ruff check` and `ruff format --check --force-exclude` clean on all four touched files; `mypy` clean.
- [ ] No `safe.directory` write, no wildcard trust, no new config mutation anywhere in the diff.
- [ ] Commits are small, imperative, and mention the issue (`#7131`).

## Risks & Mitigations

- **Import cycle**: `specify_cli.core.git_preflight` already imports from `specify_cli.core`;
  `kernel.git` is a leaf package with no `specify_cli` import, so the direction is safe. If mypy or an
  import gate disagrees, report it rather than reaching for a local copy.
- **`__all__` gate**: `tests/architectural/` has convention gates on `__all__`; follow the file's own
  ordering exactly.

## Reviewer Guidance

- Confirm `git diff` shows a *move*, not a rewrite: the two matched substrings must be unchanged.
- Confirm the preflight tests pass unmodified (only additive changes to the test file).
- Confirm nothing in the diff writes git configuration.
