---
work_package_id: WP05
title: mission_state lock canonical
dependencies:
- WP01
requirement_refs:
- FR-008
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-local-write-safety-01M2ZPZD
base_commit: 6663dc6f1e1d8b5bc33af9d582429af0297223ac
created_at: '2026-09-20T20:14:51.321732+00:00'
subtasks:
- T017
- T018
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/unit/migration/test_mission_state_lock_canonical.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/migration/mission_state.py
- tests/unit/migration/test_mission_state_lock_canonical.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (+ `charter context --action implement`); apply and state.

## Objective
Retire the last hand-rolled lock (`migration/mission_state.py`) into the canonical `kernel.locks`
authority so it is symlink-safe (inheriting WP01's `O_NOFOLLOW`) and no longer a canonical-source
violation.

## Context
- `migration/mission_state.py` has a hand-rolled `_git_lock` (`os.open(..., O_CREAT|O_EXCL|O_WRONLY)` with no `O_NOFOLLOW`) that bypasses `kernel.locks` — a latent instance of the FR-010 lock-primitive-ban concern.
- Depends on **WP01** (needs the hardened primitive to actually get symlink-safety — routing through an un-hardened authority would satisfy C-001 but not FR-008).
- **⚠ HARD external gate — PR #4813**: #4813 adds ~180 lines to this same file (up to ~line 1712) but does **not** touch the lock (~line 2339). This WP must be **based on post-#4813 `main`** — keep it in draft until #4813 merges, then rebase; the lock line will have shifted ~+180.
- See `../research.md` D8; overlap analysis in the mission history.

## Subtasks

### T017 — Route the lock through `machine_file_lock`
- Replace the hand-rolled `_git_lock` (`mission_state.py:~2339`, `os.open(..., O_CREAT|O_EXCL|O_WRONLY)`) with `kernel.locks.machine_file_lock` on a dedicated lock path. Remove the raw `os.open`.
- ⚠ **Semantic change**: the hand-rolled lock is **exclusive-create** (a second concurrent acquirer fails because the file exists); `machine_file_lock` is **truncate-and-reuse with an advisory OS lock** (blocking/advisory, never O_EXCL). Preserve the *intended* behavior — do not silently change contention/re-entrancy semantics.

### T018 — Red-first canonical + symlink-safe + parity assertions
- Assert the lock is acquired through `machine_file_lock` (the `test_lock_primitive_ban.py` gate should now cover this site) and does not follow a symlink at the lock path (bytes intact + refuse). Red-first against the hand-rolled version. Isolated HOME.
- **Explicit lock-semantics parity test** (do not rely solely on "existing tests green"): assert the second concurrent acquirer behaves as the migration requires, and re-entrancy/scope is unchanged.

## Branch Strategy
Base/merge `fix/local-write-safety`, **but rebase the WP branch onto post-#4813 `main` before leaving draft** (shared file). Depends on WP01. `spec-kitty agent action implement WP05 --agent claude`.

## Definition of Done (non-fakeable)
- Lock routes through `kernel.locks` (ban-gate green for this site) and is symlink-safe (SC-001); isolated HOME.
- **Lock-semantics parity test** proves concurrent second-acquirer + re-entrancy behavior is preserved (not just "existing tests green").
- Based on post-#4813 `main`; no merge conflict with #4813's `mission_state.py` changes.
- **Red-first evidence**: PR "Tests run" includes the failing-on-hand-rolled output for the symlink-safe assertion.
- Existing mission-state migration tests remain green. ruff + mypy clean; complexity ≤15.

## ⚠ Dispatch gate (enforced by the implement loop, not the scheduler)
The #4813 hard gate is invisible to lane scheduling. **Hold WP05 in draft**; before dispatching it, verify `gh pr view 4813 --repo spec-kitty/spec-kitty --json state` returns `MERGED`, then rebase this WP's base onto post-#4813 `main`. Starting WP05 on a pre-#4813 base is the failure this gate prevents.

## Risks & Reviewer Guidance
- **Risk**: landing before #4813 → conflict/rework. Reviewer: confirm the base includes #4813.
- **Risk**: changing lock semantics (scope/re-entrancy) and breaking migration. Reviewer: confirm behavior parity.
