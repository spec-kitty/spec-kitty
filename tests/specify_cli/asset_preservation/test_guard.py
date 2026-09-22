"""Unit tests for the guard decision surface (performs delete on owned;
preserves/archives otherwise)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.asset_preservation import guard_destructive_removal
from specify_cli.tool_surface.operations import OwnershipProof

pytestmark = pytest.mark.unit


class _AlwaysOwned:
    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:  # noqa: ARG002
        return OwnershipProof("managed_path", "test:owned")


class _NeverOwned:
    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:  # noqa: ARG002
        return None


def _seed(project: Path, rel: str, content: bytes = b"x") -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --- owned ⇒ the guard removes ---------------------------------------------


def test_owned_file_is_removed_by_the_guard(tmp_path: Path) -> None:
    path = _seed(tmp_path, ".kittify/templates/x.md")
    verdict = guard_destructive_removal(path, tmp_path, prover=_AlwaysOwned())
    assert verdict.owned is True
    assert verdict.proof is not None
    assert not path.exists()


def test_owned_tree_is_removed_by_the_guard(tmp_path: Path) -> None:
    d = tmp_path / ".kittify" / "templates"
    _seed(tmp_path, ".kittify/templates/a.md")
    _seed(tmp_path, ".kittify/templates/sub/b.md")
    verdict = guard_destructive_removal(d, tmp_path, prover=_AlwaysOwned(), is_tree=True)
    assert verdict.owned is True
    assert not d.exists()


def test_owned_dry_run_does_not_remove(tmp_path: Path) -> None:
    path = _seed(tmp_path, ".kittify/templates/x.md")
    verdict = guard_destructive_removal(path, tmp_path, prover=_AlwaysOwned(), dry_run=True)
    assert verdict.owned is True
    assert path.exists()


# --- unprovable ⇒ preserve (never delete) ----------------------------------


def test_unprovable_preserved_in_place_when_parent_survives(tmp_path: Path) -> None:
    path = _seed(tmp_path, ".kittify/command-templates/custom.md", b"user bytes")
    verdict = guard_destructive_removal(path, tmp_path, prover=_NeverOwned())
    assert verdict.owned is False
    assert path.exists()
    assert path.read_bytes() == b"user bytes"
    assert verdict.preserved_path == path
    assert verdict.backup_path is None
    assert "Preserved" in verdict.diagnostic


def test_unprovable_dir_preserved_in_place(tmp_path: Path) -> None:
    d = tmp_path / ".claude" / "skills" / "spec-kitty.advise"
    _seed(tmp_path, ".claude/skills/spec-kitty.advise/SKILL.md", b"user skill")
    verdict = guard_destructive_removal(d, tmp_path, prover=_NeverOwned(), is_tree=True)
    assert verdict.owned is False
    assert (d / "SKILL.md").read_bytes() == b"user skill"


def test_unprovable_archived_when_parent_removed(tmp_path: Path) -> None:
    path = _seed(tmp_path, ".kittify/constitution/skipped.md", b"skipped governance")
    backup_parent = tmp_path / ".kittify"
    verdict = guard_destructive_removal(path, tmp_path, prover=_NeverOwned(), backup_parent=backup_parent)
    assert verdict.owned is False
    assert not path.exists()  # original removed after archiving
    assert verdict.backup_path is not None
    assert verdict.backup_path.exists()
    assert verdict.backup_path.read_bytes() == b"skipped governance"
    assert "archived" in verdict.diagnostic


def test_unprovable_archive_dry_run_preserves_original(tmp_path: Path) -> None:
    path = _seed(tmp_path, ".kittify/constitution/skipped.md", b"gov")
    verdict = guard_destructive_removal(path, tmp_path, prover=_NeverOwned(), backup_parent=tmp_path / ".kittify", dry_run=True)
    assert verdict.owned is False
    assert path.exists()
    assert verdict.backup_path is None


def test_absent_path_is_a_noop(tmp_path: Path) -> None:
    verdict = guard_destructive_removal(tmp_path / "does-not-exist", tmp_path, prover=_AlwaysOwned())
    assert verdict.owned is False
    assert verdict.reason == "absent"


# --- owned but read-only-attributed ⇒ the guard still removes (regression) -


def test_owned_read_only_file_is_removed_by_the_guard(tmp_path: Path) -> None:
    """A package-owned file whose containing directory was installed without
    the write bit (e.g. a read-only package install) must still be removed —
    ownership is proven, so the guard retries after making it writable rather
    than raising."""
    parent = tmp_path / "readonly-parent"
    parent.mkdir()
    path = parent / "x.md"
    path.write_bytes(b"x")
    parent.chmod(0o555)  # r-xr-xr-x: no write bit, blocks unlink of children
    try:
        verdict = guard_destructive_removal(path, tmp_path, prover=_AlwaysOwned())
    finally:
        parent.chmod(0o755)
    assert verdict.owned is True
    assert not path.exists()


def test_owned_read_only_tree_is_removed_by_the_guard(tmp_path: Path) -> None:
    """A package-owned directory that is itself read-only (and carries a
    read-only file inside) must still be removed in full — ownership is
    proven, so the guard retries the rmtree after making the blocking members
    writable rather than raising."""
    d = tmp_path / ".kittify" / "templates"
    d.mkdir(parents=True)
    member = d / "a.md"
    member.write_bytes(b"a")
    member.chmod(0o444)  # read-only file
    d.chmod(0o555)  # read-only dir: blocks unlinking members inside it
    try:
        verdict = guard_destructive_removal(d, tmp_path, prover=_AlwaysOwned(), is_tree=True)
    finally:
        if d.exists():
            d.chmod(0o755)
    assert verdict.owned is True
    assert not d.exists()
