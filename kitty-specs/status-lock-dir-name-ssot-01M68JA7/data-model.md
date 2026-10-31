# Data Model — status-lock directory name single-source

This mission introduces no stored data, no schema and no wire format. The model
below records the three path concepts the diff touches and the invariants that
keep them from collapsing into each other.

## Entities

### Runtime-state directory name

| Field | Value |
| --- | --- |
| Owner | `src/specify_cli/paths/windows_paths.py` (`RUNTIME_STATE_DIR_NAME`) |
| Type | `str` (a single path segment) |
| Value | `".spec-kitty"` |
| Derived by | `get_runtime_root()` on POSIX and on the Windows platformdirs-failure branch (`Path.home() / RUNTIME_STATE_DIR_NAME`) |

**Validation rules**: a bare segment — no separator, no `~`, no trailing slash.
It is a *name*, not a path; callers attach it to a base they already resolved.

### Repository-local runtime directory

| Field | Value |
| --- | --- |
| Derived by | `<repo_root> / RUNTIME_STATE_DIR_NAME` |
| Consumers | `status/locking.py` non-git lock fallback; `review/lock.py` worktree review lock |
| Purpose | Hold ephemeral, repository-scoped runtime state (lock files) without minting a project or repository marker |

**Invariants**:

1. It is **not** the user-global runtime root. `SPEC_KITTY_HOME` does not move
   it, and it never lives outside the tree it locks (C-001).
2. Creating it must not make the tree look like a project (`locate_project_root`
   walks up for `.kittify`) or a repository (`resolve_canonical_root` walks up
   for `.git`) — the #6367 guarantee, pinned by
   `tests/status/test_lock_fallback_never_mints_marker.py`.
3. The directory name is the same string as the runtime-state directory name by
   design (a reviewer of either lock finds state in the same recognisable
   directory), which is exactly why it is taken from the owner rather than
   re-typed.

### User-global runtime root

| Field | Value |
| --- | --- |
| Derived by | `specify_cli.paths.get_runtime_root().base` (Windows/POSIX aware, `SPEC_KITTY_HOME` first) |
| Consumer in this mission | indirectly, via the shared name constant — the value is unchanged |
| Invariant | resolution is pure (creates no directory) and the kernel-floor mirror `kernel.paths.get_runtime_state_root()` resolves identically (`tests/kernel/test_runtime_root_resolver_parity.py`) |

## State transitions

None. The change is a static re-pointing of one string; no lock lifecycle step,
no event, and no persisted state changes shape. Lock files keep their names
(`<key>.status.lock`, `review-lock.json`) and their directories.

## Invariants the diff must preserve (test-visible)

| Invariant | Pin |
| --- | --- |
| Bare non-git tree locks under `<root>/.spec-kitty/spec-kitty-locks/` | `tests/status/test_lock_fallback_never_mints_marker.py::test_bare_tree_locks_under_a_non_marker_home` |
| An existing `.kittify` keeps the historical `.kittify` lock location | same file, `test_existing_kittify_keeps_its_lock_location` |
| An existing `.git` dir keeps the historical `.git` lock location | same file, `test_existing_dot_git_dir_keeps_its_lock_location` |
| The review lock still lives at `<worktree>/.spec-kitty/review-lock.json` | `tests/specify_cli/test_audit_tail_readers.py`, `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py` |
| No new hand-rolled `.spec-kitty` literal outside the sanctioned owners | `tests/audit/test_no_legacy_path_literals.py` |
