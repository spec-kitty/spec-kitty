"""Branch pins for ``kernel.user_dirs`` (#6488).

Every branch of :func:`user_cache_dir`, :func:`user_state_dir` and
:func:`user_config_dir`, on each platform. The authority delegates to
``platformdirs``, so these pins read that library's own layout for the app:

* Linux -- XDG bases, with ``~/.cache``, ``~/.local/state`` and ``~/.config``
  as the documented fallbacks;
* macOS -- ``~/Library/Caches`` and ``~/Library/Application Support``, with the
  XDG variables still winning when set (``platformdirs``' ``XDGMixin``);
* Windows -- ``%LOCALAPPDATA%`` with the opinionated ``Cache`` level for the
  cache and no XDG branch at all.

The Windows branch is selected through the ``kernel.paths.is_windows`` seam and
the macOS branch through ``sys.platform``; ``os.name`` is never faked (it flips
``pathlib`` to ``WindowsPath``). On a non-Windows host ``platformdirs`` reads
``WIN_PD_OVERRIDE_*``/``LOCALAPPDATA`` instead of the shell API, which is how
these pins run on Linux (spec C-005: no macOS or Windows host is available).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.user_dirs import user_cache_dir, user_config_dir, user_state_dir
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]

APP = "spec-kitty"

#: ``(kind, platform) -> (base relative to the faked home, *segments after the base)``.
#: The single table the default-fallback pins and the empty-variable pins share, so
#: the two can never drift apart.
_DEFAULTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("cache", "linux"): (".cache", APP),
    ("cache", "darwin"): ("Library", "Caches", APP),
    ("state", "linux"): (".local", "state", APP),
    ("state", "darwin"): ("Library", "Application Support", APP),
    ("config", "linux"): (".config", APP),
    ("config", "darwin"): ("Library", "Application Support", APP),
}

_RESOLVERS = {"cache": user_cache_dir, "state": user_state_dir, "config": user_config_dir}


def _resolve(kind: str) -> Path:
    return _RESOLVERS[kind]()


# -- XDG overrides (honoured on Linux and macOS) -----------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize(("kind", "variable", "expected"), [
    ("cache", "XDG_CACHE_HOME", "xdg"),
    ("state", "XDG_STATE_HOME", "xdg"),
    ("config", "XDG_CONFIG_HOME", "xdg"),
])
def test_posix_honours_the_xdg_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, kind: str, variable: str, expected: str) -> None:
    fake_platform(monkeypatch, tmp_path, platform, {variable: expected})
    assert _resolve(kind) == tmp_path / expected / APP


def test_macos_honours_xdg_cache_home_before_library_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``platformdirs``' macOS class mixes XDG in, so an XDG variable wins on macOS too."""
    fake_platform(monkeypatch, tmp_path, "darwin", {"XDG_CACHE_HOME": "xdg"})
    assert user_cache_dir() == tmp_path / "xdg" / APP


# -- platform defaults ------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("kind", ["cache", "state", "config"])
def test_posix_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, kind: str) -> None:
    home = fake_platform(monkeypatch, tmp_path, platform, {})
    assert _resolve(kind) == home.joinpath(*_DEFAULTS[(kind, platform)])


@pytest.mark.parametrize(("kind", "expected"), [
    ("cache", ("lad", APP, "Cache")),
    ("state", ("lad", APP)),
    ("config", ("lad", APP)),
])
def test_windows_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str, expected: tuple[str, ...]) -> None:
    """``%LOCALAPPDATA%`` for all three; the cache additionally gets ``Cache``."""
    fake_platform(monkeypatch, tmp_path, "windows", {"LOCALAPPDATA": "lad"})
    assert _resolve(kind) == tmp_path.joinpath(*expected)


@pytest.mark.parametrize("kind", ["cache", "state", "config"])
def test_windows_reads_no_xdg_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str) -> None:
    """``platformdirs`` gives Windows no XDG branch; the pre-#6488 helper did."""
    fake_platform(monkeypatch, tmp_path, "windows", {"LOCALAPPDATA": "lad", "XDG_CACHE_HOME": "ignored", "XDG_STATE_HOME": "ignored", "XDG_CONFIG_HOME": "ignored"})
    assert "ignored" not in _resolve(kind).parts
    assert _resolve(kind) == tmp_path.joinpath("lad", APP, *(["Cache"] if kind == "cache" else []))


# -- rules that hold on every platform --------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize("kind", ["cache", "state", "config"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_posix_variable_counts_as_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, kind: str, value: str) -> None:
    home = fake_platform(monkeypatch, tmp_path, platform, {})
    monkeypatch.setenv({"cache": "XDG_CACHE_HOME", "state": "XDG_STATE_HOME", "config": "XDG_CONFIG_HOME"}[kind], value)
    assert _resolve(kind) == home.joinpath(*_DEFAULTS[(kind, platform)])


def test_relative_xdg_value_is_used_as_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_platform(monkeypatch, tmp_path, "linux", {})
    monkeypatch.setenv("XDG_CACHE_HOME", "rel/cache")
    assert user_cache_dir() == Path("rel/cache") / APP


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize("kind", ["cache", "state", "config"])
def test_app_name_appears_once_in_every_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, kind: str) -> None:
    """No doubled ``spec-kitty/spec-kitty`` segment (the ``appauthor`` trap on Windows)."""
    fake_platform(monkeypatch, tmp_path, platform, {"LOCALAPPDATA": "lad"})
    assert _resolve(kind).parts.count(APP) == 1


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize("kind", ["cache", "state", "config"])
def test_resolving_creates_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, kind: str) -> None:
    """NFR-002: resolution is a pure environment read."""
    fake_platform(monkeypatch, tmp_path, platform, {"LOCALAPPDATA": "lad"})
    path = _resolve(kind)
    assert not path.exists()
    assert not path.parent.exists(), f"{path.parent} was created by resolving"
    assert list(tmp_path.iterdir()) == [], "resolving created something"
