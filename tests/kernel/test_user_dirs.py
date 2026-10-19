"""Branch tests for ``kernel.user_dirs`` (#6481).

Every branch of :func:`user_cache_dir` and :func:`user_state_dir`, on each
platform. The Windows branch is selected through the ``kernel.paths.is_windows``
seam; ``os.name`` is never faked (it flips ``pathlib`` to ``WindowsPath``).
``sys.platform`` is set to ``darwin`` to prove macOS takes the POSIX rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from kernel.user_dirs import user_cache_dir, user_state_dir

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ENV_VARS = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "LOCALAPPDATA")


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An isolated home with every variable the helpers read cleared."""
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return fake_home


def _platform(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setattr("kernel.paths.is_windows", lambda: name == "windows")
    monkeypatch.setattr(sys, "platform", {"linux": "linux", "darwin": "darwin", "windows": "win32"}[name])


# -- user_cache_dir ----------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_cache_posix_honours_xdg_cache_home(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path, platform: str) -> None:
    _platform(monkeypatch, platform)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))
    assert user_cache_dir() == tmp_path / "xdg"


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("xdg", [None, ""])
def test_cache_posix_falls_back_to_dot_cache(monkeypatch: pytest.MonkeyPatch, home: Path, platform: str, xdg: str | None) -> None:
    _platform(monkeypatch, platform)
    if xdg is not None:
        monkeypatch.setenv("XDG_CACHE_HOME", xdg)
    assert user_cache_dir() == home / ".cache"


def test_cache_windows_uses_localappdata(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path) -> None:
    _platform(monkeypatch, "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "ignored"))
    assert user_cache_dir() == tmp_path / "lad"


@pytest.mark.parametrize("lad", [None, ""])
def test_cache_windows_falls_back_to_appdata_local(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path, lad: str | None) -> None:
    _platform(monkeypatch, "windows")
    if lad is not None:
        monkeypatch.setenv("LOCALAPPDATA", lad)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "ignored"))
    assert user_cache_dir() == home / "AppData" / "Local"


def test_cache_windows_opt_out_uses_xdg_rule(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path) -> None:
    _platform(monkeypatch, "windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))
    assert user_cache_dir(windows_local_appdata=False) == home / ".cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert user_cache_dir(windows_local_appdata=False) == tmp_path / "xdg"


def test_cache_relative_xdg_is_used_as_given(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    _platform(monkeypatch, "linux")
    monkeypatch.setenv("XDG_CACHE_HOME", "rel/cache")
    assert user_cache_dir() == Path("rel/cache")


# -- user_state_dir ----------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
def test_state_honours_xdg_state_home(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path, platform: str) -> None:
    _platform(monkeypatch, platform)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored"))
    assert user_state_dir() == tmp_path / "state"


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize("state", [None, ""])
def test_state_falls_back_to_literal_dot_cache(monkeypatch: pytest.MonkeyPatch, home: Path, tmp_path: Path, platform: str, state: str | None) -> None:
    """The fallback is ``~/.cache`` itself: neither XDG_CACHE_HOME nor LOCALAPPDATA."""
    _platform(monkeypatch, platform)
    if state is not None:
        monkeypatch.setenv("XDG_STATE_HOME", state)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "ignored-cache"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "ignored-lad"))
    assert user_state_dir() == home / ".cache"
