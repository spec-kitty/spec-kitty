# Discovery: one authority for per-user cache and state locations (#6488)

Recorded 2026-10-31 on `main` at `35318ef51c`, before the spec was authored. Everything
below is either read from the tree or reproduced from the installed dependency; where a
claim rests on a platform this host is not, it says so.

## Decision D1 — the authority is `kernel.user_dirs`, and it returns the full app directory

`kernel/user_dirs.py` (added by #6481) already owns the resolution, but it returns a
*base* directory and every caller appends the literal `"spec-kitty"` again. That is the
seam the divergence grew in: the app name and the platform rule are two facts, and each
caller re-stated one of them.

Decision: the helper returns the app directory (`<base>/spec-kitty`-shaped, via
`platformdirs`' `appname`), and callers append only their own subpath. Consequences:

- the app name appears once, in `kernel/user_dirs.py`;
- six `"spec-kitty"` literals disappear from the six callers;
- `Path` equality between callers becomes directly testable, which is what FR-006 needs.

## Decision D2 — `platformdirs` semantics with `appauthor=False`

Operator triage (issue comment, 2026-10-19) settles the rule: `platformdirs` semantics
win for cache and state. The remaining question was the Windows author segment, because
`platformdirs.user_cache_dir("spec-kitty")` with the default `appauthor=None` produces
`%LOCALAPPDATA%\spec-kitty\spec-kitty\Cache` (the doubled name the issue's table quotes).

Decision: `appauthor=False`, i.e. `%LOCALAPPDATA%\spec-kitty\Cache`. Reasons:

- `kernel.paths.get_kittify_home()` and `specify_cli.paths.windows_paths` already call
  `platformdirs.user_data_dir("spec-kitty", appauthor=False, roaming=False)`; the repo
  has one established Windows convention and the cache should not invent a second;
- the doubled segment carries no information (`appauthor` exists for `<Vendor>\<App>`);
- it keeps the Windows cache one level deep, which the issue's own comparison table
  treats as the expected shape.

This is a deliberate, documented narrowing of "platformdirs defaults", not a divergence:
the platform *rule* (which base, which opinionated subdirectory) is platformdirs', and
only the vendor segment is pinned off, consistently, in one place.

## Decision D3 — the platform class is selected explicitly, not by `platformdirs` import

`platformdirs/__init__.py` binds `PlatformDirs = _Result` at **import time** from
`sys.platform` (`win32` → `Windows`, `darwin` → `MacOS`, else `Unix`). A Linux host can
therefore never exercise the macOS branch through the module-level functions, and this
host is Linux (C-005).

Decision: `kernel.user_dirs` builds the class itself — `platformdirs.windows.Windows`,
`platformdirs.macos.MacOS`, `platformdirs.unix.Unix` — chosen from
`kernel.paths.is_windows()` (the existing seam the tests already monkeypatch) and
`sys.platform == "darwin"`. That makes FR-005 possible on this host and keeps the
Windows seam identical to the one `tests/kernel/_user_dirs_pins.py` fakes today.

Verified from the installed `platformdirs` 4.9.6 (`.venv/lib/python3.11/site-packages/platformdirs/`):

| Class | `user_cache_dir` | `user_state_dir` | `user_config_dir` |
|---|---|---|---|
| `Windows` | `%LOCALAPPDATA%\<app>\Cache` | `%LOCALAPPDATA%\<app>` | `%LOCALAPPDATA%\<app>` |
| `MacOS` (`XDGMixin` + defaults) | `$XDG_CACHE_HOME/<app>` else `~/Library/Caches/<app>` | `$XDG_STATE_HOME/<app>` else `~/Library/Application Support/<app>` | `$XDG_CONFIG_HOME/<app>` else `~/Library/Application Support/<app>` |
| `Unix` (`XDGMixin` + defaults) | `$XDG_CACHE_HOME/<app>` else `~/.cache/<app>` | `$XDG_STATE_HOME/<app>` else `~/.local/state/<app>` | `$XDG_CONFIG_HOME/<app>` else `~/.config/<app>` |

Two facts that matter and are easy to get wrong:

1. **macOS honours XDG variables** (`XDGMixin`), so "platformdirs semantics" does *not*
   mean "always `~/Library/...` on macOS"; an XDG variable wins there too. FR-005 pins
   both halves.
2. **`Windows` works on a Linux host** as long as `LOCALAPPDATA`/`APPDATA`/`USERPROFILE`
   are set: `platformdirs.windows._pick_get_win_folder()` falls back to the environment
   variables off `win32` (`WIN_PD_OVERRIDE_*` first, which the tests can use). So the
   Windows branch is pinnable here as well.

## Decision D4 — what actually moves, per platform

| Kind | Linux before → after | macOS before → after | Windows before → after |
|---|---|---|---|
| cache | `$XDG_CACHE_HOME`/`~/.cache` + `spec-kitty` → **unchanged** | `~/.cache/spec-kitty` → `~/Library/Caches/spec-kitty` | `%LOCALAPPDATA%\spec-kitty` (3 callers) / `%LOCALAPPDATA%\spec-kitty\spec-kitty\Cache` (nag) → `%LOCALAPPDATA%\spec-kitty\Cache` |
| state | `$XDG_STATE_HOME`/`~/.cache` + `spec-kitty` → `$XDG_STATE_HOME`/`~/.local/state` + `spec-kitty` | `~/.cache/spec-kitty` → `~/Library/Application Support/spec-kitty` | `~/.cache/spec-kitty` → `%LOCALAPPDATA%\spec-kitty` |
| config | `$XDG_CONFIG_HOME`/`~/.config` + `spec-kitty` → **unchanged** | **unchanged** (`platformdirs` already) | `%LOCALAPPDATA%\spec-kitty\spec-kitty` → `%LOCALAPPDATA%\spec-kitty` |

So on Linux nothing moves but the one-time marker; on macOS the cache and marker move.

## Decision D5 — legacy cleanup must skip any path that is current for any kind

The pre-fix **state** rule (`$XDG_STATE_HOME` else literal `~/.cache`, then `spec-kitty`)
and the post-fix **cache** rule on Linux are the *same directory*:
`~/.cache/spec-kitty`. A naive "delete the old state root" step would therefore delete the
live pack cache, the live service cache and the live upgrade-check cache on every Linux
machine — a data-loss bug, and specifically a hazard on this shared build host, where
`~/.cache/spec-kitty/open-packs/<sha>/` is a cache twenty agents share
(`/home/exedev/work/MISSION-BRIEF.md`, "Shared machine state").

Decision: cleanup computes the legacy roots from the **old** rules, then removes a
candidate only when it is not the current cache, state or config directory. On Linux that
makes the whole step a no-op (which is also why CI cannot lose a cache to it), and on
macOS/Windows it removes the orphaned trees.

Removal reuses `kernel.tree_removal.remove_tool_owned_tree(path, tool_root=<base>,
best_effort=True)`, which already proves the path lies inside the named root and refuses
to delete through a git checkout. Two extra guards: skip a candidate that is a symlink
(resolution may land outside the base; `remove_tool_owned_tree` would raise) and never
delete the home directory or a base itself.

## Decision D6 — cleanup runs once per process at the CLI startup seam

Placement options considered:

1. inside `user_cache_dir()`/`user_state_dir()` — impure getter, called on hot paths,
   including from scripts that never touch the CLI;
2. a dedicated `spec-kitty` subcommand — new surface, and users will not run it;
3. the existing startup housekeeping seam, `prepare_startup_assets(owners)` in
   `src/specify_cli/__init__.py`, which already isolates per-owner failures (#6473).

Decision: (3), as a fourth owner. It runs on every normal CLI invocation, is already
failure-isolated, and keeps the resolvers pure (NFR-002). Scripts and the hatch build hook
that resolve a cache without the CLI simply keep an orphaned directory; the changelog
says so.

## Decision D7 — the two `ImportError` fallbacks are deleted, not kept as a safety net

`platformdirs>=4.9.2` is a hard dependency (`pyproject.toml`), so
`specify_cli/compat/cache.py:489-508` and `specify_cli/compat/config.py:101-114` carry
fallbacks that cannot execute, and the cache one encodes a *third* Windows rule
(`%LOCALAPPDATA%\spec-kitty\Cache`, one level shallower than what the import path
produces). Deleting both is the point of the issue ("Remove the `platformdirs` fallbacks
that can never run"), and it removes the only remaining second implementation.

## Evidence

- `src/kernel/user_dirs.py` — the #6481 helper, its docstring, and the
  `windows_local_appdata` opt-out that FR-008 removes.
- `src/specify_cli/core/upgrade_notifier.py:74` (`/ "spec-kitty" / ...`),
  `src/charter/offering/packs/pack_fetch.py:73`,
  `src/kernel/service_artifacts.py:80` — the three XDG-rule cache callers.
- `src/specify_cli/compat/cache.py:489-508`, `src/specify_cli/compat/config.py:101-114` —
  the two `platformdirs` callers and their dead fallbacks.
- `src/runtime/next/_runtime_pkg_notice.py:44-52` — the state caller whose docstring says
  `platformdirs` and whose code calls the kernel helper.
- `tests/kernel/_user_dirs_pins.py`, `tests/kernel/test_user_dirs.py`,
  `tests/core/test_upgrade_probe_and_notifier.py:552`,
  `tests/charter_offering/test_pack_fetch_cache_root.py`,
  `tests/next/test_runtime_pkg_notice_unit.py:133` — the five tests that currently pin
  the *old* per-caller locations and must be rewritten, not appended to.
- `git log -S"user_dirs"` → `e390ace319` (#6481 introduced the helper),
  `1cb30d8add` (its pre-PR fold), `44ccd1311b` (#6590 added the fourth caller).
  `gh pr list --search 6488` → only PR #6490 (#6481, merged); nothing else has touched
  the question since, so the issue is neither superseded nor part-done.
- `platformdirs` 4.9.6 sources as quoted under D3; `pyproject.toml:63` pins
  `platformdirs>=4.9.2`.

## Open questions (resolved before tasks)

- **Q1 — does the state move belong to this Mission?** Yes: the operator's ruling names
  state, and `_runtime_pkg_notice` is the only state caller. It also drags in D5, which is
  why cleanup is a requirement and not a footnote.
- **Q2 — is `compat/config.py` in scope?** Yes for the dead fallback (the operator names
  it) and for routing through the authority, because leaving one direct `platformdirs`
  call is exactly the "second source of truth" the issue is about. Its *Linux and macOS*
  paths do not change.
- **Q3 — does anything read these paths by string?** Checked: the docs name
  `~/.cache/spec-kitty/...` in `docs/development/how-to/sync-packs.md`,
  `docs/development/how-to/service-pins.md` and
  `docs/guides/how-to/installation/install-and-upgrade.md`; both ADRs that mention them
  are historical records and stay untouched. No code parses a cache path from a string.
- **Q4 — is there a `platformdirs`-free consumer that would break?** No: every caller is
  in-process Python, and `platformdirs` ships in the wheel.
