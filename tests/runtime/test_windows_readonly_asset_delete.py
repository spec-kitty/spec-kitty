"""Regression (#4703 cross-OS family): removing a managed asset must succeed on
Windows even though the asset is materialized read-only.

Managed content is written read-only (``0o444`` — see ``_write_asset``'s
``or 0o444`` and agent-skill assets that strip ``0o222``). On Windows
``DeleteFile``/``RemoveDirectory`` REFUSE a read-only target with
``PermissionError``; POSIX ``unlink``/``rmdir`` ignore the mode. So an upgrade /
repair / skill re-install that deletes a stale managed asset crashed on Windows —
the same POSIX-ignores/Windows-enforces divergence as the #4703 lock read.

The Windows semantics are simulated on POSIX by making ``Path.unlink``/``rmdir``
raise ``PermissionError`` on a read-only target. The control test proves the
simulation genuinely breaks a bare delete (i.e. the bug is real); the fix routes
every managed-asset delete through a writable-then-retry helper.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

import specify_cli.runtime.asset_preparation as ap
from specify_cli.core import safe_delete
from specify_cli.tool_surface.operations import FileState, OperationRoot, OwnershipProof, PhysicalEffect

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _install_windows_readonly_delete_sim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate Windows: unlink/rmdir of a read-only path raises PermissionError."""
    real_unlink = Path.unlink
    real_rmdir = Path.rmdir

    def _is_readonly(path: Path) -> bool:
        try:
            return not (path.lstat().st_mode & stat.S_IWRITE)
        except OSError:
            return False

    def guarded_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if _is_readonly(self):
            raise PermissionError(13, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    def guarded_rmdir(self: Path, *args: object, **kwargs: object) -> None:
        if _is_readonly(self):
            raise PermissionError(13, "Permission denied")
        return real_rmdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    monkeypatch.setattr(Path, "rmdir", guarded_rmdir)


def _delete_write(root_dir: Path, relative: str, *, is_dir: bool) -> ap.AssetWrite:
    before = FileState("directory", mode=0o555) if is_dir else FileState("file", sha256=ap.digest(b"x"), mode=0o444)
    effect = PhysicalEffect(
        owner="global_skills",
        phase="global_bootstrap",
        root=OperationRoot("global_skills", "global", root_dir),
        path=relative,
        action="delete",
        before=before,
        after=FileState("absent"),
        reason="prune a retired managed asset",
        ownership=(OwnershipProof("managed_path", "global_skills:asset"),),
        logical_owners=("global_skills",),
    )
    return ap.AssetWrite(effect=effect, content=None)


class TestControlSimulationIsFaithful:
    """The simulation must genuinely break a bare delete, or the fix tests below
    would pass vacuously on POSIX."""

    def test_bare_unlink_of_readonly_file_raises_under_sim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "f.txt"
        victim.write_text("x")
        victim.chmod(0o444)
        _install_windows_readonly_delete_sim(monkeypatch)
        with pytest.raises(PermissionError):
            victim.unlink()

    def test_bare_rmdir_of_readonly_dir_raises_under_sim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "d"
        victim.mkdir()
        victim.chmod(0o555)
        _install_windows_readonly_delete_sim(monkeypatch)
        with pytest.raises(PermissionError):
            victim.rmdir()


class TestWriteAssetDeletesReadOnlyManagedAssets:
    """FR (#4703 family): ``_write_asset``'s delete path must remove a read-only
    managed asset on Windows. RED pre-fix (bare unlink/rmdir under the sim)."""

    def test_delete_readonly_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "sub" / "asset.txt"
        victim.parent.mkdir(parents=True)
        victim.write_text("x")
        victim.chmod(0o444)
        _install_windows_readonly_delete_sim(monkeypatch)

        ap._write_asset(_delete_write(tmp_path, "sub/asset.txt", is_dir=False))
        assert not victim.exists()

    def test_delete_readonly_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        victim = tmp_path / "sub" / "adir"
        victim.mkdir(parents=True)
        victim.chmod(0o555)
        _install_windows_readonly_delete_sim(monkeypatch)

        ap._write_asset(_delete_write(tmp_path, "sub/adir", is_dir=True))
        assert not victim.exists()


class TestSafeDeleteHelpers:
    """The helper mechanism, exercised directly for both owners.

    WP04: ``asset_preparation`` no longer carries its own
    ``_force_writable``/``_safe_unlink``/``_safe_rmdir`` copy -- it routes
    onto the canonical ``specify_cli.core.safe_delete`` util (WP02), which
    ``_write_asset`` (exercised above) now calls directly. This proves the
    module-level names asset_preparation itself binds (``safe_unlink``)
    resolve to that same canonical implementation.
    """

    def test_asset_preparation_uses_the_canonical_safe_unlink(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ap.safe_unlink is safe_delete.safe_unlink
        assert ap.safe_rmdir is safe_delete.safe_rmdir

        victim = tmp_path / "f"
        victim.write_text("x")
        victim.chmod(0o444)
        _install_windows_readonly_delete_sim(monkeypatch)
        ap.safe_unlink(victim)
        assert not victim.exists()

    def test_installer_safe_unlink_and_rmdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.skills import installer

        f = tmp_path / "f"
        f.write_text("x")
        f.chmod(0o444)
        d = tmp_path / "d"
        d.mkdir()
        d.chmod(0o555)
        _install_windows_readonly_delete_sim(monkeypatch)
        installer._safe_unlink(f)
        installer._safe_rmdir(d)
        assert not f.exists()
        assert not d.exists()
