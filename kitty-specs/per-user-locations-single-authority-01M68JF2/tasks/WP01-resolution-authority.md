---
work_package_id: WP01
title: The resolution authority
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-008
- NFR-001
- NFR-002
- SC-002
planning_base_branch: issue-6488-per-user-locations-single-authority
merge_target_branch: issue-6488-per-user-locations-single-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6488-per-user-locations-single-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6488-per-user-locations-single-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-per-user-locations-single-authority-01M68JF2
base_commit: 378009ad6a8c15cecef035cf0513981562404dc6
created_at: '2026-10-31T08:55:58.655810+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Authority
history:
- timestamp: '2026-10-31T08:55:00Z'
  agent: python-pedro
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/kernel/
create_intent: []
execution_mode: code_change
owned_files:
- src/kernel/user_dirs.py
- tests/architectural/**
- tests/kernel/_user_dirs_pins.py
- tests/kernel/test_user_dirs.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – The resolution authority

## Objective

Make `src/kernel/user_dirs.py` the single authority for per-user **cache**, **state** and
**config** directories, implementing `platformdirs` semantics (operator ruling on #6488)
with an explicitly selected platform class.

Read first: `research.md` in this Mission's directory
decisions D1–D4 and `data-model.md` ("Resolved locations"), then the current
`src/kernel/user_dirs.py`.

## What changes

- The module answers three questions — `user_cache_dir()`, `user_state_dir()`,
  `user_config_dir()` — and each returns the **full app directory** (`.../spec-kitty`), not
  a base directory. Callers in WP02 append only their own subpath.
- The `platformdirs` class is constructed **explicitly**: `platformdirs.windows.Windows`
  when `kernel.paths.is_windows()`, `platformdirs.macos.MacOS` when
  `sys.platform == "darwin"`, else `platformdirs.unix.Unix`. `platformdirs` binds its own
  class at import time, so relying on the module-level functions would make the macOS and
  Windows branches untestable on this Linux host.
- Constructor arguments: `appname="spec-kitty"`, `appauthor=False`, `ensure_exists=False`,
  defaults elsewhere. `appauthor=False` matches `kernel.paths.get_kittify_home()` and
  `specify_cli.paths.windows_paths()`; without it Windows gets the doubled
  `%LOCALAPPDATA%\spec-kitty\spec-kitty\Cache`.
- The `windows_local_appdata` keyword and the `~/.cache` state fallback are **deleted**.
  No caller may opt out of the platform rule any more (FR-008).
- The module docstring states the rule per platform and names `platformdirs` as the
  authority it delegates to. It must not claim a behaviour the code does not have (that is
  exactly the defect in `_runtime_pkg_notice` that WP02 fixes).

## Red-first

`tests/kernel/test_user_dirs.py` is rewritten as the branch pins **before** the module
changes and must be red against the pre-fix helper (the helper cannot produce
`~/Library/Caches/spec-kitty` on faked macOS). Keep `pytest.mark.unit` + `pytest.mark.fast`.

Cover, with one test per branch and a stable failure message naming the platform and env:

| platform | env | expected |
|---|---|---|
| linux, darwin | `XDG_CACHE_HOME` set | `$XDG_CACHE_HOME/spec-kitty` |
| linux, darwin | no XDG | `~/.cache/spec-kitty` (linux) / `~/Library/Caches/spec-kitty` (darwin) |
| linux, darwin | `XDG_STATE_HOME` set | `$XDG_STATE_HOME/spec-kitty` |
| linux | no XDG state | `~/.local/state/spec-kitty` |
| darwin | no XDG state | `~/Library/Application Support/spec-kitty` |
| linux, darwin | `XDG_CONFIG_HOME` set | `$XDG_CONFIG_HOME/spec-kitty` |
| linux | no XDG config | `~/.config/spec-kitty` |
| windows | `LOCALAPPDATA` set | cache `%LOCALAPPDATA%\spec-kitty\Cache`; state and config `%LOCALAPPDATA%\spec-kitty` |
| windows | `LOCALAPPDATA` empty/unset | `~/AppData/Local/...` (platformdirs' documented fallback) |

Also pin: an **empty** variable counts as unset; a **relative** XDG value is used as given;
the app name is `spec-kitty` with **no** doubled author segment on Windows.

## Fixture work (T003)

`s/kernel/_user_dirs_pins.py` fakes one platform and one environment. Extend it (do not
rewrite the seam it already provides) so it also clears `XDG_CONFIG_HOME`, `APPDATA`,
`LOCALAPPDATA` and any `WIN_PD_OVERRIDE_*` variable, and sets `USERPROFILE`/`HOME` into a
temporary home. The `platformdirs` Windows class reads `LOCALAPPDATA`/`APPDATA` off
`win32`, so this fixture is what makes the Windows pins meaningful on Linux.

## Purity (T004)

Add the pin that resolving any kind into a non-existent temporary base **creates nothing**
(`NFR-002`), and assert `kernel.user_dirs` imports no `charter`/`specify_cli` module by
importing it in a subprocess with those packages blocked, or by the existing architectural
gate — do not add a new allowlist entry.

## Validation

```bash
uv run pytest tests/kernel/test_user_dirs.py -q
uv run pytest tests/architectural -q -k "kernel or import"   # named gates only
uv run ruff check src/kernel/user_dirs.py tests/kernel/test_user_dirs.py tests/kernel/_user_dirs_pins.py
uv run mypy src/kernel/user_dirs.py
```

## Definition of done

- Three resolvers, explicit platform class, no `windows_local_appdata`, no `~/.cache`
  state fallback, truthful docstring.
- Branch pins red first, then green, covering every row of the table above.
- Purity pin green; no architectural allowlist change; ruff and mypy clean on touched files.
