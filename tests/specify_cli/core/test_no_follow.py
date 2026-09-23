"""Contract tests for the shared no-follow file helpers (issue #699)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.core.no_follow import (
    NoFollowPathError,
    chmod_fd,
    fd_relative_dir_ops_supported,
    read_text_no_follow,
    write_text_no_follow,
)


pytestmark = [pytest.mark.fast, pytest.mark.unit]


def test_regular_file_can_be_written_and_read(tmp_path: Path) -> None:
    """The helper provides ordinary text-file semantics for regular files."""
    path = tmp_path / "settings.txt"

    write_text_no_follow(path, "safe content\n")

    assert read_text_no_follow(path) == "safe content\n"


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="kernel no-follow flag unavailable")
def test_read_rejects_symlink_without_reading_its_target(tmp_path: Path) -> None:
    """A final-component symlink is refused by the open syscall itself."""
    target = tmp_path / "secret.txt"
    target.write_text("do not disclose\n", encoding="utf-8")
    path = tmp_path / "settings.txt"
    path.symlink_to(target)

    with pytest.raises(NoFollowPathError):
        read_text_no_follow(path)

    assert target.read_text(encoding="utf-8") == "do not disclose\n"


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="kernel no-follow flag unavailable")
def test_read_rejects_dangling_symlink(tmp_path: Path) -> None:
    """A dangling link cannot be mistaken for an absent regular file."""
    path = tmp_path / "settings.txt"
    path.symlink_to(tmp_path / "missing-target.txt")

    with pytest.raises(NoFollowPathError):
        read_text_no_follow(path)


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="kernel no-follow flag unavailable")
def test_read_rejects_symlink_planted_before_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The syscall refuses a link swapped in after the caller chose the path."""
    path = tmp_path / "settings.txt"
    path.write_text("safe content\n", encoding="utf-8")
    target = tmp_path / "secret.txt"
    target.write_text("do not disclose\n", encoding="utf-8")
    original_open = os.open
    swapped = False

    def plant_symlink(candidate: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        nonlocal swapped
        if Path(candidate) == path and not swapped:
            path.unlink()
            path.symlink_to(target)
            swapped = True
        return original_open(candidate, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", plant_symlink)

    with pytest.raises(NoFollowPathError):
        read_text_no_follow(path)

    assert swapped
    assert target.read_text(encoding="utf-8") == "do not disclose\n"


def test_chmod_fd_uses_fchmod_when_available(tmp_path: Path) -> None:
    """On a platform with ``os.fchmod`` (every CI target), the fd path is used."""
    path = tmp_path / "settings.txt"
    path.write_text("content\n", encoding="utf-8")

    with path.open("r+b") as handle:
        chmod_fd(handle.fileno(), path, 0o640)

    import stat

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_chmod_fd_falls_back_to_path_chmod_without_fchmod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no ``os.fchmod``) still applies the mode via ``Path.chmod``.

    Before the fix this call would raise ``AttributeError: module 'os' has
    no attribute 'fchmod'`` on a platform lacking the syscall.
    """
    monkeypatch.delattr(os, "fchmod", raising=False)
    path = tmp_path / "settings.txt"
    path.write_text("content\n", encoding="utf-8")

    with path.open("r+b") as handle:
        chmod_fd(handle.fileno(), path, 0o640)

    import stat

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_fd_relative_dir_ops_supported_true_on_this_platform() -> None:
    """Every CI target (Linux/macOS) supports the fd-relative dance."""
    assert fd_relative_dir_ops_supported() is (os.open in os.supports_dir_fd and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"))


def test_fd_relative_dir_ops_supported_false_when_o_nofollow_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows: no ``O_NOFOLLOW`` means the predicate reports unsupported."""
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)

    assert fd_relative_dir_ops_supported() is False


def test_fd_relative_dir_ops_supported_false_when_dir_fd_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows: an empty ``os.supports_dir_fd`` means unsupported."""
    monkeypatch.setattr(os, "supports_dir_fd", set())

    assert fd_relative_dir_ops_supported() is False
