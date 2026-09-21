---
work_package_id: WP01
title: Kernel no-follow foundation
dependencies: []
requirement_refs:
- FR-001
- FR-003
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-write-safety-01M2ZPZD
base_commit: a5f50cd9bb37c35711c5b4c7ffc893a138a5a024
created_at: '2026-09-20T16:46:11.497809+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/
create_intent:
- src/kernel/no_follow.py
- tests/kernel/test_no_follow.py
- tests/kernel/test_locks_symlink_safe.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/no_follow.py
- src/kernel/locks.py
- src/specify_cli/core/no_follow.py
- tests/kernel/test_no_follow.py
- tests/kernel/test_locks_symlink_safe.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load` (or
`spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --json`)
and apply its identity, boundaries, directives, and tactics. State which you applied.

## Objective

Make the **canonical lock authority symlink-safe** and establish **one canonical no-follow module
at the kernel layer**. This is the foundation every other WP depends on — a regression here reds
the whole lock surface, so treat it as tier-1.

## Context

- Root cause of #4756 lives in `src/kernel/locks.py`: `_LockCore.open_fd` opens with
  `os.O_RDWR | os.O_CREAT` and **no `O_NOFOLLOW`**; `release()`/`force_release` then truncate the
  followed inode. A planted symlink at a lock path truncates the victim.
- The no-follow helper (`open_no_follow`, `NoFollowPathError`, `chmod_fd`,
  `fd_relative_dir_ops_supported`, `read_text_no_follow`, `write_text_no_follow`) currently lives in
  `src/specify_cli/core/no_follow.py`. `kernel.locks` **cannot** import it (violates the enforced
  `kernel ↛ specify_cli` direction). So the module must be hoisted **down** to `kernel/`.
- See `../contracts/no-follow-open.md` and `../research.md` D1/D2.

## Subtasks

### T001 — Hoist the whole no-follow module to `kernel/`
- Move the **entire** `src/specify_cli/core/no_follow.py` (all six symbols) to `src/kernel/no_follow.py`. It imports only stdlib (`os`, `errno`, `pathlib`) — layer-clean.
- Replace `src/specify_cli/core/no_follow.py` body with `from kernel.no_follow import *` and an `__all__` **identical to today's** (all six names).
- `NoFollowPathError` must remain a **single class object** (re-exported, not redefined) — `git_common/gitignore_manager.py:18` does `except NoFollowPathError`; a redefinition silently breaks the catch.
- Keep `open_no_follow(path, flags, mode=0o666)` signature byte-identical.

### T002 — Add `O_NOFOLLOW` to the lock primitive
- In `kernel.locks._LockCore.open_fd` add `getattr(os, "O_NOFOLLOW", 0)` to the open flags; do the same at the raw `os.open` in `force_release`.
- **Do NOT add `O_EXCL`** — lock files are re-opened by later acquirers (release truncates, never unlinks); `O_EXCL` would break re-acquisition (C-003).
- Prefer routing the open through `kernel.no_follow.open_no_follow` so there is one no-follow implementation.
- Windows: `O_NOFOLLOW` resolves to `0` (documented safe-degrade).

### T003 — Red-first symlink-plant regression on the lock path
- Write the test **before** the fix and confirm it fails on the un-hardened primitive.
- Plant a symlink at a computed lock path → a victim file with known bytes; acquire the lock; assert (1) victim bytes **unchanged** and (2) the acquire **raises `NoFollowPathError`** (never exit-0).
- Use the **isolated per-worker HOME**, never the real `~/.spec-kitty`.

### T004 — Blast-radius verification
- Run and keep green: the **11 `specify_cli.core.no_follow` importers** (coordination/atomic_write, git_common/gitignore_manager, intake/brief_writer, session_presence/writers/markdown_rules, skills/{command_installer,installer,manifest_store}, tool_surface/{bundles/projection, providers/agent_profiles, providers/session_presence}, upgrade/migrations/m_3_2_8) **and** the 13 `kernel.locks` consumers (auth, checkout, status, merge, review, lanes/auto_rebase, tracker, zeitgeist, asset_preparation, windows_migrate, _auth_doctor).
- Keep `tests/architectural/test_lock_primitive_ban.py` and `test_layer_rules.py` green.

## Branch Strategy

Planning/base branch: `fix/local-write-safety`. Final merge target: `fix/local-write-safety`
(the mission branch, which is PR'd to `main` by the operator). Execution worktree is allocated
per computed lane from `lanes.json` — do not hand-create branches. This WP has **no dependencies**;
implement it first: `spec-kitty agent action implement WP01 --agent claude`.

## Definition of Done (non-fakeable)
- Symlink-plant test proves victim bytes intact **AND** raise (not exit-0) — reject a test that only asserts "the helper is used" or "the path moved" (SC-001).
- `core/no_follow.py` still exports the full 6-symbol `__all__`; `NoFollowPathError` identity preserved (importers unmodified).
- No `O_EXCL` on the shared lock open; re-acquisition still works.
- All 11 importer + 13 consumer + ban-gate + layer tests green on POSIX; Windows lock parity unbroken (SC-004).
- **Red-first evidence**: PR "Tests run" includes the failing-on-un-hardened-primitive output for the symlink-plant test (command + failure), so red-first is verifiable after the fix lands.
- ruff + mypy clean; complexity ≤15.

## Risks & Reviewer Guidance
- **Risk**: redefining `NoFollowPathError` in kernel while `core` keeps its own → silent `except` miss. Reviewer: confirm identity (`core.NoFollowPathError is kernel.no_follow.NoFollowPathError`).
- **Risk**: `O_EXCL` sneaking in → breaks every lock re-acquisition. Reviewer: grep the diff for `O_EXCL` on the lock path.
- **Risk**: layer violation. Reviewer: confirm `kernel/no_follow.py` imports only stdlib.
