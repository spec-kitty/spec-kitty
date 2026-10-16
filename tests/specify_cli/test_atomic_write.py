"""Tests for the shared atomic_write utility."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.atomic import atomic_write


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_atomic_write_str(tmp_path: Path) -> None:
    """Write a string, read back, confirm UTF-8 content matches."""
    target = tmp_path / "output.txt"
    atomic_write(target, "hello world\n")
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_atomic_write_bytes(tmp_path: Path) -> None:
    """Write raw bytes, read back, confirm content matches."""
    target = tmp_path / "output.bin"
    data = b"\x00\x01\x02\xff"
    atomic_write(target, data)
    assert target.read_bytes() == data


def test_atomic_write_mkdir(tmp_path: Path) -> None:
    """Target path with non-existent parents + mkdir=True succeeds."""
    target = tmp_path / "a" / "b" / "c" / "file.txt"
    atomic_write(target, "nested content", mkdir=True)
    assert target.read_text(encoding="utf-8") == "nested content"


def test_atomic_write_mkdir_false_missing_parent(tmp_path: Path) -> None:
    """Target path with non-existent parents + mkdir=False raises FileNotFoundError."""
    target = tmp_path / "nonexistent" / "file.txt"
    with pytest.raises(FileNotFoundError):
        atomic_write(target, "should fail")


def test_atomic_write_interrupt_preserves_original(tmp_path: Path) -> None:
    """Original content is preserved when os.replace raises OSError."""
    target = tmp_path / "data.txt"
    target.write_text("original", encoding="utf-8")

    with (
        patch("specify_cli.core.atomic.os.replace", side_effect=OSError("disk error")),
        pytest.raises(OSError, match="disk error"),
    ):
        atomic_write(target, "replacement")

    # Original content must be intact
    assert target.read_text(encoding="utf-8") == "original"

    # No temp files left behind
    temps = list(tmp_path.glob(".atomic-*.tmp"))
    assert temps == []


def test_atomic_write_keyboard_interrupt_cleanup(tmp_path: Path) -> None:
    """Temp file is cleaned up when KeyboardInterrupt fires (BaseException catch)."""
    target = tmp_path / "data.txt"

    with (
        patch("specify_cli.core.atomic.os.replace", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        atomic_write(target, "interrupted")

    # Target must not exist (was never written)
    assert not target.exists()

    # No temp files left behind
    temps = list(tmp_path.glob(".atomic-*.tmp"))
    assert temps == []


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    """Writing to an existing file replaces old content with new."""
    target = tmp_path / "data.txt"
    target.write_text("old content", encoding="utf-8")

    atomic_write(target, "new content")
    assert target.read_text(encoding="utf-8") == "new content"


def test_atomic_write_temp_in_same_dir(tmp_path: Path) -> None:
    """After a successful write, no .atomic-*.tmp files remain in the target directory."""
    target = tmp_path / "data.txt"
    atomic_write(target, "some content")

    temps = list(tmp_path.glob(".atomic-*.tmp"))
    assert temps == []
    assert target.read_text(encoding="utf-8") == "some content"


def test_atomic_write_overwrites_read_only_destination_and_restores_mode(tmp_path: Path) -> None:
    """A read-only destination is overwritten and left read-only again (#6228).

    Cross-platform gate for the write-bit-restore path: the overwrite must succeed
    over a read-only file (on Windows ``os.replace`` would otherwise raise WinError 5),
    and the destination's original mode must be re-applied afterward. The mode is the
    POSIX-observable proof -- without the fix the file would end at the temp file's
    writable ``0o600`` instead of its original ``0o400``.
    """
    target = tmp_path / "SKILL.md"
    target.write_text("old project skill\n", encoding="utf-8")
    target.chmod(stat.S_IREAD)  # 0o400: a managed read-only asset

    atomic_write(target, "new project skill\n")

    assert target.read_text(encoding="utf-8") == "new project skill\n"
    assert stat.S_IMODE(target.stat().st_mode) == stat.S_IREAD


def test_atomic_write_leaves_a_writable_destination_untouched_in_mode(tmp_path: Path) -> None:
    """A writable destination is overwritten with no read-only dance (#6228 scope guard).

    The write-bit restore is scoped to read-only destinations, so a normal writable
    target behaves exactly as before: content replaced and still owner-writable.
    """
    target = tmp_path / "data.txt"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o644)

    atomic_write(target, "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(target.stat().st_mode) & stat.S_IWRITE
    assert os.access(target, os.W_OK)
