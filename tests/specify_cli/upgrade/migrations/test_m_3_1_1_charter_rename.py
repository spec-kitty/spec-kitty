"""WP04 (#4862 + borderline B1) — the charter-rename migration must not destroy
governance files it cannot prove the package owns.

ATDD, red-first (contract C4 US3 + data-model census row 9 / borderline B1):

* **preserve** (RED on base ``32cfc272ee`` → GREEN on the WP04 fix) — a
  "Skipped" collision file, a mission-specific ``constitution/`` dir, and a
  stale ``memory/constitution.md`` each survive in a recoverable backup instead
  of being destroyed by the residual/legacy removal. On base the raw
  ``shutil.rmtree`` / ``unlink`` destroys them with no backup, so these fail.
* **owned-delete / no-collision** (GREEN on base and fix) — non-vacuity anchors:
  a marker-bearing owned collision is removed (not archived), and a no-collision
  residual dir is still cleaned up (US3 scenario 2).

The suite imports only the migration (the ``asset_preservation`` guard does not
exist on base), so the same file runs on base to capture the RED evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_1_1_charter_rename import (
    CharterRenameMigration,
)

pytestmark = pytest.mark.fast

# A marker-bearing file is package-owned; the ``CanonicalContentProver`` proves
# it and the guard removes it directly (no archive). Governance payloads never
# carry this marker, which is why they preserve.
_VERSION_MARKER = "<!-- spec-kitty-command-version: 1 -->"


@pytest.fixture
def migration() -> CharterRenameMigration:
    return CharterRenameMigration()


def _find_backup_copy(kittify: Path, needle: str, *, original: Path) -> Path | None:
    """Return a recoverable copy of ``needle`` living somewhere OTHER than the
    original (doomed) location — i.e. an archived backup — or ``None``."""
    for candidate in kittify.rglob("*"):
        if not candidate.is_file() or candidate == original:
            continue
        try:
            if candidate.read_text(encoding="utf-8") == needle:
                return candidate
        except (OSError, UnicodeDecodeError):
            continue
    return None


class TestSkippedCollisionSurvives:
    """US3 / #4862: a same-named collision reported "Skipped" must survive."""

    def test_skipped_collision_file_is_preserved_not_destroyed(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """RED on base: the residual ``rmtree(constitution_dir)`` destroys the
        colliding constitution-side file with no backup. GREEN on fix: it is
        archived to a recoverable backup with a diagnostic and the residual dir
        is still removed."""
        kittify = tmp_path / ".kittify"
        payload = "GOVERNANCE-SIDE-PAYLOAD-XYZ"
        original = kittify / "constitution" / "governance.yaml"
        original.parent.mkdir(parents=True)
        original.write_text(payload, encoding="utf-8")
        charter_file = kittify / "charter" / "governance.yaml"
        charter_file.parent.mkdir(parents=True)
        charter_file.write_text("CHARTER-SIDE-PAYLOAD", encoding="utf-8")

        result = migration.apply(tmp_path)

        assert result.success
        # The charter-side file is untouched.
        assert charter_file.read_text(encoding="utf-8") == "CHARTER-SIDE-PAYLOAD"
        # The constitution-side bytes survive in a recoverable backup (RED point).
        backup = _find_backup_copy(kittify, payload, original=original)
        assert backup is not None, "constitution-side 'Skipped' payload was destroyed"
        # A diagnostic names the preserved file.
        assert any("governance.yaml" in w for w in result.warnings)
        # The residual dir is still removed (legitimate cleanup).
        assert not (kittify / "constitution").exists()

    def test_no_collision_residual_dir_still_removed(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """US3 scenario 2 (GREEN on base and fix): with no collision every file
        merges and the now-empty residual dir is still removed."""
        kittify = tmp_path / ".kittify"
        (kittify / "constitution").mkdir(parents=True)
        (kittify / "constitution" / "extra.yaml").write_text("extra", encoding="utf-8")
        (kittify / "charter").mkdir(parents=True)
        (kittify / "charter" / "charter.md").write_text("current", encoding="utf-8")

        result = migration.apply(tmp_path)

        assert result.success
        assert (kittify / "charter" / "extra.yaml").exists()
        assert not (kittify / "constitution").exists()

    def test_marker_bearing_collision_is_removed_not_archived(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """Owned-delete anchor (GREEN on base and fix): a colliding file that
        carries the package version marker is package-owned, so it is removed
        directly — never archived — which stops a preserve-everything guard from
        passing."""
        kittify = tmp_path / ".kittify"
        marker_body = f"{_VERSION_MARKER}\nowned generated content\n"
        original = kittify / "constitution" / "governance.yaml"
        original.parent.mkdir(parents=True)
        original.write_text(marker_body, encoding="utf-8")
        charter_file = kittify / "charter" / "governance.yaml"
        charter_file.parent.mkdir(parents=True)
        charter_file.write_text("CHARTER-SIDE-PAYLOAD", encoding="utf-8")

        result = migration.apply(tmp_path)

        assert result.success
        assert charter_file.read_text(encoding="utf-8") == "CHARTER-SIDE-PAYLOAD"
        assert not (kittify / "constitution").exists()
        # Owned content is deleted, not archived: no backup copy is created.
        assert _find_backup_copy(kittify, marker_body, original=original) is None


class TestB1MissionConstitutionPreserved:
    """Borderline B1 (:148): a mission-specific ``constitution/`` dir preserves."""

    def test_mission_constitution_is_preserved_unless_proven(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """RED on base: ``rmtree(mission_constitution)`` destroys the content
        with no backup. GREEN on fix: it is archived recoverably before the guard
        removes the legacy dir."""
        kittify = tmp_path / ".kittify"
        payload = "MISSION-GOVERNANCE-PAYLOAD-QRS"
        original = kittify / "missions" / "software-dev" / "constitution" / "local.md"
        original.parent.mkdir(parents=True)
        original.write_text(payload, encoding="utf-8")

        result = migration.apply(tmp_path)

        assert result.success
        # Legacy dir cleaned up ...
        assert not (kittify / "missions" / "software-dev" / "constitution").exists()
        # ... but the bytes survive in a recoverable backup (RED point).
        assert _find_backup_copy(kittify, payload, original=original) is not None


class TestB1StaleMemoryConstitutionPreserved:
    """Borderline B1 (:161): a stale ``memory/constitution.md`` preserves.

    Seed fix (binding correction T013): ``charter/charter.md`` MUST also exist,
    else the migration takes the MOVE branch (no loss) and the test is falsely
    GREEN. With charter.md present the STALE branch (:161 unlink) is exercised.
    """

    def test_stale_memory_constitution_is_preserved_unless_proven(self, tmp_path: Path, migration: CharterRenameMigration) -> None:
        """RED on base: ``memory_constitution.unlink()`` destroys the stale file
        with no backup. GREEN on fix: archived recoverably before removal."""
        kittify = tmp_path / ".kittify"
        payload = "STALE-MEMORY-GOVERNANCE-PAYLOAD-TUV"
        original = kittify / "memory" / "constitution.md"
        original.parent.mkdir(parents=True)
        original.write_text(payload, encoding="utf-8")
        # Force the STALE branch: charter/charter.md already exists.
        charter_md = kittify / "charter" / "charter.md"
        charter_md.parent.mkdir(parents=True)
        charter_md.write_text("current charter", encoding="utf-8")

        result = migration.apply(tmp_path)

        assert result.success
        # Stale file removed from its live location ...
        assert not original.exists()
        # ... but recoverable in a backup (RED point).
        assert _find_backup_copy(kittify, payload, original=original) is not None
        # The existing charter is untouched.
        assert charter_md.read_text(encoding="utf-8") == "current charter"
