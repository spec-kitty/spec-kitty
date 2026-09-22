---
work_package_id: WP01
title: Shared overwrite-backup helper (backup_before_overwrite)
dependencies: []
requirement_refs:
- FR-004
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: 9cd349f76a51c7650ff3ebe4e80ac6b3464c603c
created_at: '2026-09-22T18:38:58.396481+00:00'
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/asset_preservation/
create_intent:
- tests/specify_cli/asset_preservation/test_backup_before_overwrite.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/asset_preservation/backup.py
- tests/specify_cli/asset_preservation/test_backup_before_overwrite.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load`
(or the `spk-doctrine-profile-load` skill) for **python-pedro**. Load the profile
YAML — identity, boundaries, governance scope — not merely the persona name. Then
return here.

## Objective

Add ONE shared, symlink-aware `backup_before_overwrite(path: Path) -> Path` to
`src/specify_cli/asset_preservation/backup.py`. This is the single backup-naming
authority for the *overwrite* flows (WP03 hook install reuses it). It creates a
byte-exact in-place sidecar of a file about to be overwritten and returns its path.
It does NOT remove or modify the original.

**Why**: today overwrite flows either destroy the existing file (#4895) or would each
hand-roll a `f"{path}.{ts}"` name. The removal-flow archiver (`archive_into` /
`_allocate_backup_dir`) is the wrong shape — it builds a `.backup-<ts>/` directory tree
for parent-removal. Overwrites need an in-place sidecar (`pre-commit.<ts>`).

## Contract (see contracts/preservation-contract.md §P1)

```
backup_before_overwrite(path: Path) -> Path
```
1. Returns sidecar path `<path>.<timestamp>` (timestamp from the canonical clock seam used elsewhere in the module), created with `O_EXCL` — a collision raises rather than clobbering.
2. Sidecar is byte-identical; mode + mtime preserved where the platform allows.
3. Symlink-aware: if `path` is a symlink, capture the link via `os.readlink` and recreate it — do NOT dereference-and-copy the target silently, do NOT raise on a broken link a readlink would resolve.
4. Does NOT remove/modify `path`.
5. Built on the existing exported `write_file_verbatim` core for the regular-file case (single copy authority). Reuse the module's timestamp seam — do not introduce a second clock.

## Subtasks

### T001 — Implement `backup_before_overwrite`
- Read `src/specify_cli/asset_preservation/backup.py` fully; reuse `write_file_verbatim` and the existing timestamp/clock seam (find how `archive_into` timestamps its dir and reuse the same clock).
- Regular file: allocate `<path>.<ts>`, open with `O_EXCL`, write verbatim bytes, copy mode+mtime.
- Return the sidecar `Path`.
- Add to `__all__`.

### T002 — Symlink handling
- If `path.is_symlink()`: read `os.readlink(path)` and recreate the link at the sidecar path (`os.symlink(target, sidecar)`), rather than reading bytes through the link. Handle a broken link (target missing) without raising where readlink succeeds.
- Keep complexity ≤ 15; extract a small `_backup_symlink` helper if needed.

### T003 — Unit tests (`tests/specify_cli/asset_preservation/test_backup_before_overwrite.py`)
- Byte-identity of a regular file's sidecar; mode + mtime preserved.
- `O_EXCL` collision raises when the sidecar already exists.
- Symlink: sidecar is a symlink to the same target; original link untouched.
- Broken symlink: sidecar recreated, no raise.
- Original file/link is never removed or modified by the call.

## Branch strategy

Planning base `fix/user-content-preservation`; final merge target `fix/user-content-preservation` (then a PR to upstream `main`). The execution worktree is allocated per computed lane from `lanes.json` — do not hand-create branches.

## Definition of Done

- `backup_before_overwrite` implemented per §P1, exported, mypy --strict + ruff clean, complexity ≤ 15.
- Unit tests green; every new branch covered (Sonar new-code).
- No change to `archive_into`/existing removal helpers.

## Reviewer guidance (reviewer-renata, opus)

- Confirm O_EXCL (no silent clobber) and symlink non-dereference.
- Confirm reuse of `write_file_verbatim` + the module clock (no second authority).
- Confirm the original is never mutated.
