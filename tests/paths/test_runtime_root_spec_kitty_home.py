"""Env-precedence tests for ``get_runtime_root()`` honoring ``SPEC_KITTY_HOME``.

Locks the keystone contract in
``kitty-specs/spec-kitty-home-isolation-01KW1JXX/contracts/runtime-state-root.md``
(obligations T-RR-1 .. T-RR-4) and the mission requirements FR-011 (env wins on
all platforms), FR-012 (empty/unset falls through), and NFR-002 (pure resolution
— no directory creation).

Platform dispatch is forced by monkeypatching ``windows_paths._current_platform``
(the single platform-detection source used by ``get_runtime_root``); the Windows
default is made deterministic by stubbing ``platformdirs.user_data_dir`` so the
tests are stable on any host OS.
"""
from __future__ import annotations

import platformdirs
import pytest

from pathlib import Path

from specify_cli.paths import RuntimeRoot, get_runtime_root
from specify_cli.paths import windows_paths

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# The three normalised platform strings ``_current_platform`` can return.
PLATFORMS = ("linux", "darwin", "win32")
# Deterministic stand-in for the Windows LocalAppData base.
WIN_DATA_DIR = r"C:\Users\test\AppData\Local\spec-kitty"


def _force_platform(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    """Pin ``get_runtime_root``'s platform detection to *platform*."""
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: platform)


def _stub_windows_data_dir(
    monkeypatch: pytest.MonkeyPatch, value: str = WIN_DATA_DIR
) -> None:
    """Make the Windows ``platformdirs`` default deterministic on any host."""
    monkeypatch.setattr(platformdirs, "user_data_dir", lambda *_a, **_kw: value)


def _pin_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    """Pin ``Path.home()`` so POSIX defaults are deterministic and isolated."""
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))


# ---------------------------------------------------------------------------
# T-RR-1 / FR-011: a non-empty SPEC_KITTY_HOME becomes base on ALL platforms.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", PLATFORMS)
def test_spec_kitty_home_overrides_base_on_all_platforms(
    monkeypatch: pytest.MonkeyPatch, platform: str, tmp_path: Path
) -> None:
    """Set env ⇒ base is the env path verbatim, regardless of platform."""
    _force_platform(monkeypatch, platform)
    # Stub the Windows default too, to prove the env branch wins before it.
    _stub_windows_data_dir(monkeypatch)
    env_base = tmp_path / "skhome"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(env_base))

    root = get_runtime_root()

    assert root.base == env_base
    assert root.platform == platform


def test_spec_kitty_home_is_used_verbatim_not_suffixed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The env path is the base directly — ``.spec-kitty`` is NOT appended."""
    _force_platform(monkeypatch, "linux")
    base = tmp_path / "skhome"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))

    root = get_runtime_root()

    assert root.base == base
    assert root.base.name != ".spec-kitty"


def test_distinct_env_values_yield_distinct_bases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Isolation guarantee G1: different env values ⇒ different bases."""
    _force_platform(monkeypatch, "linux")

    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "one"))
    first = get_runtime_root().base
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "two"))
    second = get_runtime_root().base

    assert first != second


# ---------------------------------------------------------------------------
# T-RR-2 / FR-012: an EMPTY SPEC_KITTY_HOME falls through to platform default.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", PLATFORMS)
def test_empty_spec_kitty_home_falls_through(
    monkeypatch: pytest.MonkeyPatch, platform: str, tmp_path: Path
) -> None:
    """Empty string is falsy ⇒ resolves to the platform default."""
    _force_platform(monkeypatch, platform)
    _stub_windows_data_dir(monkeypatch)
    fake_home = tmp_path / "home"
    _pin_home(monkeypatch, fake_home)
    monkeypatch.setenv("SPEC_KITTY_HOME", "")

    root = get_runtime_root()

    if platform == "win32":
        assert root.base == Path(WIN_DATA_DIR)
    else:
        assert root.base == fake_home / ".spec-kitty"


# ---------------------------------------------------------------------------
# T-RR-3 / FR-012: UNSET SPEC_KITTY_HOME preserves the pre-fix defaults.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", PLATFORMS)
def test_unset_spec_kitty_home_uses_platform_default(
    monkeypatch: pytest.MonkeyPatch, platform: str, tmp_path: Path
) -> None:
    """Unset env ⇒ POSIX ``~/.spec-kitty``; win32 platformdirs base."""
    _force_platform(monkeypatch, platform)
    _stub_windows_data_dir(monkeypatch)
    fake_home = tmp_path / "home"
    _pin_home(monkeypatch, fake_home)
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)

    root = get_runtime_root()

    if platform == "win32":
        assert root.base == Path(WIN_DATA_DIR)
    else:
        assert root.base == fake_home / ".spec-kitty"


# ---------------------------------------------------------------------------
# Derived directories inherit the env-aware base (G4 / FR-011).
# ---------------------------------------------------------------------------


def test_derived_dirs_inherit_env_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """All derived dirs are ``base`` joined with their fixed suffix."""
    _force_platform(monkeypatch, "darwin")
    base = tmp_path / "skhome"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))

    root = get_runtime_root()

    assert root.base == base
    assert root.auth_dir == base / "auth"
    assert root.tracker_dir == base / "tracker"
    assert root.cache_dir == base / "cache"


def test_runtime_root_remains_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """RuntimeRoot stays an immutable frozen dataclass (T002)."""
    import dataclasses

    _force_platform(monkeypatch, "linux")
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "skhome"))

    root = get_runtime_root()

    assert isinstance(root, RuntimeRoot)
    # RuntimeRoot is a frozen dataclass: attribute assignment must raise.
    with pytest.raises(dataclasses.FrozenInstanceError):
        root.base = tmp_path  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T-RR-4 / T005 / NFR-002: resolution is pure — it creates no directories.
# ---------------------------------------------------------------------------


def _assert_no_dirs_created(root: RuntimeRoot) -> None:
    """Read every path off *root* and assert none materialised on disk."""
    for path in (
        root.base,
        root.auth_dir,
        root.tracker_dir,
        root.cache_dir,
    ):
        assert not path.exists(), f"{path} was created — resolution is not pure"


def test_resolution_creates_no_directories_with_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With HOME and SPEC_KITTY_HOME at fresh temp dirs, nothing is created."""
    _force_platform(monkeypatch, "linux")
    fake_home = tmp_path / "home"
    env_home = tmp_path / "skhome"
    _pin_home(monkeypatch, fake_home)
    monkeypatch.setenv("SPEC_KITTY_HOME", str(env_home))

    # Pre-conditions: neither root exists yet.
    assert not fake_home.exists()
    assert not env_home.exists()

    root = get_runtime_root()
    _assert_no_dirs_created(root)

    # The env-home base and the (unused) default home are both untouched.
    assert not env_home.exists()
    assert not fake_home.exists()


def test_resolution_creates_no_directories_with_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The default (env-unset) branch is equally pure — no dirs created."""
    _force_platform(monkeypatch, "linux")
    fake_home = tmp_path / "home"
    _pin_home(monkeypatch, fake_home)
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)

    assert not fake_home.exists()

    root = get_runtime_root()
    _assert_no_dirs_created(root)

    assert not fake_home.exists()
