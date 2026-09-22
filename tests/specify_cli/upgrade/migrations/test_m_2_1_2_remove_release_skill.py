"""ATDD for the ownership-gated release-skill retirement (WP07, census row 6).

The release skill is a managed-skills *directory*, so it routes through
``ManifestProver`` with an external ``backup_parent`` (the directory is removed,
so an unprovable collision is archived verbatim before teardown rather than left
in place):

* **preserve** (RED on base ``32cfc272ee``) — a user-authored ``release`` skill
  with no managing manifest entry is unprovable, so its bytes SURVIVE in a
  recoverable backup with a diagnostic. On base the migration ``rmtree``s the
  directory by name with no backup → this test is RED.
* **owned-delete** (GREEN on base) — a manifest-owned skill (recorded content
  hash matches the bytes on disk, ``copy`` delivery) IS still removed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    save_manifest,
)
from specify_cli.upgrade.migrations.m_2_1_2_remove_release_skill import (
    RemoveReleaseSkillMigration,
)

pytestmark = pytest.mark.unit

_SKILL_DIR_REL = ".claude/skills/release"
_SKILL_FILE_REL = f"{_SKILL_DIR_REL}/SKILL.md"
_NOW = "2026-01-01T00:00:00+00:00"


def _seed(project: Path, rel: str, content: bytes) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _seed_managed_manifest(project: Path, rel: str, *, content_hash: str) -> None:
    manifest = ManagedSkillManifest(
        entries=[
            ManagedFileEntry(
                skill_name="release",
                source_file="SKILL.md",
                installed_path=rel,
                installation_class="native-root-required",
                agent_key="claude",
                content_hash=content_hash,
                installed_at=_NOW,
                delivery_mode="copy",
            )
        ]
    )
    save_manifest(manifest, project)


def test_user_authored_release_skill_survives_as_backup(tmp_path: Path) -> None:
    """Unprovable release-skill collision (no manifest) is archived, not lost."""
    user_bytes = b"# my own release checklist skill\n"
    _seed(tmp_path, _SKILL_FILE_REL, user_bytes)

    result = RemoveReleaseSkillMigration().apply(tmp_path)

    assert result.success
    assert not (tmp_path / _SKILL_DIR_REL).exists()  # original location cleared
    assert result.preserved_paths  # archived to a recoverable backup
    backups = list((tmp_path / ".kittify").rglob("SKILL.md"))
    assert backups, "expected the user's skill bytes archived under .kittify"
    assert any(candidate.read_bytes() == user_bytes for candidate in backups)
    assert any("Preserved" in warning for warning in result.warnings)


def test_manifest_owned_release_skill_is_removed(tmp_path: Path) -> None:
    """A manifest-owned release skill is proven-owned and still removed."""
    member = _seed(tmp_path, _SKILL_FILE_REL, b"shipped release skill body\n")
    _seed_managed_manifest(tmp_path, _SKILL_FILE_REL, content_hash=compute_content_hash(member))

    result = RemoveReleaseSkillMigration().apply(tmp_path)

    assert result.success
    assert not (tmp_path / _SKILL_DIR_REL).exists()
    assert not result.preserved_paths
    assert any("Removed" in change for change in result.changes_made)
