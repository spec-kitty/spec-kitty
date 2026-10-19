"""Shared set-up for the per-caller location pins of #6481.

Each caller of ``kernel.user_dirs`` pins the exact path it resolved before the
helpers existed. This module fakes one platform and one environment: the
Windows branch goes through the ``kernel.paths.is_windows`` seam (``os.name`` is
never faked) and ``sys.platform`` is set so a macOS branch, if one were added,
would be exercised.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SYS_PLATFORM = {"linux": "linux", "darwin": "darwin", "windows": "win32"}
_ENV_VARS = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "LOCALAPPDATA")


def fake_platform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, env: dict[str, str]) -> Path:
    """Fake *platform* with only the variables in *env* set (values relative to *tmp_path*); return the fake home."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, str(tmp_path / value))
    monkeypatch.setattr("kernel.paths.is_windows", lambda: platform == "windows")
    monkeypatch.setattr(sys, "platform", _SYS_PLATFORM[platform])
    return home
