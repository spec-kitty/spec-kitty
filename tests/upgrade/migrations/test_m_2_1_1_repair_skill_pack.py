"""Tests for the 2.1.1 repair-skill-pack migration."""

from __future__ import annotations

import json
from kernel.clock import now_utc
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.skills.registry import SkillRegistry
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack import (
    RepairSkillPackMigration,
)
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = pytest.mark.fast


def _setup_project(tmp_path: Path, agents: list[str] | None = None) -> Path:
    """Create a minimal initialized project with .kittify/ and config."""
    import subprocess

    project = tmp_path / "project"
    project.mkdir()
    # A real project is git-tracked. Post-cutover, ledger-diff selection (the
    # version window is retired) surfaces migrations whose charter resolution
    # requires a git root -- so this fixture must be a git repo, as a real one is.
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=project, check=True, capture_output=True)
    kittify = project / ".kittify"
    kittify.mkdir()

    if agents is not None:
        config_content = "agents:\n  available:\n"
        for agent_key in agents:
            config_content += f"    - {agent_key}\n"
        (kittify / "config.yaml").write_text(config_content, encoding="utf-8")

    return project


def _setup_skills(tmp_path: Path) -> Path:
    """Create test skill fixtures and return the fake doctrine skills root."""
    skills_root = tmp_path / "doctrine_skills"
    skill_dir = skills_root / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: spec-kitty-test-skill\ndescription: test\n---\n# Test\n",
        encoding="utf-8",
    )
    ref_dir = skill_dir / "references"
    ref_dir.mkdir()
    (ref_dir / "guide.md").write_text("# Guide\nTest reference.\n", encoding="utf-8")
    return skills_root


class TestDetect:
    def test_true_when_manifest_missing_for_installable_agent(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["claude"])
        skills_root = _setup_skills(tmp_path)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack._discover_registry",
            return_value=SkillRegistry(skills_root),
        ):
            assert RepairSkillPackMigration().detect(project) is True

    def test_false_when_only_wrapper_agents_configured(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["q"])
        assert RepairSkillPackMigration().detect(project) is False


class TestApply:
    def test_apply_installs_skills_and_manifest(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["claude"])
        skills_root = _setup_skills(tmp_path)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack._discover_registry",
            return_value=SkillRegistry(skills_root),
        ):
            result = RepairSkillPackMigration().apply(project)

        assert result.success is True
        assert any("Installed" in change for change in result.changes_made)
        assert (project / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()

        manifest_path = project / ".kittify" / "skills-manifest.json"
        assert manifest_path.is_file()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["spec_kitty_version"] == "2.1.1"
        assert len(data["entries"]) >= 1

    def test_detect_false_after_successful_apply(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["claude"])
        skills_root = _setup_skills(tmp_path)
        registry = SkillRegistry(skills_root)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack._discover_registry",
            return_value=registry,
        ):
            result = RepairSkillPackMigration().apply(project)
            assert result.success is True
            assert RepairSkillPackMigration().detect(project) is False

    def test_detect_true_when_managed_skill_file_is_missing(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["claude"])
        skills_root = _setup_skills(tmp_path)
        registry = SkillRegistry(skills_root)

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack._discover_registry",
            return_value=registry,
        ):
            result = RepairSkillPackMigration().apply(project)
            assert result.success is True

            skill_file = project / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md"
            skill_file.unlink()

            assert RepairSkillPackMigration().detect(project) is True


class TestRunnerIntegration:
    def test_upgrade_from_2_1_0_repairs_missing_skill_pack(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path, agents=["claude"])
        skills_root = _setup_skills(tmp_path)

        metadata = ProjectMetadata(
            version="2.1.0",
            initialized_at=now_utc(),
            last_upgraded_at=now_utc(),
        )
        metadata.save(project / ".kittify")

        # Ledger-diff selection (ADR 2026-10-17-1): selection is declared-minus-
        # settled, with no version window. Represent a project already migrated
        # up to this point by seeding the LEDGER with every declared migration
        # as settled EXCEPT the repair migration under test, so the runner
        # selects exactly it (and does not re-run the whole manifest).
        from specify_cli.upgrade.ledger import MigrationLedger, build_record
        from specify_cli.upgrade.migrations import auto_discover_migrations
        from specify_cli.upgrade.registry import MigrationRegistry

        auto_discover_migrations()
        _ledger = MigrationLedger(project)
        for _mig in MigrationRegistry.get_all():
            if _mig.migration_id != "2.1.1_repair_skill_pack":
                _ledger.append(build_record(_mig, "success"))

        with patch(
            "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack._discover_registry",
            return_value=SkillRegistry(skills_root),
        ):
            result = MigrationRunner(project).upgrade("2.1.1", include_worktrees=False)

        assert result.success is True
        assert "2.1.1_repair_skill_pack" in result.migrations_applied
        assert (project / ".kittify" / "skills-manifest.json").is_file()
        assert (project / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()
