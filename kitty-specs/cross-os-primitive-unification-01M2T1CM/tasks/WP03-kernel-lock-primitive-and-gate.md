---
work_package_id: WP03
title: Canonical lock primitive in kernel + DIRECTIVE_043 gate + parity harness
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-010
- NFR-001
- NFR-002
planning_base_branch: feat/cross-os-primitive-unification
merge_target_branch: feat/cross-os-primitive-unification
branch_strategy: Planning artifacts for this mission were generated on feat/cross-os-primitive-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cross-os-primitive-unification unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 1 - Implementation
history:
- at: '2026-09-18T11:05:00Z'
  actor: system
  action: Prompt generated for cross-os-primitive-unification mission
agent_profile: python-pedro
authoritative_surface: src/kernel/locks.py
create_intent:
- src/kernel/locks.py
- tests/architectural/test_lock_primitive_ban.py
- tests/kernel/test_locks.py
- tests/kernel/test_lock_parity.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/kernel/locks.py
- src/specify_cli/core/file_lock.py
- src/specify_cli/auth/refresh_transaction.py
- src/specify_cli/auth/token_manager.py
- src/specify_cli/cli/commands/_auth_doctor.py
- src/specify_cli/lanes/auto_rebase.py
- pyproject.toml
- tests/architectural/conftest.py
- tests/architectural/test_lock_primitive_ban.py
- tests/kernel/test_locks.py
- tests/kernel/test_lock_parity.py
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

Home the canonical lock primitive at `kernel/locks.py` (C1) by **moving**
`MachineFileLock` from `specify_cli/core/file_lock.py`, extend it with a **sync**
surface + blocking/timeout + re-entrancy + a test-double seam, author the
non-vacuous DIRECTIVE_043 lock gate (seeded fail-closed with ALL current sites),
and build the cross-OS parity harness. This is the mission's core.

Read first: `../spec.md` (FR-006/007/010, NFR-001/002, C-001/004),
`../contracts/lock-primitive.md`, `../data-model.md` E-01/E-04,
`../research.md` R-01/R-03/R-05.

**Success**: `kernel/locks.py` owns all raw `msvcrt`/`fcntl`; the primitive can
never yield a payload handle; the gate is non-vacuous; the parity harness proves
read-safety under simulated Windows mandatory-lock semantics.

## Context

A-04 validated: `MachineFileLock`'s only non-stdlib import is `kernel.clock`, so
this is a **move, not a rewrite**. It is already sidecar-model and #4703-safe
(truncate-not-unlink on release; observes via `read_lock_record`). The move makes
`kernel.clock` intra-kernel. Adding an `asyncio`-bearing module to the zero-dep
kernel requires the layer fixtures to accept it (T011). Kernel is
zero-third-party-dep (C-001) — the primitive stays stdlib; **do not** add
`filelock`.

## Subtasks

### T010 — Create kernel/locks.py (move + extend)
Move the `MachineFileLock` core (`_LockCore`: open / `_os_lock` / `_os_unlock` /
`_atomic_write_under_lock` / truncate) into `kernel/locks.py`. Preserve the
async `MachineFileLock` facade verbatim in behaviour. Add:
- a **sync** facade (`SyncMachineFileLock` and/or a `machine_file_lock(...)`
  contextmanager) over the same `_LockCore`;
- `blocking: bool` + `timeout_s: float | None` (cover non-blocking-retry AND
  blocking-with-timeout — `filelock`/bootstrap need the latter);
- optional **re-entrancy** (thread-local) for `status/locking.py` (WP05);
- a supported **test-double injection seam** for `verdict_commit_queue.py` (WP05).
Both context managers yield a `LockRecord` (holder metadata) — **never** a handle
to the protected resource (FR-007). The primitive derives the sidecar path
(`resource.parent / f".{resource.name}.lock"`) itself.

### T011 — Kernel-surface architectural acceptance
Add `kernel/locks.py` to `pyproject.toml` `[tool.hatch.build.targets.wheel].packages`
if needed and to the `landscape` fixture (`tests/architectural/conftest.py`) so
`test_layer_rules.py` + `test_pyproject_shape.py` accept it. Run
`tests/architectural/` **targeted** (never the whole suite locally — it breaks
the session). Confirm the enforced chain `kernel <- … <- specify_cli` holds.

