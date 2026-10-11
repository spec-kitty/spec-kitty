---
work_package_id: WP03
title: '#5434 lane worktree .spec-kitty exclude + migration + dead-writer removal'
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- SC-002
planning_base_branch: fix/5964-5434-4796-govern-user-content
merge_target_branch: fix/5964-5434-4796-govern-user-content
branch_strategy: Planning artifacts for this mission were generated on fix/5964-5434-4796-govern-user-content. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5964-5434-4796-govern-user-content unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-govern-user-content-safety-01M4NWGM
base_commit: 712caec82fa7fa265cca177d3b978ecf168806b9
created_at: '2026-10-11T17:32:03.327060+00:00'
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 2 - Fixes
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_exclude_spec_kitty.py
- tests/upgrade/test_exclude_spec_kitty_migration.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_exclude_spec_kitty.py
- src/specify_cli/core/worktree.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/upgrade/test_exclude_spec_kitty_migration.py
- tests/integration/core/test_worktree_exclude_spec_kitty.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '5434'
---
# Work Package Prompt: WP03 – #5434 lane worktree .spec-kitty exclude

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/spk-charter-profile-load`, then `spec-kitty charter context --action implement --json`.

## Problem (grounded at HEAD 3498b426)
`src/specify_cli/core/worktree.py::_ensure_spec_kitty_exclude` (~:38-109) writes `.spec-kitty/` into the PER-WORKTREE `.git/worktrees/<name>/info/exclude` (via `git rev-parse --git-dir`), which git does NOT read; only the common-dir `.git/info/exclude` is honoured. It is called from two already-dead functions (`create_wp_workspace` ~:241, `create_feature_worktree` ~:421). So `allocate_lane_worktree`'s `_validate_worktree_clean` (`worktree_allocator.py:~1849`) sees `?? .spec-kitty/` and raises `DirtyWorktreeError` on reuse/crash-recovery. WP01 `test_lane_worktree_spec_kitty_residue_5434.py` is RED on this. Independent of the residue predicate.

## Approach (C-001, C-002 smallest viable)
- T009: in `allocate_lane_worktree`, at the single code-lane choke point (`worktree_allocator.py:~1085-1087`, where `install_lane_tip_recorder(repo_root)` runs — BEFORE both `_validate_worktree_clean` calls), add `exclude_from_git_index(repo_root, [".spec-kitty/"])` (reuse `core/git_ops.py::exclude_from_git_index`, ~:223). Assert/comment that `repo_root` is the main repo (not a worktree; `.git` must be a dir).
- T010: new migration `m_4_0_0rc8_exclude_spec_kitty.py`, modeled 1:1 on `m_0_13_1_exclude_worktrees.py` (`detect`/`can_apply`/`apply`), pattern `.spec-kitty/`, `target_version` aligned to the release this ships in (confirm against any version bump; rc8 is the current assumption). Register with `@MigrationRegistry.register`.
- T011: DELETE `_ensure_spec_kitty_exclude` + its two call sites (`core/worktree.py`); drop the two now-removed rows from `tests/architectural/dead_symbol_allowlist.yaml` (the `create_feature_worktree`/`create_wp_workspace` rows ONLY if their deletion makes them vanish — otherwise leave the functions; scope is the writer, not the whole legacy cluster). Do NOT delete the larger `core/worktree.py`/`core/vcs` cluster (out of scope).
- T012: new `tests/upgrade/test_exclude_spec_kitty_migration.py` (mirror `test_exclude_worktrees_migration.py`): real repo, `detect` flips True→False, `apply` adds `.spec-kitty/` to common-dir exclude + `git status --porcelain` empty, idempotent, no-op on non-git dir. Remove/replace the wrong-location `tests/integration/core/test_worktree_exclude_spec_kitty.py`.

## Acceptance
- WP01 `test_lane_worktree_spec_kitty_residue_5434.py` → GREEN (clean porcelain, no `DirtyWorktreeError` on reuse + recovery).
- Migration test green + idempotent. Dead writer gone; dead-symbol gate still passes.

## Validation
`PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes/test_worktree_allocator.py tests/lanes/test_lane_worktree_spec_kitty_residue_5434.py tests/upgrade/test_exclude_spec_kitty_migration.py -q`; the specific dead-symbol arch-gate file (`tests/architectural/test_no_dead_symbols.py`) NOT the bare dir; `make test-fast`. `ruff`/`mypy --strict` clean. Record counts.
