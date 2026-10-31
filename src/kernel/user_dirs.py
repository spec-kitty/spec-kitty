"""Per-user cache, state and config directories -- the one authority (#6488).

``platformdirs`` semantics win for every kind of per-user directory (operator
triage on #6488, 2026-10-19). This module is the only place in the codebase that
turns a platform and an environment into such a path; every caller resolves
through :func:`user_cache_dir`, :func:`user_state_dir` or :func:`user_config_dir`
and appends only its own subpath. Before #6488 each caller carried a copy of the
rule and they disagreed, so on macOS the upgrade, pack and service caches landed
in ``~/.cache/spec-kitty`` while the upgrade-nag cache landed in
``~/Library/Caches/spec-kitty``.

The resolved directories (app name ``spec-kitty``, ``appauthor=False``):

* cache -- ``$XDG_CACHE_HOME/spec-kitty`` (else ``~/.cache/spec-kitty``) on
  Linux; ``$XDG_CACHE_HOME/spec-kitty`` (else ``~/Library/Caches/spec-kitty``)
  on macOS; ``%LOCALAPPDATA%\\spec-kitty\\Cache`` on Windows.
* state -- ``$XDG_STATE_HOME/spec-kitty`` (else ``~/.local/state/spec-kitty``)
  on Linux; ``$XDG_STATE_HOME/spec-kitty`` (else
  ``~/Library/Application Support/spec-kitty``) on macOS;
  ``%LOCALAPPDATA%\\spec-kitty`` on Windows.
* config -- ``$XDG_CONFIG_HOME/spec-kitty`` (else ``~/.config/spec-kitty``) on
  Linux; ``$XDG_CONFIG_HOME/spec-kitty`` (else
  ``~/Library/Application Support/spec-kitty``) on macOS;
  ``%LOCALAPPDATA%\\spec-kitty`` on Windows.

Three details are deliberate:

* The ``platformdirs`` class is chosen here rather than by
  ``platformdirs``' own import-time platform detection, so a test can exercise
  the macOS and Windows branches from any host (spec C-005). The Windows choice
  goes through :func:`kernel.paths.is_windows`, the seam the tests already fake.
* ``appauthor=False`` keeps one Windows convention across the tool:
  :func:`kernel.paths.get_kittify_home` and ``specify_cli.paths.windows_paths``
  pass it too. The default (``appauthor`` = app name) would produce the doubled
  ``%LOCALAPPDATA%\\spec-kitty\\spec-kitty\\Cache``.
* ``ensure_exists`` stays ``False``: resolving a directory is a pure environment
  read that creates nothing, and a caller decides when to write.

State and config coincide on macOS and Windows because that is what
``platformdirs`` documents for those platforms; on Linux they differ, which is
the XDG spec.
"""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs.api import PlatformDirsABC
from platformdirs.macos import MacOS
from platformdirs.unix import Unix
from platformdirs.windows import Windows

from kernel import paths as _paths

__all__ = ["user_cache_dir", "user_config_dir", "user_state_dir"]

APP_NAME = "spec-kitty"


def _platform_dirs() -> PlatformDirsABC:
    """Return the ``platformdirs`` instance for the current platform and app.

    The Windows check goes through :func:`kernel.paths.is_windows` at call time
    (so tests can fake it); macOS is read from ``sys.platform`` for the same
    reason. Everything else takes the Unix class, which is also what
    ``platformdirs`` itself would pick.
    """
    if _paths.is_windows():
        platform_dirs: type[PlatformDirsABC] = Windows
    elif sys.platform == "darwin":
        platform_dirs = MacOS
    else:
        platform_dirs = Unix
    return platform_dirs(appname=APP_NAME, appauthor=False, ensure_exists=False)


def user_cache_dir() -> Path:
    """Return the per-user cache directory for spec-kitty (disposable files)."""
    return Path(_platform_dirs().user_cache_dir)


def user_state_dir() -> Path:
    """Return the per-user state directory for spec-kitty (small persistent markers)."""
    return Path(_platform_dirs().user_state_dir)


def user_config_dir() -> Path:
    """Return the per-user config directory for spec-kitty (operator-edited settings)."""
    return Path(_platform_dirs().user_config_dir)
