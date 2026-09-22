"""Unit tests for ``backup_before_overwrite`` (WP01, contract §P1).

Covers: byte-identity + mode/mtime preservation for regular files, ``O_EXCL``
collision refusal, symlink non-dereference (including a broken link), and
that the original file/link is never mutated by the call.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from specify_cli.asset_preservation.backup import backup_before_overwrite

pytestmark = pytest.mark.unit


def test_regular_file_sidecar_is_byte_identical(tmp_path: Path) -> None:
    original = tmp_path / "pre-commit"
    content = b"#!/bin/sh\necho hook\n"
    original.write_bytes(content)
    os.chmod(original, 0o755)

    sidecar = backup_before_overwrite(original)

    assert sidecar.parent == original.parent
    assert sidecar.name.startswith(f"{original.name}.")
    assert sidecar.name != original.name
    assert sidecar.read_bytes() == content


def test_regular_file_sidecar_preserves_mode_and_mtime(tmp_path: Path) -> None:
    original = tmp_path / "pre-commit"
    original.write_bytes(b"payload")
    os.chmod(original, 0o750)
    info = original.lstat()
    os.utime(original, ns=(info.st_mtime_ns, info.st_mtime_ns))

    sidecar = backup_before_overwrite(original)

    src_info = original.lstat()
    dest_info = sidecar.lstat()
    assert stat.S_IMODE(dest_info.st_mode) == stat.S_IMODE(src_info.st_mode)
    assert dest_info.st_mtime_ns == src_info.st_mtime_ns


def test_second_call_same_second_does_not_silently_clobber(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "pre-commit"
    original.write_bytes(b"payload")

    frozen_stamp = "20260101T000000Z"
    monkeypatch.setattr(
        "specify_cli.asset_preservation.backup.now_utc_compact_stamp",
        lambda: frozen_stamp,
    )

    first = backup_before_overwrite(original)
    assert first.name == f"pre-commit.{frozen_stamp}"

    with pytest.raises(FileExistsError):
        backup_before_overwrite(original)


def test_symlink_sidecar_is_a_symlink_to_same_target(tmp_path: Path) -> None:
    target = tmp_path / "real-hook"
    target.write_bytes(b"real content")
    link = tmp_path / "pre-commit"
    link.symlink_to(target)

    sidecar = backup_before_overwrite(link)

    assert sidecar.is_symlink()
    assert os.readlink(sidecar) == os.readlink(link)
    # Original link is untouched.
    assert link.is_symlink()
    assert os.readlink(link) == str(target)


def test_broken_symlink_backed_up_without_raising(tmp_path: Path) -> None:
    missing_target = tmp_path / "does-not-exist"
    link = tmp_path / "pre-commit"
    link.symlink_to(missing_target)

    sidecar = backup_before_overwrite(link)

    assert sidecar.is_symlink()
    assert os.readlink(sidecar) == str(missing_target)
    assert not sidecar.exists()  # broken link: exists() follows and fails
    assert link.is_symlink()


def test_original_regular_file_never_modified(tmp_path: Path) -> None:
    original = tmp_path / "pre-commit"
    content = b"original bytes"
    original.write_bytes(content)
    info_before = original.lstat()

    backup_before_overwrite(original)

    info_after = original.lstat()
    assert original.read_bytes() == content
    assert info_after.st_mtime_ns == info_before.st_mtime_ns
    assert info_after.st_mode == info_before.st_mode


def test_original_symlink_never_modified(tmp_path: Path) -> None:
    target = tmp_path / "real-hook"
    target.write_bytes(b"real content")
    link = tmp_path / "pre-commit"
    link.symlink_to(target)

    backup_before_overwrite(link)

    assert link.is_symlink()
    assert os.readlink(link) == str(target)


def test_exported_in_all() -> None:
    from specify_cli.asset_preservation import backup

    assert "backup_before_overwrite" in backup.__all__