### T012 — Repoint consumers; shim/remove core/file_lock.py
Repoint existing `MachineFileLock` importers to `kernel.locks`:
`auth/refresh_transaction.py`, `auth/token_manager.py`, `cli/commands/_auth_doctor.py`,
`lanes/auto_rebase.py`. Make `core/file_lock.py` a thin re-export shim OR remove
it and update imports (prefer removal to avoid a second surface, per
canonical-source discipline). Route `file_lock.py`'s inline `sys.platform` check
through `kernel.paths.is_windows` (WP01) as part of the move; shrink its entry in
the OS gate allowlist (out-of-map edit on WP01's gate, with a one-line rationale).
Route `token_manager.py`'s OS check likewise.

### T013 — DIRECTIVE_043 lock gate
`tests/architectural/test_lock_primitive_ban.py`, modelled on
`test_clock_import_ban.py` + `test_clock_call_ban.py`:
- **Scan corpus = `src/` ONLY** (post-tasks squad MF-1): a deliberate divergence
  from the clock template's `SCAN_ROOTS=(src,tests,scripts)`. `tests/`/`scripts/`
  legitimately use raw `msvcrt`/`fcntl`/the concrete lock type — the parity
  harness (T014) and lock unit tests MUST exercise raw locking and can never
  route through `kernel/locks.py`. The gate bans re-forking in *production* code.
  Record the divergence + rationale in the gate docstring.
- **Import ban**: `import msvcrt`/`fcntl`/`filelock`, `from filelock import …`
  outside `kernel/locks.py`.
- **Call ban**: `msvcrt.locking(...)`, `fcntl.flock/lockf(...)`, `FileLock(...)`
  outside `kernel/locks.py`.
- **Concrete floor**: assert `kernel/locks.py` contains ≥1 `msvcrt.locking` and
  ≥1 `fcntl.flock` (deleting the door must fail).
- **Self-mutation**: synthetic violation must be flagged.
- **Predicate honours the holder (C-004)**: permit `kernel/locks.py`'s own raw
  calls + its legitimate sidecar-record read; the invariant is "no raw locking
  outside the holder" + "no reading a *payload* under a held lock", not a blunt
  "no read under lock".
- **Per-WP exemption files** (post-tasks squad S-2): use a plural-glob
  `tests/architectural/_exemptions/lock-ban-*.txt` (mirroring the clock gate) so
  WP04 and WP05 shrink their **own** file — no rebase collision between the two
  parallel migration WPs.
- **Shrink-only allowlist**, seeded fail-closed with EVERY current `src/` site
  (asset_preparation, bootstrap, tracker/credentials, windows_migrate,
  pre_review_gate, checkout_file_lock, status/locking, verdict_commit_queue,
  auth file_fallback, zeitgeist_client credentials+outbox_approval). **Exclude
  `src/specify_cli/upgrade/migrations/`** (C-002). WP04/WP05 shrink their entries.

### T014 — Cross-OS parity harness (SC-004)
`tests/kernel/test_lock_parity.py`. **The PRIMARY proof is STRUCTURAL** (post-tasks
squad N-2, FR-007/G2): assert the API surface yields only a `LockRecord` and that
**no code path exists to read the protected payload through a held lock** — a
runtime "acquire, read, assert no error" test is VACUOUS on advisory POSIX (the
holder can read its own flock'd file — exactly why #4703 shipped). Then, as
secondary runtime proofs: simulate Windows mandatory-lock semantics on POSIX (the
#4703 signature — a process reading a path it holds a mandatory lock over raises
`PermissionError`); cross-process contention (subprocess) and blocking-with-timeout
behave correctly; release truncates (inode stable).

## Branch Strategy

Planning base and merge target: `feat/cross-os-primitive-unification`. Lane
worktree per `lanes.json`; **this WP's tests shell out to `<worktree>/.venv/bin/python`**
in some suites — the lane needs its own synced `.venv` (`uv sync --frozen --all-extras`).

## Definition of Done

- `kernel/locks.py` present; sync+async; yields only `LockRecord`.
- Layer/pyproject-shape tests accept it; chain intact.
- Consumers repointed; `core/file_lock.py` shimmed/removed.
- Lock gate non-vacuous, seeded fail-closed; parity harness green.
- `ruff`/format clean; complexity ≤15; new branches tested.

## Risks

- **Async→sync**: `pre_review_gate` (WP04) needs the SYNC surface because it runs
  outside an event loop; bootstrap runs before the loop. Get the sync facade
  right here or WP04 strands.
- **Kernel arch acceptance**: run `tests/architectural/` targeted, not whole.
  T011 edits `tests/architectural/conftest.py` (the landscape fixture) — a
  **cross-cutting** change that per CLAUDE.md needs the FULL `tests/architectural/`
  suite, which must NOT run locally (breaks the session). **NFR-002 is therefore
  CI-certified, not self-certified — flag this explicitly in the PR body** (post-tasks squad N-4).
- **Complexity ≤15 (NFR-006)**: the acquire logic multiplies
  non-blocking-retry × blocking-with-timeout × reentrant × sync/async × win/posix.
  Extract a per-mode helper set (one small function per axis) so no single
  function exceeds C901/S3776=15. If T013 (gate) + T014 (parity) push the WP over
  ~10 subtasks or 700 lines during implement, split them into a follow-on WP
  rather than packing them in.

## Reviewer guidance (reviewer-renata, opus)

Confirm: no API path yields a payload handle; the sidecar path is derived
internally; the gate floor + self-mutation genuinely fail when broken; the
predicate does not flag the holder's own record read; the parity harness models
the mandatory-lock refusal, not just advisory POSIX behaviour.
