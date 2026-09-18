"""Contract tests for the canonical managed-asset safe-delete util (#4714).

Managed content is materialized read-only (``0o444``/``0o555``). Windows
``DeleteFile``/``RemoveDirectory`` refuse a read-only target with
``PermissionError``; POSIX ignores the mode on unlink/rmdir. The util clears
the write bit and retries. The no-follow (``lstat``) + masked (``S_IMODE``)
contract is the load-bearing property under test here (SC-006): a
managed-asset delete must never chmod through a symlink onto a target that
may live outside the managed tree.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from specify_cli.core.safe_delete import force_writable, safe_rmdir, safe_unlink

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _is_readonly(path: Path) -> bool:
    return not (path.lstat().st_mode & stat.S_IWRITE)


class TestForceWritable:
    """Direct coverage of the bit-clearing primitive."""

    def test_clears_readonly_bit_on_file(self, tmp_path: Path) -> None:
        victim = tmp_path / "f.txt"
        victim.write_text("x")
        victim.chmod(0o444)

        force_writable(victim)

        assert not _is_readonly(victim)

    def test_swallows_missing_path(self, tmp_path: Path) -> None:
        """A vanished path (raced deletion) must not raise — best-effort."""
        missing = tmp_path / "does-not-exist"

        force_writable(missing)  # must not raise

    def test_does_not_follow_symlink_to_outside_target(self, tmp_path: Path) -> None:
        """SC-006 negative proof: chmod on a symlink must not touch its target."""
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        target = outside_dir / "secret.txt"
        target.write_text("do not touch")
        target.chmod(0o444)
        target_mode_before = stat.S_IMODE(target.lstat().st_mode)

        managed_dir = tmp_path / "managed"
        managed_dir.mkdir()
        link = managed_dir / "link.txt"
        link.symlink_to(target)

        force_writable(link)

        assert stat.S_IMODE(target.lstat().st_mode) == target_mode_before
        assert target.exists()


class TestSafeUnlink:
    """FR-001/FR-002: read-only file delete succeeds; symlink target is untouched."""

    def test_deletes_readonly_file(self, tmp_path: Path) -> None:
        victim = tmp_path / "f.txt"
        victim.write_text("x")
        victim.chmod(0o444)

        safe_unlink(victim)

        assert not victim.exists()

    def test_deletes_writable_file_without_retry(self, tmp_path: Path) -> None:
        victim = tmp_path / "f.txt"
        victim.write_text("x")

        safe_unlink(victim)

        assert not victim.exists()

    def test_symlink_negative_proof_target_untouched(self, tmp_path: Path) -> None:
        """SC-006, the heart of this WP: deleting a managed symlink whose target
        lives OUTSIDE the managed tree must remove only the link — the target's
        mode and existence must be unchanged (proves no-follow, not just that
        the link is gone)."""
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        target = outside_dir / "secret.txt"
        target.write_text("do not touch")
        target.chmod(0o444)
        target_mode_before = stat.S_IMODE(target.lstat().st_mode)

        managed_dir = tmp_path / "managed"
        managed_dir.mkdir()
        link = managed_dir / "link.txt"
        link.symlink_to(target)

        safe_unlink(link)

        assert not link.exists()
        assert not link.is_symlink()
        assert target.exists()
        assert stat.S_IMODE(target.lstat().st_mode) == target_mode_before


class TestSafeRmdir:
    """FR-001: read-only directory delete succeeds."""

    def test_deletes_readonly_directory(self, tmp_path: Path) -> None:
        victim = tmp_path / "d"
        victim.mkdir()
        victim.chmod(0o555)

        safe_rmdir(victim)

        assert not victim.exists()

    def test_deletes_writable_directory_without_retry(self, tmp_path: Path) -> None:
        victim = tmp_path / "d"
        victim.mkdir()

        safe_rmdir(victim)

        assert not victim.exists()


@pytest.mark.skipif(os.name == "nt", reason="simulated-Windows PermissionError sim is POSIX-only")
class TestSimulatedWindowsPermissionDenied:
    """Simulate Windows' enforce-on-readonly semantics on POSIX (mirrors the
    established pattern in tests/runtime/test_windows_readonly_asset_delete.py)
    to prove the retry path itself — not just that POSIX ignores the mode."""

    def _install_sim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_unlink = Path.unlink
        real_rmdir = Path.rmdir

        def guarded_unlink(self: Path, *args: object, **kwargs: object) -> None:
            if not (self.lstat().st_mode & stat.S_IWRITE):
                raise PermissionError(13, "Permission denied")
            return real_unlink(self, *args, **kwargs)

        def guarded_rmdir(self: Path, *args: object, **kwargs: object) -> None:
            if not (self.lstat().st_mode & stat.S_IWRITE):
                raise PermissionError(13, "Permission denied")
            return real_rmdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", guarded_unlink)
        monkeypatch.setattr(Path, "rmdir", guarded_rmdir)

    def test_safe_unlink_retries_after_permission_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "f.txt"
        victim.write_text("x")
        victim.chmod(0o444)
        self._install_sim(monkeypatch)

        safe_unlink(victim)

        assert not victim.exists()

    def test_safe_rmdir_retries_after_permission_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "d"
        victim.mkdir()
        victim.chmod(0o555)
        self._install_sim(monkeypatch)

        safe_rmdir(victim)

        assert not victim.exists()
