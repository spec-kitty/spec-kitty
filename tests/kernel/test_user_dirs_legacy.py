"""Discard the per-user directories the pre-#6488 rules wrote (#6488).

The dangerous half of this clean-up is what it must *not* remove. On Linux the pre-fix
state root (``$XDG_STATE_HOME``, else the literal ``~/.cache``, then ``spec-kitty``) is the
post-fix **cache** root, so a naive "delete the old state directory" step would delete the
live open-packs and service caches on every Linux machine. Windows has the mirror problem:
the pre-fix cache root (``%LOCALAPPDATA%\\spec-kitty``) is the post-fix **state** directory.

Every test below therefore asserts both halves on one fixture: the legacy root that must go,
and the live directory that must survive. A probe that always deleted, or always kept,
fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import user_dirs_legacy
from kernel.user_dirs import user_cache_dir, user_state_dir
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _plant(path: Path, payload: str = "{}") -> Path:
    """Create *path* as a file with parents, so a removal has something to prove."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


# -- macOS: the whole legacy tree moves and is discarded ---------------------


def test_macos_legacy_cache_tree_is_discarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = fake_platform(monkeypatch, tmp_path, "darwin", {})
    legacy = _plant(home / ".cache" / "spec-kitty" / "upgrade-check.json")
    live_cache = user_cache_dir()
    live_marker = _plant(user_state_dir() / ".spec-kitty-runtime-cutover-notice-shown", "")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert legacy.exists() is False, "the pre-#6488 macOS cache tree must be discarded"
    assert (home / ".cache" / "spec-kitty") in removed
    assert live_cache == home / "Library" / "Caches" / "spec-kitty"
    assert live_marker.exists(), "the resolved state directory is never touched"


def test_macos_legacy_tree_is_left_alone_when_xdg_cache_home_is_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With ``XDG_CACHE_HOME`` set the new location already was the old one."""
    _home = fake_platform(monkeypatch, tmp_path, "darwin", {"XDG_CACHE_HOME": "xdg"})
    live = _plant(tmp_path / "xdg" / "spec-kitty" / "upgrade-check.json")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == ()
    assert live.exists()


# -- Linux: nothing is discarded, because the legacy root is live ------------


def test_linux_legacy_state_root_is_the_live_cache_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = fake_platform(monkeypatch, tmp_path, "linux", {})
    live = _plant(home / ".cache" / "spec-kitty" / "open-packs" / "abc" / "tree.yaml")
    _plant(home / ".cache" / "spec-kitty" / "upgrade-check.json")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == (), "~/.cache/spec-kitty is the live cache directory on Linux"
    assert live.exists()
    assert user_cache_dir() == home / ".cache" / "spec-kitty"


def test_linux_discards_only_the_marker_file_inside_the_live_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """On Linux the moved *state* file is the marker; the directory itself is the live cache."""
    home = fake_platform(monkeypatch, tmp_path, "linux", {})
    legacy_root = home / ".cache" / "spec-kitty"
    stale_marker = _plant(legacy_root / ".spec-kitty-runtime-cutover-notice-shown", "")
    live_cache = _plant(legacy_root / "open-packs" / "abc" / "tree.yaml")
    live_marker = _plant(user_state_dir() / ".spec-kitty-runtime-cutover-notice-shown", "")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == (stale_marker,), "exactly the stale marker file, nothing else"
    assert stale_marker.exists() is False
    assert live_cache.exists(), "the live pack cache was not touched"
    assert live_marker.exists(), "the live marker was not touched"


# -- Windows: the doubled-author tree goes, the live tree stays --------------


def test_windows_doubled_author_tree_is_discarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_platform(monkeypatch, tmp_path, "windows", {"LOCALAPPDATA": "lad"})
    legacy = _plant(tmp_path / "lad" / "spec-kitty" / "spec-kitty" / "Cache" / "upgrade-nag.json")
    live_state = _plant(user_state_dir() / "some-state.json")
    live_cache = _plant(user_cache_dir() / "open-packs" / "abc" / "tree.yaml")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert legacy.exists() is False
    assert (tmp_path / "lad" / "spec-kitty" / "spec-kitty") in removed
    assert live_state.exists(), "%LOCALAPPDATA%/spec-kitty is the live state directory"
    assert live_cache.exists()


# -- bounds -----------------------------------------------------------------


def test_a_symlinked_candidate_is_left_in_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = fake_platform(monkeypatch, tmp_path, "darwin", {})
    target = _plant(tmp_path / "elsewhere" / "keep.txt")
    link = home / ".cache" / "spec-kitty"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target.parent, target_is_directory=True)

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == ()
    assert link.is_symlink()
    assert target.exists()


def test_a_candidate_holding_a_git_checkout_is_left_in_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = fake_platform(monkeypatch, tmp_path, "darwin", {})
    legacy = home / ".cache" / "spec-kitty"
    (legacy / ".git").mkdir(parents=True)
    _plant(legacy / "upgrade-check.json")

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == ()
    assert legacy.exists(), "a git checkout is never deleted by this path"


def test_a_removal_failure_is_silent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    home = fake_platform(monkeypatch, tmp_path, "darwin", {})
    _plant(home / ".cache" / "spec-kitty" / "upgrade-check.json")

    def boom(*_args: object, **_kwargs: object) -> bool:
        raise OSError("read-only")

    monkeypatch.setattr(user_dirs_legacy, "remove_tool_owned_tree", boom)

    removed = user_dirs_legacy.discard_legacy_locations()

    assert removed == ()
    captured = capsys.readouterr()
    assert captured.out == "", "clean-up never writes to stdout"
    assert captured.err == "", "clean-up never writes to stderr"


def test_nothing_is_discarded_when_no_legacy_root_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_platform(monkeypatch, tmp_path, "darwin", {})
    assert user_dirs_legacy.discard_legacy_locations() == ()


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
def test_a_candidate_that_is_live_today_is_never_discarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str) -> None:
    """Invariant L1: with the XDG variables set, every legacy root *is* a live directory."""
    fake_platform(
        monkeypatch,
        tmp_path,
        platform,
        {"LOCALAPPDATA": "lad", "XDG_CACHE_HOME": "xdg", "XDG_STATE_HOME": "state", "XDG_CONFIG_HOME": "cfg"},
    )
    live = _plant(user_cache_dir() / "keep.json")
    expected = {tmp_path / "xdg" / "spec-kitty", tmp_path / "state" / "spec-kitty"}
    if platform == "windows":
        # The pre-fix Windows cache root and the platformdirs doubled-author tree.
        expected |= {tmp_path / "lad" / "spec-kitty", tmp_path / "lad" / "spec-kitty" / "spec-kitty"}
    assert set(user_dirs_legacy.legacy_roots()) == expected

    assert user_dirs_legacy.discard_legacy_locations() == ()
    assert live.exists(), "a directory the tool still writes to was deleted"
