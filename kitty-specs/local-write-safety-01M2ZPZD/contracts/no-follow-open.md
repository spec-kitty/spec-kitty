# Contract: canonical no-follow module (`kernel.no_follow`)

**Layer**: `src/kernel/` (so `kernel.locks` may consume it without violating `kernel ↛ specify_cli`).

## Module hoist (whole module, not just the open primitive)
The existing `src/specify_cli/core/no_follow.py` is **hoisted in full** to `src/kernel/no_follow.py`.
`specify_cli.core.no_follow` becomes a thin re-export (`from kernel.no_follow import *`) with an
`__all__` **identical to today's**, so all existing importers need zero edits.

**Full preserved public API** (all six symbols; identity preserved):
`NoFollowPathError`, `chmod_fd`, `fd_relative_dir_ops_supported`, `open_no_follow`,
`read_text_no_follow`, `write_text_no_follow`.

- `NoFollowPathError` must remain a **single class object** re-exported (not redefined), so
  `except NoFollowPathError` at `specify_cli/git_common/gitignore_manager.py:18` (and peers) still catches.
- `open_no_follow(path, flags, mode=0o666)` keeps its **exact signature**.

## Behavior (`open_no_follow`)
- Adds `O_NOFOLLOW` (POSIX) to the flags; a symlink at the final component raises `ELOOP` →
  surfaced as `NoFollowPathError` (does not follow, does not truncate, does not exit-0).
- Windows: `O_NOFOLLOW` resolves to `0` (`getattr(os, "O_NOFOLLOW", 0)`) — degrades to current
  semantics; documented residual risk (NFR-001 POSIX-scoped).
- Does **not** add `O_EXCL` by default (fresh-create callers, e.g. credential temp writes, pass it
  explicitly; the shared lock does not — C-003).

## Consumers routed through this primitive (the 4 defect write-sites + the lock)
`kernel.locks._LockCore.open_fd`, `kernel.locks.force_release`, `zeitgeist_client/credentials.py`,
`tracker/credentials.py`, `migration/mission_state.py` (its lock), `runtime/next/_tmp_namespace.py`,
`runtime/asset_preparation.py` (sentinel). **Scope note**: this mission routes the lock + these
defect sites through the canonical helper. The ~7 *already-correct* pre-existing hand-rolled
`O_NOFOLLOW` sites elsewhere are NOT in scope (see spec Non-Goals / research D1 census).

## Acceptance
- A planted symlink at the target path leaves the pointed-at file's bytes unchanged AND the call
  raises `NoFollowPathError` (never exit-0). Tested per consumer path (SC-001), isolated HOME.
- **Repoint blast radius**: WP01 acceptance runs the **11 `specify_cli.core.no_follow` importers**
  (coordination/atomic_write, git_common/gitignore_manager, intake/brief_writer,
  session_presence/writers/markdown_rules, skills/{command_installer,installer,manifest_store},
  tool_surface/{bundles/projection, providers/agent_profiles, providers/session_presence},
  upgrade/migrations/m_3_2_8) **in addition to** the 13 `kernel.locks` consumers.
- `tests/architectural/test_layer_rules.py` and `test_lock_primitive_ban.py` stay green.
