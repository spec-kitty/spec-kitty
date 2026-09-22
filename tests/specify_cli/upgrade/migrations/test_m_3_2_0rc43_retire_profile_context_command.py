"""ATDD for the ownership-gated profile-context retirement (WP07, census row 8).

Both directions of the asset-preservation guard are pinned for the 3.2.0rc43
forward migration that removes stale ``spec-kitty.profile-context.md`` copies:

* **preserve** (RED on base ``32cfc272ee``) — a user-authored file reusing the
  retired command filename with no version marker is unprovable, so it SURVIVES
  in place with a diagnostic. On base the migration unlinks it by name → RED.
* **owned-delete** (GREEN on base) — a marker-bearing shipped command IS still
  removed, proving the routing is non-vacuous.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_2_0rc43_retire_profile_context_command import (
    RetireProfileContextCommandMigration,
)

pytestmark = pytest.mark.unit

_MARKER = b"<!-- spec-kitty-command-version: 4.0.0 -->\n"
_DEST_REL = ".claude/commands/spec-kitty.profile-context.md"


def _seed(project: Path, rel: str, content: bytes) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_user_authored_profile_context_survives_in_place(tmp_path: Path) -> None:
    """Unprovable name collision (no marker) is preserved, not deleted."""
    user_bytes = b"# my own profile-context notes, not the shipped command\n"
    path = _seed(tmp_path, _DEST_REL, user_bytes)

    result = RetireProfileContextCommandMigration().apply(tmp_path)

    assert result.success
    assert path.exists()
    assert path.read_bytes() == user_bytes
    assert str(path) in result.preserved_paths
    assert any("Preserved" in warning for warning in result.warnings)


def test_package_owned_profile_context_is_removed(tmp_path: Path) -> None:
    """A marker-bearing shipped command is proven-owned and still removed."""
    path = _seed(tmp_path, _DEST_REL, _MARKER + b"# shipped profile-context body\n")

    result = RetireProfileContextCommandMigration().apply(tmp_path)

    assert result.success
    assert not path.exists()
    assert any("Removed retired" in change for change in result.changes_made)
    assert not result.preserved_paths
