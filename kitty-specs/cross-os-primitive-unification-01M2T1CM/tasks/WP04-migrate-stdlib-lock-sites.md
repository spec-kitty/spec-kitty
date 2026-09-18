---
work_package_id: WP04
title: Migrate stdlib-family lock sites incl. the
dependencies:
- WP02
- WP03
requirement_refs:
- FR-003
- FR-008
- FR-011
planning_base_branch: feat/cross-os-primitive-unification
merge_target_branch: feat/cross-os-primitive-unification
branch_strategy: Planning artifacts for this mission were generated on feat/cross-os-primitive-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cross-os-primitive-unification unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 1 - Implementation
history:
- at: '2026-09-18T11:05:00Z'
  actor: system
  action: Prompt generated for cross-os-primitive-unification mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/runtime/asset_preparation.py
create_intent:
- tests/runtime/test_asset_preparation_lock_migration.py
- tests/runtime/test_bootstrap_lock_migration.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/runtime/asset_preparation.py
- src/specify_cli/runtime/bootstrap.py
- src/specify_cli/tracker/credentials.py
- src/specify_cli/paths/windows_migrate.py
- src/specify_cli/review/pre_review_gate.py
- tests/runtime/test_asset_preparation_lock_migration.py
- tests/runtime/test_bootstrap_lock_migration.py
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

Migrate the raw `msvcrt`/`fcntl` lock sites onto the canonical `kernel/locks.py`
primitive, and give `runtime/asset_preparation.py` its full treatment (remove its
safe-delete copy → route onto WP02's util; fold the FR-011 hardening; migrate its
`_HELD_LOCKS` cold-install locking — the #4703-origin site). Shrink the lock + OS
gate allowlists for the files this WP owns.

Read first: `../spec.md` (FR-003/008/011, SC-003), `../contracts/lock-primitive.md`
(§Migration acceptance), `../research.md` R-03, `../data-model.md` E-01.

**Success**: no raw `msvcrt`/`fcntl` remains in the owned files; each site passes
the parity harness; the gate allowlist shrinks (never grows).

## Context

Depends on WP02 (safe-delete util) and WP03 (lock primitive). `asset_preparation.py`
is co-owned in reality by three concerns — this WP does ALL of them so the file
has a single owner: (a) route its `_is_windows` through the kernel seam and
delete the local def, (b) remove its `_force_writable`/`_safe_unlink`/`_safe_rmdir`
copy and route onto `core.safe_delete`, (c) fold FR-011, (d) migrate `_HELD_LOCKS`
locking. The `_HELD_LOCKS` serialization (~L801-835) is the exact fork the #4703
point fix *increased* — retiring it onto the canonical primitive is the mission's
headline.

## Subtasks

### T015 — asset_preparation: safe-delete copy removal + OS routing
Delete `_force_writable`/`_safe_unlink`/`_safe_rmdir` (L901-931); route callers
(L921/930/939/941/955) onto `core.safe_delete` (WP02). Delete the local
`_is_windows` (L741-746) and route through `kernel.paths.is_windows` — **preserve
its testability intent** (the seam is patchable without faking `os.name`); shrink
its OS-gate allowlist entry.

### T016 — asset_preparation: FR-011 folds
- Normalize the anchor path (case/trailing-slash) **before** the `sha256` sentinel
  keying so equivalent spellings key one sentinel, not several.
- Add the defensive `node_state` read guard in `_children_tolerated` (an "extra"
  child's bytes are read; guard against a missing/oversized read even though a
  recorded self-held lock never reaches that branch).

### T017 — asset_preparation: migrate _HELD_LOCKS onto kernel/locks.py
Replace the hand-rolled anchor-dir flock / temp-sentinel / read+write-handle
locking (~L786-835) with the canonical primitive (sync surface). Preserve the
cold-install serialization semantics (POSIX dir-flock vs Windows sentinel) and
the `_HELD_LOCKS` reentrancy short-circuit. **Keep the #4703 fix**: the owner
lock is observed by lstat only (`read_content=False`) — never read the payload
under the held lock.

### T018 — bootstrap: migrate _flock
Replace `runtime/bootstrap.py`'s `_flock`/`_lock_file` (msvcrt blocking /
fcntl.LOCK_EX, L60-82) and the `.update.lock` acquisition (L166) with the
canonical sync primitive (`blocking=True`, a timeout). Route its OS check through
the seam. This runs before the event loop — use the SYNC facade, never
`asyncio.run()`.

### T019 — tracker/credentials + windows_migrate + pre_review_gate
- `tracker/credentials.py` (msvcrt/fcntl, L104-107): migrate; it locks the file it
  reads/writes — ensure the canonical primitive's sidecar model removes the
  latent #4703 shape.
- `paths/windows_migrate.py` (msvcrt, L198): migrate (Windows-only).
- `review/pre_review_gate.py`: migrate the scoped `fcntl` lock (L280) onto the
  **sync** surface (it deliberately hand-rolled sync because the old lock was
  async-only — the new sync facade is exactly its home). **Also route its
  `:260` `sys.platform=="win32"` advisory-skip branch** through
  `kernel.paths.is_windows` (post-tasks squad MF-3 — it is a routable branch, NOT
  the `import fcntl` guard; the import guard stays raw/allowlisted).

### T020 — Shrink gates + per-site parity tests
Shrink this WP's entries in the **per-WP exemption files** (post-tasks squad S-2):
`tests/architectural/_exemptions/lock-ban-wp04.txt` for the lock gate and the
matching OS-gate exemption — out-of-map edits on WP03/WP01's gate infrastructure,
one-line rationale each; do NOT touch WP05's exemption file. Leave both gates
green at this commit. Add focused migration tests:
`test_asset_preparation_lock_migration.py` (cold-install serialization + no
payload read under lock, via the parity harness),
`test_bootstrap_lock_migration.py` (blocking acquire + `.update.lock` no-self-read).

## Branch Strategy

Planning base and merge target: `feat/cross-os-primitive-unification`. Lane
worktree per `lanes.json`; sync the lane `.venv` (`uv sync --frozen --all-extras`)
since some tests shell out to `<worktree>/.venv/bin/python`.

## Definition of Done

- No raw `msvcrt`/`fcntl` in owned files; all route through `kernel/locks.py`.
- `asset_preparation.py`: safe-delete copy gone, FR-011 folded, `_HELD_LOCKS`
  migrated, #4703 read-safety preserved.
- Lock + OS gate allowlists shrunk for owned files; both green at the fold commit.
- Parity/migration tests green; `ruff`/format clean; complexity ≤15.

## Risks

- **Blocking-in-bootstrap**: never wrap the sync path in `asyncio.run()` (deadlock
  before the loop). Use the sync facade.
- **Cold-install semantics**: preserve POSIX-dir-flock vs Windows-sentinel; don't
  regress the #4703 fix (lstat-only observation).
- **tracker/credentials lock-the-payload shape**: the migration must not read the
  credential file while holding a mandatory lock over it.

## Reviewer guidance (reviewer-renata, opus)

Confirm: `_HELD_LOCKS` truly retired onto the primitive; no payload read under a
held lock at any migrated site (run the parity harness); bootstrap uses the sync
facade; gate allowlists shrank (diff shows removals, never additions); FR-011
folds present.
