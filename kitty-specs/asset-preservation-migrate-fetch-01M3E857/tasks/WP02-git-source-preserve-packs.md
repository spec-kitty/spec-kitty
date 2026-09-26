---
work_package_id: WP02
title: 'git-source fetch preserves hand-authored packs (#4960, #4989)'
dependencies: []
requirement_refs:
- FR-003
- FR-004
planning_base_branch: spec/asset-preservation-migrate-fetch
merge_target_branch: spec/asset-preservation-migrate-fetch
branch_strategy: Planning artifacts for this mission were generated on spec/asset-preservation-migrate-fetch. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into spec/asset-preservation-migrate-fetch unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-asset-preservation-migrate-fetch-01M3E857
base_commit: 0eb94038e5d87a5e31ec7ff4c880573228affbf4
created_at: '2026-09-26T07:26:51.336019+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 1 - Product fixes
history:
- at: '2026-09-26T07:18:36Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/doctrine/sources/git_source.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/sources/git_source.py
- tests/specify_cli/doctrine/test_sources.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – git-source fetch preserves hand-authored packs (#4960, #4989)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the frontmatter profile and behave per its guidance first.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix #4960 and #4989 in `src/specify_cli/doctrine/sources/git_source.py`:
- `_first_install` must never `rmtree` a pre-existing hand-authored pack when a clone fails (#4960).
- `_update` must never silently discard local pack edits (committed or uncommitted), and a configured
  `ref` must actually advance the pack (#4989).

Done when:
- A non-empty `local_path` that is not a valid clone survives a failed/unreachable clone (only a
  fetch-created temp is ever removed); a pre-existing EMPTY dir is still permitted.
- `_update` on a dirty OR ahead-of-upstream pack preserves the local content git-natively (reported) or
  fail-closed refuses — never silent `reset --hard` discard.
- A pack with `ref: <branch>` advances to `origin/<branch>`; a pack pinned to a tag/SHA still resolves
  correctly (no regression).
- Red-first regressions RED before, GREEN after; re-pinned call-order test passes.

## Context & Constraints

- Authority: `../research.md` F2, F3, F6, F7, F8; `../contracts/preservation-contract.md` Site B; `../plan.md`.
- **Reference pattern (F8)**: `src/specify_cli/doctrine/snapshot.py:196-228` (move-aside `.old-<uuid>` →
  promote `.tmp-<uuid>` → restore-on-failure → delete backup only after success) and staging `:122-137`.
  Use this, NOT a bare `Path.replace` (raises on non-empty, and on Windows even onto an existing empty dir).
- **fetch() dispatch**: `_update` when `(target_dir/".git").exists()` else `_first_install` (git_source.py:51-53).
  A valid clone never reaches `_first_install`, so the refusal condition there is "exists AND non-empty",
  NOT "is a clone of url" (do not build a url-comparison helper for `_first_install`).
- **Caller constraint (F8)**: `doctrine/template_render/resolve.py::_resolve_git` (:239-243) passes an EMPTY
  `mkdtemp` dir to `fetch()` — the refuse-on-exists rule MUST permit an empty dir.
- **Ref resolution (F6)**: resolve `origin/<ref>` only when `git rev-parse --verify --quiet
  refs/remotes/origin/<ref>` succeeds (branch); otherwise use bare `<ref>` (tag/SHA). A blanket
  `origin/<ref>` regresses tag- and SHA-pinned packs.
- **Local-commit preservation (F7)**: `_dirty_entries` is status-only and returns `[]` for a clean worktree
  with commits ahead of upstream, and a worktree archive cannot preserve `.git` history. So add an explicit
  ahead check (`git rev-list --count origin/<ref>..HEAD` > 0) AND the dirty check; for dirty OR ahead/
  divergent, preserve git-natively (create a backup branch/ref, e.g. `git branch backup/<utc-stamp> HEAD`,
  or preserve the whole dir incl. `.git`) OR fail-closed refuse. A worktree-bytes archive alone is insufficient.
- **Dirty predicate reuse (F7)**: `src/specify_cli/git/ref_advance.py::_dirty_entries` is kw-only —
  compute the resolved target SHA and `target_paths = _target_tree_paths(worktree, new_sha, env)` first
  (see caller `src/specify_cli/git/destructive_guard.py:189-197`), then call it. Do NOT add a parallel
  `git status --porcelain` predicate (arch gate T019 forbids it).
- Reuse `asset_preservation/backup.py` (`backup_before_overwrite`/`archive_into`) for worktree-content backup
  where applicable. No CLI version bump (C-002).

## Branch Strategy

- **Strategy**: pr-bound feature branch
- **Planning base branch**: `spec/asset-preservation-migrate-fetch`
- **Merge target branch**: `spec/asset-preservation-migrate-fetch`

> Work only inside your lane worktree. `.venv/bin/python`, never bare `uv run`. Prefix `PWHEADLESS=1`.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first regressions
- **Purpose**: prove #4960/#4989 and lock the fixes.
- **Steps**: In `tests/specify_cli/doctrine/test_sources.py` (class `TestGitSource`), add `@pytest.mark.regression`
  tests (use scratch temp git repos + a local bare remote, no network):
  1. pre-existing non-empty non-`.git` `local_path` + failing clone (bad url) → files survive; only temp removed.
  2. clone succeeds then `git checkout <ref>` fails → pre-existing content restored/intact.
  3. pre-existing EMPTY `local_path` → clone proceeds (permitted).
  4. `_update` with a dirty worktree → local edits preserved/backed up (reported), not discarded.
  5. `_update` with a committed-ahead pack (clean worktree, local commit ahead of origin) → the local commit
     is recoverable (backup branch/ref) or the update refuses; assert NOT silently orphaned.
  6. `ref="main"` update after origin advanced → pack advances (reset resolves `origin/main`).
  7. tag-pinned and SHA-pinned `ref` → still resolve (no `origin/<tag>` regression).
- **Files**: `tests/specify_cli/doctrine/test_sources.py`
- **Notes**: cite `#4960`/`#4989` in docstrings.

### Subtask T008 – `_first_install` clone-to-temp + move-aside + refuse-on-nonempty
- **Purpose**: fix #4960.
- **Steps**: Rewrite `_first_install` to (a) refuse up front when `target_dir` exists and is non-empty
  (permit absent/empty); (b) clone into a `.tmp-<uuid>` sibling; (c) on clone/checkout failure remove ONLY the
  temp (never `target_dir`); (d) on success promote via the `snapshot.py:196-228` move-aside pattern.
- **Files**: `src/specify_cli/doctrine/sources/git_source.py`

### Subtask T009 – `_update` ref-type resolution + ahead/dirty preservation
- **Purpose**: fix #4989 (both sub-bugs).
- **Steps**: Resolve the reset target by ref type (branch → `origin/<ref>`, else bare `<ref>`). Before any
  `git reset --hard`, run the ahead check and `_dirty_entries` (wired per Context). For dirty OR
  ahead/divergent, create a git-native backup (backup branch/ref) or fail-closed refuse with a clear message.
  Keep the existing safe fetch-failure early return (:88-95).
- **Files**: `src/specify_cli/doctrine/sources/git_source.py`

### Subtask T010 – Re-pin call-order test
- **Purpose**: F9 — inserting dirty/ahead checks changes the git call sequence.
- **Steps**: Re-pin `test_sources.py:188-191` (`test_update_path_used_when_dot_git_exists`, asserts
  `runner.calls[0]=="fetch"`, `calls[1]=="reset"`) to the new call order. Re-verify `:214`
  (`test_first_install_failure_cleans_up`) and `:264` (`test_ref_checkout_after_first_clone`) against the
  temp-swap ordering; adjust to assert the pre-existing-dir preservation semantics.
- **Files**: `tests/specify_cli/doctrine/test_sources.py`

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/doctrine/test_sources.py -q -p no:xdist`
- New code must pass `ruff check` and `mypy` clean (no new `# noqa`/`# type: ignore`).

## Risks & Mitigations

- **Tag/SHA regression** from blanket `origin/<ref>` — mitigated by ref-type resolution (test #7).
- **Committed-ahead history loss** — mitigated by git-native backup/refuse, not worktree archive (test #5).
- **Cross-platform swap** onto existing dir — mitigated by move-aside pattern + refuse-on-nonempty.
- **Caller `_resolve_git`** passes empty dir — must remain permitted (test #3).

## Review Guidance

- MUTATION TEST: restore the unconditional `rmtree(target_dir)` and the bare-`<ref>`/blanket-`origin/<ref>`
  reset → tests MUST go RED. If any mutant stays green, reject.
- Confirm committed-ahead preservation is git-native (a worktree copy is NOT acceptable).
- Confirm `_resolve_git`'s empty-dir caller still works.
- Issue-matrix: #4960 → WP02, #4989 → WP02.

## Activity Log

- 2026-09-26T07:18:36Z – system – Prompt created.
