"""Shared set-up for the per-user location pins (#6481, converged by #6488).

One fixture fakes one platform and one environment for every caller of
``kernel.user_dirs``: the Windows branch goes through the ``kernel.paths.is_windows``
seam (``os.name`` is never faked -- it would flip ``pathlib`` to ``WindowsPath``) and
``sys.platform`` is set so the macOS branch is exercised on any host.

Because the authority now delegates to ``platformdirs``, the fixture also owns the
environment that library reads: on a non-Windows host ``platformdirs.windows`` falls
back to ``LOCALAPPDATA``/``APPDATA``/``USERPROFILE`` (and honours ``WIN_PD_OVERRIDE_*``
first), and ``platformdirs.macos``/``unix`` honour ``XDG_*`` if they are set. A variable
this fixture does not clear leaks the running host's configuration into the pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SYS_PLATFORM = {"linux": "linux", "darwin": "darwin", "windows": "win32"}

#: Every variable ``kernel.user_dirs`` or ``platformdirs`` may read for these kinds.
_ENV_VARS = (
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "LOCALAPPDATA",
    "APPDATA",
    "USERPROFILE",
    "WIN_PD_OVERRIDE_LOCAL_APPDATA",
    "WIN_PD_OVERRIDE_APPDATA",
)


def fake_platform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, env: dict[str, str]) -> Path:
    """Fake *platform* with only the variables in *env* set (values relative to *tmp_path*); return the fake home."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, str(tmp_path / value))
    if platform == "windows":
        # ``platformdirs.windows`` asks the shell for CSIDL_LOCAL_APPDATA; off win32 it
        # falls back to these environment overrides (then to ``LOCALAPPDATA``/``APPDATA``).
        # Aliasing them keeps the test call sites reading the Windows variable names.
        for source, override in (("LOCALAPPDATA", "WIN_PD_OVERRIDE_LOCAL_APPDATA"), ("APPDATA", "WIN_PD_OVERRIDE_APPDATA")):
            if source in env:
                monkeypatch.setenv(override, str(tmp_path / env[source]))
    monkeypatch.setattr("kernel.paths.is_windows", lambda: platform == "windows")
    monkeypatch.setattr(sys, "platform", _SYS_PLATFORM[platform])
    return home
