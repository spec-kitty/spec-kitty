---
work_package_id: WP02
title: Cold-install sentinel relocation
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-011
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/
create_intent:
- tests/runtime/test_cold_install_sentinel_relocation.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/runtime/asset_preparation.py
- tests/runtime/test_cold_install_sentinel_relocation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (+ `spec-kitty charter context --action implement --json`); apply and state identity/boundaries/directives/tactics.

## Objective

Move the cold-install lock sentinel out of world-shared `$TMPDIR` into the per-user runtime root
so another local user cannot pre-plant its path. Pairs with WP01's `O_NOFOLLOW` for defense-in-depth.

## Context

- `runtime/asset_preparation.py:~761` (`_cold_install_sentinel`) places the sentinel at
  `Path(tempfile.gettempdir()) / "spec-kitty-cold-install" / f"{sha256(anchor)[:16]}.lock"` and
  `mkdir(parents=True, exist_ok=True)` (no mode) — a machine-predictable, world-shared path.
- Depends on **WP01** (the hardened `machine_file_lock` + no-follow). Route the sentinel through
  `machine_file_lock`, whose `_ensure_dir` already chmods the parent `0700` (C-005) — do **not**
  hand-roll a new `mkdir(0700)`.
- See `../research.md` D3.

## Subtasks

### T005 — Relocate the sentinel to the per-user runtime root
- Compute the sentinel under the per-user runtime root (`~/.spec-kitty`, e.g. `get_runtime_root()`), not `tempfile.gettempdir()`.
- Acquire it via `machine_file_lock` so the `0700` parent is established by the canonical authority (single owner, FR-011). Remove the bare `mkdir(exist_ok=True)`.

### T006 — Red-first symlink-plant on the sentinel path  [P]
- Before the fix, prove the plant truncates (red). After: plant a symlink at the computed sentinel path → victim file; **exercise the real cold-install entry (`_cold_install_sentinel` / the production acquisition), not a re-implementation of the path** (a reconstructed open proves nothing about prod code); assert victim bytes unchanged AND the op refuses. Isolated HOME.

### T007 — Relocation + mode assertion  [P]
- Assert the resolved sentinel path is under `~/.spec-kitty` (isolated HOME), **not** `$TMPDIR`, and the parent dir is `0700` (SC-006).

## Branch Strategy
Base/merge: `fix/local-write-safety`. Depends on WP01 — rebase onto WP01 once it lands so the hardened primitive is present. `spec-kitty agent action implement WP02 --agent claude`.

## Definition of Done (non-fakeable)
- Symlink-plant leaves victim bytes intact + op refuses (SC-001).
- Resolved sentinel path asserted under `~/.spec-kitty` (0700), not world-shared temp (SC-006) — reject a test that only checks the string, assert on the resolved path in an isolated HOME.
- **Red-first evidence**: PR "Tests run" includes the failing-on-current-code output for the sentinel symlink-plant test.
- ruff + mypy clean.

## Risks & Reviewer Guidance
- **Risk**: `_ensure_dir` skips chmod on a pre-existing attacker dir — the whole point of relocation is that the parent is now under the user-owned root. Reviewer: confirm the sentinel is no longer under `gettempdir()` anywhere.
