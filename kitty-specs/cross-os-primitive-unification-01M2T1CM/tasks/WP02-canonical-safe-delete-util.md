---
work_package_id: WP02
title: Canonical safe-delete util (lstat+S_IMODE, no-follow)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: feat/cross-os-primitive-unification
merge_target_branch: feat/cross-os-primitive-unification
branch_strategy: Planning artifacts for this mission were generated on feat/cross-os-primitive-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cross-os-primitive-unification unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cross-os-primitive-unification-01M2T1CM
base_commit: 257e1a67568a9fe2e26c439ce842376d5c0b6ac8
created_at: '2026-09-18T11:37:59.394205+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Implementation
history:
- at: '2026-09-18T11:05:00Z'
  actor: system
  action: Prompt generated for cross-os-primitive-unification mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/safe_delete.py
create_intent:
- src/specify_cli/core/safe_delete.py
- tests/specify_cli/core/test_safe_delete.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/safe_delete.py
- src/specify_cli/skills/installer.py
- src/specify_cli/runtime/agent_skills.py
- tests/specify_cli/core/test_safe_delete.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4714'
---

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill before proceeding.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

Create one canonical managed-asset safe-delete util with the correct **no-follow
(`lstat`) + masked (`S_IMODE`)** contract, and consolidate the `installer.py` and
`agent_skills.py` copies onto it. (The third live copy, in
`runtime/asset_preparation.py`, is removed in WP04 where that file gets its full
lock+FR-011 treatment — a sequencing choice so the file has one owner per wave.)

Read first: `../spec.md` (FR-001/002/003, C-002, SC-001/006),
`../contracts/safe-delete-and-os-seam.md` §A, `../data-model.md` E-02,
`../research.md` R-02.

**Success**: one implementation; the two copies deleted; a test proves the
no-follow semantics do not touch a symlink target outside the managed tree.

## Context

Grounding confirmed the contract split: `asset_preparation._force_writable` uses
`stat.S_IMODE(path.lstat().st_mode)` (no-follow, masked — the CORRECT one to
adopt); `installer._make_path_writable` and `agent_skills._make_path_writable`
use `path.stat().st_mode` (follow-symlink, unmasked — the ones to replace). A
managed-asset delete must never follow a symlink out of the managed tree
(boundary leak / CWE-59-adjacent). The frozen migration copy in
`upgrade/migrations/m_3_2_0rc45_retire_standalone_skill_surface.py` is **immutable
— do not touch it** (C-002).

**Live risk (SC-006, A-02)**: the command-globalization surface materializes
managed commands as *symlinks* (`migrations/m_3_1_2_globalize_commands.py`
chmods via `target.stat()`). Switching to no-follow could relocate a
`PermissionError` onto the link target if any caller relied on follow-chmod. You
must prove the *negative* — no caller depends on it — with T009.

## Subtasks

### T006 — Create the canonical util
`src/specify_cli/core/safe_delete.py`:
```python
def force_writable(path: Path) -> None:
    """Restore the owner write bit before removing a managed asset (no-follow)."""
    with suppress(OSError):
        path.chmod(stat.S_IMODE(path.lstat().st_mode) | stat.S_IWRITE)

def safe_unlink(path: Path) -> None: ...   # unlink; on OSError: force_writable + retry
def safe_rmdir(path: Path) -> None: ...     # rmdir; on OSError: force_writable + retry
def safe_rmtree(path: Path) -> None: ...    # shutil.rmtree(onerror=<force-writable shim>)
```
Match the existing docstring rationale in `asset_preparation._force_writable`.

### T007 — Route installer.py
Replace `_make_path_writable`/`_force_writable_and_retry`/`_safe_unlink`/
`_safe_rmdir`/`_safe_rmtree` with imports from `core.safe_delete`; delete the
private definitions (L70-99). Keep call sites (L79/87/95/100/214/979) working.

### T008 — Route agent_skills.py
Same: delete `_make_path_writable`/`_force_writable_and_retry`/`_safe_unlink`/
`_safe_rmtree` (L62-84); import from `core.safe_delete`; keep call sites.

### T009 — Tests (SC-001/006)
`tests/specify_cli/core/test_safe_delete.py`:
- **SC-006 negative proof**: create a managed dir containing a symlink whose
  target file lives OUTSIDE the managed tree (read-only). `safe_unlink` the
  symlink → assert the symlink is gone AND the target's mode + existence are
  unchanged (no follow-chmod).
- Read-only (`0o444`) file and read-only directory delete succeed.
- **`safe_rmtree` over a tree CONTAINING a read-only file AND a symlink** whose
  target is outside the managed tree — exercises the `onerror` force-writable shim
  branch (a distinct code path) and confirms no-follow holds inside rmtree too
  (post-tasks squad N-3).
- Coverage of `force_writable`/`safe_unlink`/`safe_rmdir`/`safe_rmtree` branches
  (diff-cover ≥90%).

## Branch Strategy

Planning base and merge target: `feat/cross-os-primitive-unification`. Runs in
its computed lane worktree; merges back to the mission branch (PR → `skupstream/main`).

## Definition of Done

- `core/safe_delete.py` exists with the no-follow/masked contract.
- `installer.py` + `agent_skills.py` copies deleted; call sites route through it.
- SC-006 negative-proof test green; read-only delete tests green.
- `ruff`/format clean; complexity ≤15.

## Risks

- **Follow→no-follow regression** (the whole point of SC-006): if T009 finds a
  caller that DID rely on follow-chmod, stop and escalate — the contract choice
  may need a documented exception rather than a blind switch.
- Do not touch `asset_preparation.py` (owned by WP04) or the frozen migration.

## Reviewer guidance (reviewer-renata, opus)

Confirm the adopted semantics are `lstat`+`S_IMODE`; the two copies are gone; the
symlink-negative test genuinely proves the target is untouched (not just that the
link is removed); the frozen migration is unchanged.
