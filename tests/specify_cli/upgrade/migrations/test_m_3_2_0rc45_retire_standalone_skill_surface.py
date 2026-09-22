"""Tests for retiring stale standalone governance skill surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills import manifest_store
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    load_manifest,
    save_manifest,
)
from specify_cli.skills.manifest_store import ManifestEntry, SkillsManifest
from specify_cli.skills.retired import RETIRED_STANDALONE_SKILL_NAMES
from specify_cli.upgrade.migrations.m_3_2_0rc45_retire_standalone_skill_surface import (
    RetireStandaloneSkillSurfaceMigration,
)

pytestmark = [pytest.mark.fast]

_HASH = "a" * 64
_INSTALLED_AT = "2026-01-01T00:00:00+00:00"
_VERSION = "3.2.0rc45"

_KNOWN_ROOTS = (".agents/skills", ".claude/skills", ".github/skills")


def _retired_name() -> str:
    return next(iter(RETIRED_STANDALONE_SKILL_NAMES))


def _write_skill(root: Path, name: str, content: str = "# skill\n") -> Path:
    skill = root / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(content, encoding="utf-8")
    return skill


def _managed_manifest(*entries: ManagedFileEntry) -> ManagedSkillManifest:
    return ManagedSkillManifest(
        created_at=_INSTALLED_AT,
        updated_at=_INSTALLED_AT,
        spec_kitty_version=_VERSION,
        entries=list(entries),
    )


def _managed_entry(*, skill_name: str, installed_path: str, content_hash: str) -> ManagedFileEntry:
    return ManagedFileEntry(
        skill_name=skill_name,
        source_file="SKILL.md",
        installed_path=installed_path,
        installation_class="shared-root-capable",
        agent_key="codex",
        content_hash=content_hash,
        installed_at=_INSTALLED_AT,
        delivery_mode="copy",
    )


def test_detects_retired_skill_surface_in_known_project_roots(tmp_path: Path) -> None:
    retired_name = _retired_name()
    _write_skill(tmp_path / ".agents" / "skills", retired_name)

    assert RetireStandaloneSkillSurfaceMigration().detect(tmp_path) is True


def test_apply_preserves_unmanifested_retired_skill_collisions(tmp_path: Path) -> None:
    """#4859 preserve-direction (RED on base 32cfc272ee, GREEN on this fix).

    An unmanifested ``spec-kitty.advise`` skill carrying distinctive user bytes is
    NOT package-owned — a shared basename is never ownership proof — so it SURVIVES
    in place and a diagnostic names it. On base the name-only delete loop destroys
    it, which is the #4859 repro.
    """
    retired_name = _retired_name()
    distinctive = "# user-authored advise skill\nkeep-me-42\n"
    active = _write_skill(tmp_path / ".agents" / "skills", "spec-kitty")
    survivors = []
    for root_rel in _KNOWN_ROOTS:
        root = tmp_path / Path(root_rel)
        survivors.append(_write_skill(root, retired_name, content=distinctive))
        _write_skill(root, "custom-skill")

    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path)

    assert result.success is True
    for skill in survivors:
        assert skill.is_file()
        assert skill.read_text(encoding="utf-8") == distinctive
    diagnostics = "\n".join(result.warnings)
    for root_rel in _KNOWN_ROOTS:
        assert f"{root_rel}/{retired_name}" in diagnostics
    assert any("not package-owned" in warning for warning in result.warnings)
    for root_rel in _KNOWN_ROOTS:
        assert (tmp_path / Path(root_rel) / "custom-skill" / "SKILL.md").is_file()
    assert active.is_file()


def test_apply_removes_manifest_owned_retired_skill(tmp_path: Path) -> None:
    """Owned-delete anchor (GREEN on base and on fix; proves non-vacuity).

    A genuinely package-owned retired skill — a managed-manifest entry whose
    recorded ``content_hash`` matches the current on-disk bytes under copy
    delivery — IS removed and its manifest entry pruned. Without this a
    preserve-everything guard would pass all #4859 acceptance.
    """
    retired_name = _retired_name()
    skill = _write_skill(tmp_path / ".agents" / "skills", retired_name, content="# package-owned advise\n")
    installed_rel = f".agents/skills/{retired_name}/SKILL.md"
    save_manifest(
        _managed_manifest(
            _managed_entry(
                skill_name=retired_name,
                installed_path=installed_rel,
                content_hash=compute_content_hash(skill),
            ),
        ),
        tmp_path,
    )

    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path)

    assert result.success is True
    assert not skill.exists()
    assert not skill.parent.exists()
    assert any("Removed retired skill surface" in change for change in result.changes_made)
    remaining = load_manifest(tmp_path)
    assert remaining is not None
    assert remaining.entries == []


def test_apply_preserves_drifted_hash_manifested_skill(tmp_path: Path) -> None:
    """Fail-closed toward user edits (RED on base 32cfc272ee, GREEN on this fix).

    A manifest entry exists, but the on-disk bytes have drifted from the recorded
    ``content_hash`` — the user edited the file. Ownership is unprovable, so the
    skill is preserved in place and its manifest entry is kept. On base the
    name-only loop deletes it and prunes the entry regardless of the hash.
    """
    retired_name = _retired_name()
    edited = "# user-edited advise\n"
    skill = _write_skill(tmp_path / ".agents" / "skills", retired_name, content=edited)
    installed_rel = f".agents/skills/{retired_name}/SKILL.md"
    save_manifest(
        _managed_manifest(
            _managed_entry(
                skill_name=retired_name,
                installed_path=installed_rel,
                content_hash=f"sha256:{_HASH}",
            ),
        ),
        tmp_path,
    )

    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path)

    assert result.success is True
    assert skill.is_file()
    assert skill.read_text(encoding="utf-8") == edited
    assert any("not package-owned" in warning for warning in result.warnings)
    remaining = load_manifest(tmp_path)
    assert remaining is not None
    assert [entry.installed_path for entry in remaining.entries] == [installed_rel]


def test_apply_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    retired_name = _retired_name()
    stale = _write_skill(tmp_path / ".agents" / "skills", retired_name)

    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert any("Would remove retired skill surface" in change for change in result.changes_made)
    assert stale.is_file()


def test_apply_prunes_managed_and_command_manifests(tmp_path: Path) -> None:
    retired_name = _retired_name()
    stale_rel = f".agents/skills/{retired_name}/SKILL.md"
    current_rel = ".agents/skills/spec-kitty.specify/SKILL.md"

    managed = _managed_manifest(
        _managed_entry(skill_name=retired_name, installed_path=stale_rel, content_hash=f"sha256:{_HASH}"),
        _managed_entry(
            skill_name="spec-kitty",
            installed_path=".agents/skills/spec-kitty/SKILL.md",
            content_hash=f"sha256:{_HASH}",
        ),
    )
    save_manifest(managed, tmp_path)

    command_manifest = SkillsManifest(
        entries=[
            ManifestEntry(
                path=stale_rel,
                content_hash=_HASH,
                agents=("codex",),
                installed_at=_INSTALLED_AT,
                spec_kitty_version=_VERSION,
            ),
            ManifestEntry(
                path=current_rel,
                content_hash=_HASH,
                agents=("codex",),
                installed_at=_INSTALLED_AT,
                spec_kitty_version=_VERSION,
            ),
        ]
    )
    manifest_store.save(tmp_path, command_manifest)

    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path)

    assert result.success is True
    assert [entry.skill_name for entry in load_manifest(tmp_path).entries] == ["spec-kitty"]  # type: ignore[union-attr]
    assert [entry.path for entry in manifest_store.load(tmp_path).entries] == [current_rel]
    assert any("Pruned retired skill manifest entry" in change for change in result.changes_made)
    assert any("Pruned retired command skills manifest entry" in change for change in result.changes_made)


def test_apply_is_idempotent_when_surface_absent(tmp_path: Path) -> None:
    result = RetireStandaloneSkillSurfaceMigration().apply(tmp_path)

    assert result.success is True
    assert result.changes_made == ["Retired standalone governance skill surfaces absent"]


def test_migration_is_registered_by_auto_discovery() -> None:
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    MigrationRegistry.clear()
    auto_discover_migrations()

    assert "3.2.0rc45_retire_standalone_skill_surface" in MigrationRegistry._migrations
