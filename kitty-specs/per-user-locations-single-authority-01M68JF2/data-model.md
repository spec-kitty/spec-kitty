# Data model: per-user directory kinds, callers and legacy locations

This Mission moves no structured data. What it owns is a small, explicit model of *where*
per-user files live, and the invariants that keep those answers equal. Everything here is
derived from `research.md` (D1–D7) and the installed `platformdirs` 4.9.6.

## Entity: Per-user directory kind

| Field | Values | Notes |
|---|---|---|
| `kind` | `cache` \| `state` \| `config` | The three questions `kernel.user_dirs` answers. |
| `platformdirs_method` | `user_cache_dir` \| `user_state_dir` \| `user_config_dir` | Exactly one method per kind; the authority never re-implements a layout. |

### Resolved locations (app name `spec-kitty`, `appauthor=False`)

| Kind | Linux | macOS | Windows |
|---|---|---|---|
| cache | `$XDG_CACHE_HOME/spec-kitty`, else `~/.cache/spec-kitty` | `$XDG_CACHE_HOME/spec-kitty`, else `~/Library/Caches/spec-kitty` | `%LOCALAPPDATA%\spec-kitty\Cache` |
| state | `$XDG_STATE_HOME/spec-kitty`, else `~/.local/state/spec-kitty` | `$XDG_STATE_HOME/spec-kitty`, else `~/Library/Application Support/spec-kitty` | `%LOCALAPPDATA%\spec-kitty` |
| config | `$XDG_CONFIG_HOME/spec-kitty`, else `~/.config/spec-kitty` | `$XDG_CONFIG_HOME/spec-kitty`, else `~/Library/Application Support/spec-kitty` | `%LOCALAPPDATA%\spec-kitty` |

Rules: an empty variable counts as unset; a relative value is used as given; macOS honours
XDG variables through `platformdirs`' `XDGMixin`; state and config coincide on macOS and
Windows because that is what `platformdirs` documents for those platforms.

## Entity: Caller

A production function that needs one kind and appends exactly one subpath.

| Caller | Kind | Subpath it appends |
|---|---|---|
| `specify_cli.core.upgrade_notifier._default_cache_path` | cache | `upgrade-check.json` |
| `specify_cli.compat.cache._resolve_cache_dir` | cache | `upgrade-nag.json` |
| `charter.offering.packs.pack_fetch.default_cache_root` | cache | `open-packs` |
| `kernel.service_artifacts.default_cache_root` | cache | `services` |
| `runtime.next._runtime_pkg_notice._marker_path` | state | `.spec-kitty-runtime-cutover-notice-shown` |
| `specify_cli.compat.config._resolve_config_dir` | config | `upgrade.yaml` |

**Invariant C1 (convergence)**: for one faked platform and environment, every caller of a
given kind resolves under the same authority directory. A caller that composes its own
base, its own app segment or its own platform branch violates it.

**Invariant C2 (purity)**: resolving a kind reads environment variables only — no
directory creation, no file write, no network.

## Entity: Legacy location

A path a pre-fix rule wrote to. Disposable, and never migrated.

| Legacy root | Kind | Written by | Discarded when |
|---|---|---|---|
| `$XDG_CACHE_HOME/spec-kitty`, else `~/.cache/spec-kitty` | cache | `upgrade_notifier`, `pack_fetch`, `service_artifacts` | not the current directory of any kind |
| `%LOCALAPPDATA%\spec-kitty`, else `~/AppData/Local/spec-kitty` | cache | `upgrade_notifier` on Windows | not current for any kind |
| `%LOCALAPPDATA%\spec-kitty\spec-kitty` | cache | `compat.cache` on Windows (`platformdirs` default author segment) | not current for any kind |
| `$XDG_STATE_HOME/spec-kitty`, else `~/.cache/spec-kitty` | state | `runtime.next._runtime_pkg_notice` | not current for any kind |
| `$XDG_CONFIG_HOME/spec-kitty`, else `~/.config/spec-kitty` note: unchanged on Linux/macOS; Windows only | config | `compat.config` | not current for any kind |

**Invariant L1 (no live deletion)**: a candidate equal to the current cache, state or
config directory is never removed. On Linux this makes the legacy *state* candidate equal
to the current *cache* directory, so nothing is removed — deliberately.

**Invariant L2 (bounded)**: a candidate is removed only when it is one of the enumerated
roots, lies inside the per-user base it was derived from, is not a symlink, and no
directory between it and that base is a git checkout. `kernel.tree_removal.remove_tool_owned_tree`
enforces the last two.

**Invariant L3 (silent)**: a failed discard (permissions, race, unproven path) is logged at
debug level and never changes the process's exit code or stdout.

**Invariant L4 (once)**: the discard runs at most once per process, from the CLI startup
owners list, and is a no-op after the first attempt.

## State transitions

None. No entity has a lifecycle; the only transition is "a legacy root exists → it is
gone", which is idempotent and terminal.

## Validation rules

| ID | Rule | Requirement |
|---|---|---|
| V1 | Six callers, three kinds, every caller assigned to exactly one kind | FR-003 |
| V2 | Every caller's resolved path is under its kind's authority directory | FR-006 |
| V3 | A candidate is never removed when it equals any current directory | FR-010 |
| V4 | A symlinked or git-checkout candidate survives | FR-010 |
| V5 | Resolving creates nothing | NFR-002 |
| V6 | A discard failure leaves the exit code and stdout unchanged | NFR-003 |
