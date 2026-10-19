"""Per-user base directories for cache and state files (#6481).

The one place spec-kitty turns ``XDG_CACHE_HOME`` / ``XDG_STATE_HOME`` /
``LOCALAPPDATA`` into a directory. Both helpers return the *base* directory;
callers append their own ``spec-kitty/...`` subpath.

The helpers reproduce, byte for byte, the locations the callers used before
this module existed, so no file moved when they switched over:

* :func:`user_cache_dir` -- ``%LOCALAPPDATA%`` (else ``~/AppData/Local``) on
  Windows; ``$XDG_CACHE_HOME`` (else ``~/.cache``) everywhere else, macOS
  included. ``windows_local_appdata=False`` drops the Windows branch, so the
  XDG rule applies on Windows too.
* :func:`user_state_dir` -- ``$XDG_STATE_HOME`` (else ``~/.cache``) on every
  platform. The fallback is the literal ``~/.cache``: it does not consult
  ``XDG_CACHE_HOME`` and is not the XDG-spec ``~/.local/state``.

An empty environment variable counts as unset. Relative values are used as
given. Stdlib only: the kernel takes no third-party dependency, so this does
not use ``platformdirs``.
"""

from __future__ import annotations

import os
from pathlib import Path

from kernel import paths as _paths

__all__ = ["user_cache_dir", "user_state_dir"]

_XDG_CACHE_HOME = "XDG_CACHE_HOME"
_XDG_STATE_HOME = "XDG_STATE_HOME"
_LOCALAPPDATA = "LOCALAPPDATA"


def user_cache_dir(*, windows_local_appdata: bool = True) -> Path:
    """Return the per-user base cache directory.

    Windows, when *windows_local_appdata* is true: ``%LOCALAPPDATA%``, or
    ``~/AppData/Local`` when it is unset or empty. Otherwise:
    ``$XDG_CACHE_HOME``, or ``~/.cache`` when it is unset or empty.

    The Windows check goes through :func:`kernel.paths.is_windows` at call
    time, so tests can monkeypatch that seam.
    """
    if windows_local_appdata and _paths.is_windows():
        local_app_data = os.environ.get(_LOCALAPPDATA)
        if local_app_data:
            return Path(local_app_data)
        return Path.home() / "AppData" / "Local"
    xdg = os.environ.get(_XDG_CACHE_HOME)
    if xdg:
        return Path(xdg)
    return Path.home() / ".cache"


def user_state_dir() -> Path:
    """Return the per-user base state directory.

    ``$XDG_STATE_HOME``, or ``~/.cache`` when it is unset or empty, on every
    platform (no Windows or macOS branch).
    """
    state_home = os.environ.get(_XDG_STATE_HOME)
    if state_home:
        return Path(state_home)
    return Path.home() / ".cache"
