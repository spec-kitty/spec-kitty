"""Branch tests for ``kernel.user_dirs`` (#6481).

Every branch of :func:`user_cache_dir` and :func:`user_state_dir`, on each
platform. The Windows branch is selected through the ``kernel.paths.is_windows``
seam; ``os.name`` is never faked (it flips ``pathlib`` to ``WindowsPath``).
``sys.platform`` is set to ``darwin`` to prove macOS takes the POSIX rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.user_dirs import user_cache_dir, user_state_dir
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# -- user_cache_dir ----------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_cache_posix_honours_xdg_cache_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str) -> None:
    fake_platform(monkeypatch, tmp_path, platform, {"XDG_CACHE_HOME": "xdg", "LOCALAPPDATA": "ignored"})
    assert user_cache_dir() == tmp_path / "xdg"


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("xdg", [None, ""])
def test_cache_posix_falls_back_to_dot_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, xdg: str | None) -> None:
    home = fake_platform(monkeypatch, tmp_path, platform, {})
    if xdg is not None:
        monkeypatch.setenv("XDG_CACHE_HOME", xdg)
    assert user_cache_dir() == home / ".cache"


def test_cache_windows_uses_localappdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_platform(monkeypatch, tmp_path, "windows", {"LOCALAPPDATA": "lad", "XDG_CACHE_HOME": "ignored"})
    assert user_cache_dir() == tmp_path / "lad"


@pytest.mark.parametrize("lad", [None, ""])
def test_cache_windows_falls_back_to_appdata_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lad: str | None) -> None:
    home = fake_platform(monkeypatch, tmp_path, "windows", {"XDG_CACHE_HOME": "ignored"})
    if lad is not None:
        monkeypatch.setenv("LOCALAPPDATA", lad)
    assert user_cache_dir() == home / "AppData" / "Local"


def test_cache_windows_opt_out_uses_xdg_rule(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = fake_platform(monkeypatch, tmp_path, "windows", {"LOCALAPPDATA": "ignored"})
    assert user_cache_dir(windows_local_appdata=False) == home / ".cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert user_cache_dir(windows_local_appdata=False) == tmp_path / "xdg"


def test_cache_relative_xdg_is_used_as_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_platform(monkeypatch, tmp_path, "linux", {})
    monkeypatch.setenv("XDG_CACHE_HOME", "rel/cache")
    assert user_cache_dir() == Path("rel/cache")


# -- user_state_dir ----------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
def test_state_honours_xdg_state_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str) -> None:
    fake_platform(monkeypatch, tmp_path, platform, {"XDG_STATE_HOME": "state", "LOCALAPPDATA": "ignored"})
    assert user_state_dir() == tmp_path / "state"


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize("state", [None, ""])
def test_state_falls_back_to_literal_dot_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, state: str | None) -> None:
    """The fallback is ``~/.cache`` itself: neither XDG_CACHE_HOME nor LOCALAPPDATA."""
    home = fake_platform(monkeypatch, tmp_path, platform, {"XDG_CACHE_HOME": "ignored-cache", "LOCALAPPDATA": "ignored-lad"})
    if state is not None:
        monkeypatch.setenv("XDG_STATE_HOME", state)
    assert user_state_dir() == home / ".cache"
