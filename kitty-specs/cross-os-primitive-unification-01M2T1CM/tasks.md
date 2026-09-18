# Tasks — Cross-OS Primitive Unification (#4714)

**Mission**: `cross-os-primitive-unification-01M2T1CM` | **Branch**: `feat/cross-os-primitive-unification`
**Planning base / merge target**: `feat/cross-os-primitive-unification` (PR then targets `skupstream/main`)

Completion is event-sourced: record subtask completion with
`spec-kitty agent tasks mark-status Txxx --status done`. The rows below are
reference rows, not checkboxes.

## Subtask Index (reference)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Promote `kernel/paths.py::_is_windows` → public patchable `is_windows()` | WP01 | |
| T002 | Route `runtime/home.py` + OS-detection "pure zoo" (cluster 1) through the seam | WP01 | [P] |
| T003 | Route OS-detection "pure zoo" (cluster 2) through the seam | WP01 | [P] |
| T004 | Author non-vacuous `test_os_detection_ban.py` (floor + self-mutation + import-guard allowlist), seeded fail-closed | WP01 | |
| T005 | Unit tests: seam patchable without faking `os.name`; routed consumers honour override | WP01 | |
| T006 | Create `specify_cli/core/safe_delete.py` (lstat+S_IMODE force_writable, safe_unlink/rmdir/rmtree + onerror shim) | WP02 | |
| T007 | Route `skills/installer.py` onto the util; delete its copy | WP02 | |
| T008 | Route `runtime/agent_skills.py` onto the util; delete its copy | WP02 | |
| T009 | Tests: SC-006 symlink-negative proof + read-only file/dir delete both semantics + focused coverage | WP02 | |
| T010 | Create `kernel/locks.py` — move `MachineFileLock` core + add sync facade, `blocking`/`timeout_s`, reentrancy, test-double seam | WP03 | |
| T011 | Accept `kernel/locks.py` in `pyproject.toml` wheel packages + `tests/architectural/` landscape/layer rules | WP03 | |
| T012 | Repoint existing `MachineFileLock` consumers; make `core/file_lock.py` a shim (or remove) + route its inline OS check | WP03 | |
| T013 | Author non-vacuous `test_lock_primitive_ban.py` (import+call ban, floor, self-mutation, shrink-only allowlist seeded with ALL sites, excl. migrations) | WP03 | |
| T014 | Cross-OS parity harness: simulate Windows mandatory-lock semantics on POSIX (SC-004) | WP03 | |
| T015 | `asset_preparation.py`: remove safe-delete copy (route onto util) + route OS check | WP04 | |
| T016 | `asset_preparation.py`: fold FR-011 (anchor-path sha256 normalization + `_children_tolerated` defensive read guard) | WP04 | |
| T017 | `asset_preparation.py`: migrate `_HELD_LOCKS` cold-install locking onto `kernel/locks.py` (the #4703-origin site) | WP04 | |
| T018 | Migrate `runtime/bootstrap.py` `_flock` onto the canonical primitive | WP04 | |
| T019 | Migrate `tracker/credentials.py`, `paths/windows_migrate.py`, `review/pre_review_gate.py` (sync surface) | WP04 | |
| T020 | Shrink lock + OS gates for WP04's files; per-site parity tests | WP04 | |
| T021 | Migrate `core/checkout_file_lock.py` onto the canonical primitive | WP05 | [P] |
| T022 | Migrate `status/locking.py` (preserve thread-local re-entrancy) | WP05 | [P] |
| T023 | Migrate `review/verdict_commit_queue.py` (preserve test-double contract) | WP05 | [P] |
| T024 | Migrate `auth/secure_storage/file_fallback.py` (blocking timeout=10) | WP05 | [P] |
| T025 | Migrate `zeitgeist_client/credentials.py` + `outbox_approval.py` (local client code) | WP05 | [P] |
| T026 | Remove `filelock` from `pyproject.toml`; shrink lock gate to empty (or deferral-seam state); cross-process parity tests | WP05 | |

## Work Packages

### WP01 — OS-detection kernel seam + ban gate (Wave A, tidy-first)

- **Goal**: One canonical, patchable `is_windows()` seam in kernel; route the
  routable OS-detection zoo through it; a non-vacuous gate bans inline
  `os.name=="nt"`/`sys.platform=="win32"` outside the seam.
- **Priority**: High (tidy-first enabler; de-noises `file_lock.py` before WP03 moves it)
- **Independent test**: patch `kernel.paths.is_windows` and observe routed consumers follow, with no test faking `os.name`; the gate fails on a synthetic inline check.
- **Subtasks**: T001, T002, T003, T004, T005
- **Dependencies**: none
- **Requirements**: FR-004, FR-005, FR-012 (SC-002)
- **Est. size**: ~300 lines

### WP02 — Canonical safe-delete util (Wave A, tidy-first)

- **Goal**: One `specify_cli/core/safe_delete.py` with the no-follow (`lstat`) +
  masked (`S_IMODE`) contract; consolidate the `installer.py` and
  `agent_skills.py` copies (the `asset_preparation.py` copy is removed in WP04
  where the file gets its full treatment).
- **Priority**: High (tidy-first; parallel to WP01)
- **Independent test**: delete a managed symlink whose target is outside the managed tree → target untouched (SC-006); read-only file/dir delete on both OS semantics.
- **Subtasks**: T006, T007, T008, T009
- **Dependencies**: none
- **Requirements**: FR-001, FR-002, FR-003 (partial) (SC-001, SC-006)
- **Est. size**: ~280 lines

### WP03 — Canonical lock primitive in kernel + ban gate + parity harness (Wave B)

- **Goal**: `kernel/locks.py` — sync+async sidecar-model lock (moved from
  `MachineFileLock`), structurally read-safe; a non-vacuous DIRECTIVE_043 lock
  gate seeded fail-closed with all sites; the cross-OS parity harness.
- **Priority**: High (the core deliverable)
- **Independent test**: the gate fails when `kernel/locks.py` is emptied and on a synthetic violation; the parity harness shows no site reads a payload while holding a lock over it.
- **Subtasks**: T010, T011, T012, T013, T014
- **Dependencies**: WP01
- **Requirements**: FR-006, FR-007, FR-010, NFR-001 (partial), NFR-002 (SC-004)
- **Est. size**: ~450 lines

### WP04 — Migrate stdlib-family lock sites incl. the #4703-origin (Wave C)

- **Goal**: Migrate the raw `msvcrt`/`fcntl` sites onto the canonical primitive —
  `asset_preparation.py`'s `_HELD_LOCKS` (the #4703-origin), `bootstrap.py`,
  `tracker/credentials.py`, `windows_migrate.py`, `pre_review_gate.py` — and give
  `asset_preparation.py` its full treatment (safe-delete copy removal + FR-011).
- **Priority**: High
- **Independent test**: each migrated site passes the parity harness; the lock+OS gate allowlists shrink for these files.
- **Subtasks**: T015, T016, T017, T018, T019, T020
- **Dependencies**: WP02, WP03
- **Requirements**: FR-003 (asset_preparation copy), FR-008, FR-011 (SC-003)
- **Est. size**: ~480 lines

### WP05 — Migrate filelock-family + retire `filelock` (Wave C; deferral seam)

- **Goal**: Migrate the 6 `filelock` sites onto the canonical primitive
  (preserving re-entrancy, timeout, and the verdict-queue test double), remove
  `filelock` from `pyproject.toml`, shrink the lock gate toward empty. If
  cross-process parity cannot be proven in-mission, take the A-01 deferral seam
  (leave filelock sites in the ratchet + a tracked follow-up).
- **Priority**: High (highest risk)
- **Independent test**: cross-process contention + blocking-timeout parity; `filelock` absent from runtime deps; re-entrancy + test-double preserved.
- **Subtasks**: T021, T022, T023, T024, T025, T026
- **Dependencies**: WP03
- **Requirements**: FR-009, NFR-001 (SC-003, SC-005)
- **Est. size**: ~450 lines

## Dependency graph

```
WP01 ─┐
      ├─> WP03 ─┬─> WP04
WP02 ─┘         └─> WP05
```

## MVP / sequencing note

Wave A (WP01, WP02) is independently valuable tidy-first work. WP03 is the core.
WP04/WP05 are the migration waves; WP05 carries the deferral seam. The lock gate
(authored in WP03, seeded fail-closed) is the coordination artifact — each
migration WP shrinks its own allowlist entry and leaves the gate green at its
fold commit.
