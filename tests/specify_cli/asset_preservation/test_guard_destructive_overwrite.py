"""Unit tests for ``guard_destructive_overwrite`` — the shared overwrite
decision primitive (charter L463-479 truth table, WP01 T001/#4921)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.asset_preservation import guard_destructive_overwrite
from specify_cli.tool_surface.operations import OwnershipProof

pytestmark = pytest.mark.unit


class _AlwaysOwned:
    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:  # noqa: ARG002
        return OwnershipProof("managed_path", "test:owned")


class _NeverOwned:
    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:  # noqa: ARG002
        return None


def _seed(project: Path, rel: str, content: bytes = b"user bytes") -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# --- absent destination -----------------------------------------------------


def test_absent_non_substantive_replacement_refuses(tmp_path: Path) -> None:
    """Never fabricate an empty file at an absent destination."""
    dest = tmp_path / "does-not-exist.md"
    verdict = guard_destructive_overwrite(dest, tmp_path, replacement_substantive=False, authorized=True)
    assert verdict.proceed is False
    assert verdict.backup_path is None


def test_absent_substantive_replacement_proceeds(tmp_path: Path) -> None:
    dest = tmp_path / "does-not-exist.md"
    verdict = guard_destructive_overwrite(dest, tmp_path, replacement_substantive=True, authorized=False)
    assert verdict.proceed is True
    assert verdict.backup_path is None


# --- existing, unproven (user) destination ----------------------------------


def test_existing_user_non_substantive_refuses_even_when_authorized(tmp_path: Path) -> None:
    """Never truncate to empty, even under --force (authorized=True)."""
    dest = _seed(tmp_path, "brief.md")
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=False,
        authorized=True,
        prover=_NeverOwned(),
    )
    assert verdict.proceed is False
    assert dest.read_bytes() == b"user bytes"


def test_existing_user_substantive_unauthorized_refuses(tmp_path: Path) -> None:
    dest = _seed(tmp_path, "brief.md")
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=False,
        prover=_NeverOwned(),
    )
    assert verdict.proceed is False
    assert dest.read_bytes() == b"user bytes"


def test_existing_user_substantive_authorized_proceeds(tmp_path: Path) -> None:
    dest = _seed(tmp_path, "brief.md")
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=True,
        prover=_NeverOwned(),
    )
    assert verdict.proceed is True
    # No backup_parent supplied -> no archive performed, original untouched.
    assert verdict.backup_path is None
    assert dest.read_bytes() == b"user bytes"


def test_existing_user_substantive_authorized_archives_when_backup_parent_given(
    tmp_path: Path,
) -> None:
    dest = _seed(tmp_path, "brief.md", b"original user bytes")
    backup_parent = tmp_path / "backups"
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=True,
        prover=_NeverOwned(),
        backup_parent=backup_parent,
    )
    assert verdict.proceed is True
    assert verdict.backup_path is not None
    assert verdict.backup_path.read_bytes() == b"original user bytes"
    # archive_into is copy-only: the original is left in place for the
    # caller to overwrite.
    assert dest.read_bytes() == b"original user bytes"


def test_existing_no_prover_supplied_treated_as_unproven(tmp_path: Path) -> None:
    """Omitting ``prover`` entirely must not be treated as ownership proof."""
    dest = _seed(tmp_path, "brief.md")
    verdict = guard_destructive_overwrite(dest, tmp_path, replacement_substantive=True, authorized=False)
    assert verdict.proceed is False


# --- existing, proven package-owned destination -----------------------------


def test_existing_package_owned_proceeds_when_substantive(tmp_path: Path) -> None:
    dest = _seed(tmp_path, "template.md")
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=False,
        prover=_AlwaysOwned(),
    )
    assert verdict.proceed is True
    assert "package-owned" in verdict.reason


def test_existing_package_owned_no_backup_even_with_backup_parent(tmp_path: Path) -> None:
    """A proven-owned destination is package content, not user bytes — no
    archive is needed before the caller's own overwrite."""
    dest = _seed(tmp_path, "template.md")
    verdict = guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=False,
        prover=_AlwaysOwned(),
        backup_parent=tmp_path / "backups",
    )
    assert verdict.proceed is True
    assert verdict.backup_path is None


# --- purity: the guard never writes the replacement content itself ---------


def test_guard_never_writes_replacement_content(tmp_path: Path) -> None:
    """The guard is a pure decision surface — it never writes the new bytes,
    only optionally archives the old ones (mirrors guard_destructive_removal)."""
    dest = _seed(tmp_path, "brief.md", b"original")
    guard_destructive_overwrite(
        dest,
        tmp_path,
        replacement_substantive=True,
        authorized=True,
        prover=_NeverOwned(),
    )
    assert dest.read_bytes() == b"original"


def test_symlink_destination_treated_as_existing(tmp_path: Path) -> None:
    real = _seed(tmp_path, "real.md")
    link = tmp_path / "link.md"
    link.symlink_to(real)
    verdict = guard_destructive_overwrite(
        link,
        tmp_path,
        replacement_substantive=True,
        authorized=False,
        prover=_NeverOwned(),
    )
    assert verdict.proceed is False
