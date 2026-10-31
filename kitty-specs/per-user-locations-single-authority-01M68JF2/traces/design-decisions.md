# Design decisions

- D1 The authority returns the full app directory; callers append only their own subpath,
  so the app name exists once (was: six literals).
- D2 `platformdirs` semantics with `appauthor=False`, matching `kernel.paths.get_kittify_home`
  and `specify_cli.paths.windows_paths`; avoids the doubled `spec-kitty\spec-kitty` segment.
- D3 The `Windows`/`MacOS`/`Unix` class is constructed explicitly from `kernel.paths.is_windows()`
  and `sys.platform`, because `platformdirs` binds its class at import time and this host is
  Linux; without this, the macOS branch could not be pinned at all (spec C-005).
- D4 macOS honours XDG variables (`XDGMixin`), so the pins cover both the `~/Library/...`
  default and the `$XDG_*` override.
- D5 The legacy discard skips any candidate that is current for *any* kind. On Linux the
  legacy state root and the current cache root are the same directory, so a naive discard
  would delete the live shared pack cache.
- D6 The discard is a fourth owner in `prepare_startup_assets`, not a side effect of the
  resolvers: resolution stays a pure environment read (NFR-002), and failures are already
  isolated there (#6473).
- D7 The two unreachable `ImportError` fallbacks are deleted rather than kept as a safety
  net: `platformdirs` is a hard dependency and the cache fallback encoded a third rule.
