"""Scope: B3 borderline (WP08/T022) — the ensure-missions incomplete-repair
path must ARCHIVE a co-located user/untracked member before the structurally
required ``rmtree``+``copytree`` recopy, so no user-authored content is lost
(NFR-006). ``copytree(dirs_exist_ok=False)`` needs the dest absent, so
in-place preserve is impossible here; the guard archives OUT to an external
backup first, then the legitimate recopy proceeds.

Mock-boundary unit test: ``_find_package_missions`` is stubbed with a
controlled source tree; no real package I/O, no real git.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_6_7_ensure_missions import (
    EnsureMissionsMigration,
)

pytestmark = pytest.mark.unit


def _make_package_missions(root: Path) -> Path:
    """A stand-in package missions source with every REQUIRED_MISSION complete."""
    pkg = root / "pkg-missions"
    for name in EnsureMissionsMigration.REQUIRED_MISSIONS:
        mission = pkg / name
        mission.mkdir(parents=True)
        (mission / "mission.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    return pkg


def _archived_copies(project: Path, filename: str) -> list[Path]:
    """Every copy of ``filename`` living under a guard ``.backup-*`` archive dir."""
    return [candidate for candidate in project.rglob(filename) if any(part.startswith(".backup-") for part in candidate.parts)]


def test_incomplete_mission_user_member_is_archived_then_recopied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An incomplete REQUIRED_MISSION dir holding a user member: the member is
    archived verbatim to an EXTERNAL backup, then the mission is recopied fresh.

    RED on base ``32cfc272ee`` (the raw ``rmtree`` wipes the member with no
    archive); GREEN once the removal is routed through the asset-preservation
    guard with an external ``backup_parent``.
    """
    # Arrange
    project = tmp_path / "project"
    missions_dir = project / ".kittify" / "missions"
    missions_dir.mkdir(parents=True)

    # `research` is already complete -> the copy loop `continue`s past it,
    # isolating this test to the incomplete-repair branch for `software-dev`.
    research = missions_dir / "research"
    research.mkdir()
    (research / "mission.yaml").write_text("name: research\n", encoding="utf-8")

    # `software-dev` is INCOMPLETE (no mission.yaml) but co-locates a
    # user/untracked member alongside whatever package remnants remain.
    incomplete = missions_dir / "software-dev"
    incomplete.mkdir()
    user_member = incomplete / "my-custom-notes.md"
    user_member.write_text("USER AUTHORED CONTENT", encoding="utf-8")

    pkg = _make_package_missions(tmp_path)
    monkeypatch.setattr(
        EnsureMissionsMigration,
        "_find_package_missions",
        lambda self: pkg,  # noqa: ARG005 - bound-method stub ignores self
    )

    migration = EnsureMissionsMigration()

    # Assumption check
    assert not (incomplete / "mission.yaml").exists(), "must start incomplete"
    assert user_member.exists(), "user member must be seeded"

    # Act
    result = migration.apply(project, dry_run=False)

    # Assert
    assert result.success, result.errors
    # The mission is recopied fresh from the package (now complete) ...
    assert (incomplete / "mission.yaml").read_text(encoding="utf-8") == "name: software-dev\n"
    # ... and the user member survives verbatim in an EXTERNAL backup archive.
    archived = _archived_copies(project, "my-custom-notes.md")
    assert archived, "user member must be archived before the rmtree+copytree recopy"
    assert archived[0].read_text(encoding="utf-8") == "USER AUTHORED CONTENT"
    # The archive lives outside the recopied mission dir (it survived the rmtree).
    assert incomplete not in archived[0].parents


def test_complete_mission_is_left_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A REQUIRED_MISSION that already carries mission.yaml is skipped entirely
    (no removal, no archive) — the guard route only fires on the repair path."""
    # Arrange
    project = tmp_path / "project"
    missions_dir = project / ".kittify" / "missions"
    missions_dir.mkdir(parents=True)
    for name in EnsureMissionsMigration.REQUIRED_MISSIONS:
        mission = missions_dir / name
        mission.mkdir()
        (mission / "mission.yaml").write_text("name: user\n", encoding="utf-8")

    pkg = _make_package_missions(tmp_path)
    monkeypatch.setattr(
        EnsureMissionsMigration,
        "_find_package_missions",
        lambda self: pkg,  # noqa: ARG005 - bound-method stub ignores self
    )

    migration = EnsureMissionsMigration()

    # Act
    result = migration.apply(project, dry_run=False)

    # Assert
    assert result.success, result.errors
    # User content preserved; nothing archived because nothing was removed.
    assert (missions_dir / "software-dev" / "mission.yaml").read_text(encoding="utf-8") == "name: user\n"
    assert not _archived_copies(project, "mission.yaml")
