"""Regression test for RISK-5 (mission-review-v2): manifest coexistence.

The legacy `ManagedSkillManifest` writes to `.kittify/skills-manifest.json`
(tracking canonical skills like spec-kitty-runtime-next that the legacy
installer places under agent-specific roots like .claude/skills/).

The new `SkillsManifest` writes to `.kittify/command-skills-manifest.json`
(tracking the Spec Kitty command-skill packages that command_installer
places under .agents/skills/spec-kitty-<command>/).

These two manifests previously collided because both used the same filename
constant (`skills-manifest.json`). After renaming the new manifest, a
mixed install — one legacy-path agent + one skill-only agent — must yield
two distinct manifest files with their respective schemas intact. This
test is the guardrail that keeps the two systems from being merged back
into the same path by a future refactor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.skills import command_installer
from specify_cli.skills.manifest import ManagedFileEntry, ManagedSkillManifest, save_manifest

pytestmark = pytest.mark.integration


def _legacy_manifest_path(project: Path) -> Path:
    return project / ".kittify" / "skills-manifest.json"


def _new_manifest_path(project: Path) -> Path:
    return project / ".kittify" / "command-skills-manifest.json"


def _expected_command_skill_paths() -> set[str]:
    return {
        f".agents/skills/spec-kitty-{command}/SKILL.md"
        for command in command_installer.CANONICAL_COMMANDS
    }


def _write_claude_like_legacy_manifest(project: Path) -> None:
    """Simulate what init.py does when a legacy-path agent (e.g. claude)
    lands a canonical skill (e.g. spec-kitty-runtime-next) via
    ``install_skills_for_agent`` + ``save_manifest``."""
    legacy = ManagedSkillManifest()
    legacy.add_entry(
        ManagedFileEntry(
            skill_name="spec-kitty-runtime-next",
            source_file="SKILL.md",
            installed_path=".claude/skills/spec-kitty-runtime-next/SKILL.md",
            installation_class="native-root-required",
            agent_key="claude",
            content_hash="sha256:deadbeef",
            installed_at="2026-04-14T12:00:00+00:00",
        )
    )
    save_manifest(legacy, project)


def test_mixed_install_keeps_both_manifests_intact(tmp_path: Path) -> None:
    """A project that installs both a legacy-path agent (claude) and a
    skill-only agent (vibe) must end up with both manifest files on disk,
    each holding its own schema and data. Neither may clobber the other.
    """
    project = tmp_path / "mixed-install"
    project.mkdir()
    (project / ".kittify").mkdir()
    save_agent_config(project, AgentConfig(available=["claude", "vibe"]))

    # Simulate the relevant init.py workflow: command-skill agents install
    # into .agents/skills/ during the per-agent loop; the legacy manifest for
    # native agents is saved afterward.
    expected_paths = _expected_command_skill_paths()
    report = command_installer.install(project, "vibe")
    assert set(report.added) == expected_paths

    # Now simulate the legacy path writing its manifest.
    _write_claude_like_legacy_manifest(project)

    # Assertion: both files exist.
    legacy_path = _legacy_manifest_path(project)
    new_path = _new_manifest_path(project)
    assert legacy_path.is_file(), f"Legacy manifest missing at {legacy_path}"
    assert new_path.is_file(), f"New manifest missing at {new_path}"
    assert legacy_path != new_path, "Manifests must have distinct paths"

    # Legacy manifest holds the claude skill entry.
    legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert legacy_data["version"] == 1, "Legacy manifest should carry version: 1"
    assert "schema_version" not in legacy_data, "Legacy manifest must not have schema_version"
    legacy_paths = {e["installed_path"] for e in legacy_data["entries"]}
    assert ".claude/skills/spec-kitty-runtime-next/SKILL.md" in legacy_paths

    # New manifest holds the vibe command-skill entries, schema_version: 1.
    new_data = json.loads(new_path.read_text(encoding="utf-8"))
    assert new_data["schema_version"] == 1, "New manifest must carry schema_version: 1"
    assert "version" not in new_data, "New manifest must not carry legacy version field"
    assert {entry["path"] for entry in new_data["entries"]} == expected_paths, (
        f"Expected vibe command-skill entries, got {new_data['entries']}"
    )
    for entry in new_data["entries"]:
        assert entry["agents"] == ["vibe"], entry


def test_subsequent_installer_ops_succeed_after_mixed_install(tmp_path: Path) -> None:
    """After both manifests exist, subsequent command_installer operations
    (install another skill-only agent, remove one) must succeed without
    the schema-version-mismatch error that the collision previously caused.
    """
    project = tmp_path / "mixed-post-op"
    project.mkdir()
    (project / ".kittify").mkdir()
    save_agent_config(project, AgentConfig(available=["claude", "codex", "vibe"]))

    command_installer.install(project, "vibe")
    _write_claude_like_legacy_manifest(project)

    # This would have raised InstallerError("manifest_parse_failed") before
    # the rename, because manifest_store.load would have seen the legacy
    # file and rejected its schema.
    report = command_installer.install(project, "codex")
    expected_paths = _expected_command_skill_paths()
    assert set(report.reused_shared) == expected_paths

    # Manifest now reflects both agents.
    new_data = json.loads(_new_manifest_path(project).read_text(encoding="utf-8"))
    assert {entry["path"] for entry in new_data["entries"]} == expected_paths
    for entry in new_data["entries"]:
        assert entry["agents"] == ["codex", "vibe"], entry

    # And remove(codex) works — leaving vibe entries intact.
    remove_report = command_installer.remove(project, "codex")
    assert set(remove_report.kept) == expected_paths
    final = json.loads(_new_manifest_path(project).read_text(encoding="utf-8"))
    assert {entry["path"] for entry in final["entries"]} == expected_paths
    for entry in final["entries"]:
        assert entry["agents"] == ["vibe"], entry


def test_skill_only_install_alone_does_not_create_legacy_manifest(tmp_path: Path) -> None:
    """A project that configures only vibe should end up with exactly the
    new manifest; the legacy path at .kittify/skills-manifest.json must not
    be created by command_installer (it is owned by the legacy installer).
    """
    project = tmp_path / "vibe-only"
    project.mkdir()
    (project / ".kittify").mkdir()
    save_agent_config(project, AgentConfig(available=["vibe"]))

    command_installer.install(project, "vibe")
    assert _new_manifest_path(project).is_file()
    assert not _legacy_manifest_path(project).exists(), (
        "command_installer must not write the legacy manifest path"
    )
