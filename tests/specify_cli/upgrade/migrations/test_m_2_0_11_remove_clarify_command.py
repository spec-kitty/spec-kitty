"""ATDD for the ownership-gated clarify-command retirement (WP07, census row 5).

Both directions of the asset-preservation guard are pinned here:

* **preserve** (RED on base ``32cfc272ee``) — a user-authored file that collides
  by name with the retired ``spec-kitty.clarify*`` command but carries no version
  marker is unprovable, so it SURVIVES in place with a diagnostic. On base the
  migration unlinks by name and the file is destroyed → this test is RED.
* **owned-delete** (GREEN on base) — a genuinely package-owned command (carrying
  the ``<!-- spec-kitty-command-version:`` marker) IS still removed, proving the
  routing is non-vacuous (a preserve-everything guard would fail this).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_2_0_11_remove_clarify_command import (
    RemoveClarifyCommandMigration,
)

pytestmark = pytest.mark.unit

_MARKER = b"<!-- spec-kitty-command-version: 4.0.0 -->\n"
_CLARIFY_REL = ".claude/commands/spec-kitty.clarify.md"


def _seed(project: Path, rel: str, content: bytes) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_user_authored_clarify_collision_survives(tmp_path: Path) -> None:
    """Unprovable name collision (no marker) is preserved, not deleted."""
    user_bytes = b"# my own clarify helper, not the shipped command\n"
    path = _seed(tmp_path, _CLARIFY_REL, user_bytes)

    result = RemoveClarifyCommandMigration().apply(tmp_path)

    assert result.success
    assert path.exists()
    assert path.read_bytes() == user_bytes
    assert str(path) in result.preserved_paths
    assert any("Preserved" in warning for warning in result.warnings)


def test_package_owned_clarify_command_is_removed(tmp_path: Path) -> None:
    """A marker-bearing shipped command is proven-owned and still removed."""
    path = _seed(tmp_path, _CLARIFY_REL, _MARKER + b"# shipped clarify body\n")

    result = RemoveClarifyCommandMigration().apply(tmp_path)

    assert result.success
    assert not path.exists()
    assert any(change.startswith("Removed:") for change in result.changes_made)
    assert not result.preserved_paths
