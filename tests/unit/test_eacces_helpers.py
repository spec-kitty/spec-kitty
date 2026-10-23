"""Tests for the denied-access helpers in ``tests/_support/eacces.py`` (#5691).

They live under ``tests/unit`` so they run per PR; ``tests/_support`` runs only nightly.

Every helper must give the same verdict for every uid, so none of these tests
skips as root.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from tests._support import eacces
from tests._support.eacces import deny_open_in, deny_path_method, deny_removal_from

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_POSIX_MODES = pytest.mark.skipif(sys.platform == "win32", reason="POSIX directory write bit")


def test_deny_open_in_denies_only_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "denied.txt"
    other = tmp_path / "other.txt"
    target.write_text("x", encoding="utf-8")
    other.write_text("y", encoding="utf-8")

    deny_open_in(monkeypatch, eacces, target)

    shadow_open = vars(eacces)["open"]  # the module-level shadow the helper installs
    with pytest.raises(PermissionError):
        shadow_open(target)
    with shadow_open(other) as handle:
        assert handle.read() == "y"
    with open(target, encoding="utf-8") as handle:  # this module's own open is untouched
        assert handle.read() == "x"


def test_deny_path_method_matches_a_symlinked_spelling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "denied.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    other = tmp_path / "other.txt"
    other.write_text("y", encoding="utf-8")

    deny_path_method(monkeypatch, "read_text", target)

    with pytest.raises(PermissionError):
        link.read_text(encoding="utf-8")
    assert other.read_text(encoding="utf-8") == "y"


def test_deny_path_method_stat_still_lets_the_link_itself_be_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A regular uid can lstat a link whose target sits in a 0o000 directory; only the stat through it fails."""
    (tmp_path / "vault" / "target").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "vault" / "target", target_is_directory=True)

    deny_path_method(monkeypatch, "stat", link)

    with pytest.raises(PermissionError):
        link.stat()
    assert link.is_symlink()
    assert link.stat(follow_symlinks=False).st_mode


@_POSIX_MODES
def test_deny_removal_from_blocks_unlink_while_the_directory_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    member = parent / "member.txt"
    member.write_text("x", encoding="utf-8")
    parent.chmod(0o555)
    try:
        deny_removal_from(monkeypatch, parent)

        with pytest.raises(PermissionError):
            member.unlink()
        with pytest.raises(PermissionError):
            os.remove(member)
        assert member.exists()

        parent.chmod(0o755)  # restoring the write bit lifts the denial, as for a regular uid
        member.unlink()
    finally:
        parent.chmod(0o755)
    assert not member.exists()


@_POSIX_MODES
def test_deny_removal_from_lets_a_missing_entry_report_itself_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel reports ENOENT before it checks the parent's write bit."""
    parent = tmp_path / "parent"
    parent.mkdir()
    parent.chmod(0o555)
    try:
        deny_removal_from(monkeypatch, parent)

        with pytest.raises(FileNotFoundError):
            os.unlink(parent / "absent.txt")
    finally:
        parent.chmod(0o755)


@_POSIX_MODES
def test_deny_removal_from_blocks_rmdir_and_leaves_other_directories_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "parent"
    (parent / "child").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "free.txt").write_text("x", encoding="utf-8")
    parent.chmod(0o555)
    try:
        deny_removal_from(monkeypatch, parent)

        with pytest.raises(PermissionError):
            (parent / "child").rmdir()
        (elsewhere / "free.txt").unlink()  # a writable directory is never matched
    finally:
        parent.chmod(0o755)
    assert (parent / "child").is_dir()
    assert not (elsewhere / "free.txt").exists()


@_POSIX_MODES
def test_deny_removal_from_reaches_shutil_rmtree_relative_dir_fd_removals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tree = tmp_path / "tree"
    locked = tree / "locked"
    locked.mkdir(parents=True)
    (locked / "member.txt").write_text("x", encoding="utf-8")
    locked.chmod(0o555)
    try:
        deny_removal_from(monkeypatch, locked)

        with pytest.raises(PermissionError):
            shutil.rmtree(tree)
        assert (locked / "member.txt").exists()
    finally:
        if locked.exists():
            locked.chmod(0o755)
