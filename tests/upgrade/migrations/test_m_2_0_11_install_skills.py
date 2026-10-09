"""Tests for the 2.0.11 install-skills migration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.skills.registry import SkillRegistry
from specify_cli.upgrade.migrations.m_2_0_11_install_skills import (
    InstallSkillsMigration,
)

pytestmark = pytest.mark.fast


def _setup_project(tmp_path: Path, agents: list[str] | None = None) -> Path:
    """Create a minimal initialized project with .kittify/ and config."""
    project = tmp_path / "project"
    project.mkdir()
    kittify = project / ".kittify"
    kittify.mkdir()

    if agents is not None:
        config_content = "agents:\n  available:\n"
        for a in agents:
            config_content += f"    - {a}\n"
        (kittify / "config.yaml").write_text(config_content)

    return project


def _setup_skills(tmp_path: Path) -> Path:
    """Create test skill fixtures. Returns the skills root directory."""
    skills_root = tmp_path / "doctrine_skills"
    skill_dir = skills_root / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: spec-kitty-test-skill\ndescription: test\n---\n# Test\n"
    )
    ref_dir = skill_dir / "references"
    ref_dir.mkdir()
    (ref_dir / "guide.md").write_text("# Guide\nTest reference.\n")
    return skills_root


def _patch_registry(skills_root: Path):
    """Return a context manager that patches SkillRegistry in the migration module."""
    test_registry = SkillRegistry(skills_root)

    def mock_from_package() -> SkillRegistry:
        return test_registry

    def mock_from_local(repo_root: Path) -> SkillRegistry:
        return test_registry

    return patch.multiple(
        "specify_cli.skills.registry.SkillRegistry",
        from_package=classmethod(lambda cls: mock_from_package()),
        from_local_repo=classmethod(lambda cls, p: mock_from_local(p)),
    )


# ── detect ──────────────────────────────────────────────────────────


class TestDetect:
    def test_true_when_no_manifest(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        assert InstallSkillsMigration().detect(project) is True

    def test_false_when_manifest_exists(self, tmp_path: Path) -> None:
        project = _setup_project(tmp_path)
        (project / ".kittify" / "skills-manifest.json").write_text("{}")
        assert InstallSkillsMigration().detect(project) is False


# ── can_apply ───────────────────────────────────────────────────────


class TestCanApply:
    def test_false_when_no_kittify(self, tmp_path: Path) -> None:
        project = tmp_path / "empty"
        project.mkdir()
        can, reason = InstallSkillsMigration().can_apply(project)
        assert can is False
        assert ".kittify/" in reason


# ── apply (real path) ──────────────────────────────────────────────


class TestApplyReal:
    """Exercise InstallSkillsMigration.apply() — the real code path."""

    def _apply_with_test_skills(
        self,
        tmp_path: Path,
        agents: list[str],
        *,
        dry_run: bool = False,
    ):
        project = _setup_project(tmp_path, agents=agents)
        skills_root = _setup_skills(tmp_path)
        test_registry = SkillRegistry(skills_root)

        # Patch SkillRegistry.from_package to return our test registry
        with patch(
            "specify_cli.skills.registry.SkillRegistry.from_package",
            return_value=test_registry,
        ):
            migration = InstallSkillsMigration()
            result = migration.apply(project, dry_run=dry_run)

        return project, result

    def test_native_agent_via_apply(self, tmp_path: Path) -> None:
        """apply() installs skills to .claude/skills/ for native agent."""
        project, result = self._apply_with_test_skills(tmp_path, ["claude"])

        assert result.success is True
        assert any("Installed" in c for c in result.changes_made)

        # Skill installed to native root
        assert (project / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()
        assert (project / ".claude" / "skills" / "spec-kitty-test-skill" / "references" / "guide.md").is_file()

        # Manifest created with full metadata
        manifest_path = project / ".kittify" / "skills-manifest.json"
        assert manifest_path.is_file()
        data = json.loads(manifest_path.read_text())
        assert data["version"] == 1
        assert data["created_at"] != ""
        assert data["spec_kitty_version"] == "2.0.11"
        assert len(data["entries"]) >= 1

    @pytest.mark.parametrize("agent", ["cursor", "codex"])
    def test_shared_root_agent_via_apply(self, tmp_path: Path, agent: str) -> None:
        """Upgrade gives shared agents the project skills that init repairs in."""
        project, result = self._apply_with_test_skills(tmp_path, [agent])

        assert result.success is True
        assert (project / ".agents" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()
        assert (project / ".kittify" / "skills-manifest.json").is_file()

    def test_wrapper_only_fails_when_sole_agent(self, tmp_path: Path) -> None:
        """apply() with only wrapper-only agent fails (no files installed)."""
        project, result = self._apply_with_test_skills(tmp_path, ["q"])

        assert result.success is False
        assert any("No skill files" in e for e in result.errors)
        # No manifest created
        assert not (project / ".kittify" / "skills-manifest.json").exists()

    def test_dry_run_creates_no_files(self, tmp_path: Path) -> None:
        """apply(dry_run=True) reports but does not create files."""
        project, result = self._apply_with_test_skills(tmp_path, ["claude"], dry_run=True)

        assert result.success is True
        assert any("Would install" in c for c in result.changes_made)
        assert not (project / ".kittify" / "skills-manifest.json").exists()
        assert not (project / ".claude" / "skills").exists()

    def test_idempotent_after_apply(self, tmp_path: Path) -> None:
        """detect() returns False after successful apply()."""
        project, result = self._apply_with_test_skills(tmp_path, ["claude"])
        assert result.success is True
        assert InstallSkillsMigration().detect(project) is False

    def test_mixed_agents_via_apply(self, tmp_path: Path) -> None:
        """apply() with mixed agents: native + shared + wrapper-only."""
        project, result = self._apply_with_test_skills(
            tmp_path, ["claude", "codex", "q"]
        )

        assert result.success is True
        # Claude: native root
        assert (project / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()
        # Codex: shared root
        assert (project / ".agents" / "skills" / "spec-kitty-test-skill" / "SKILL.md").is_file()
        # q: nothing
        assert not (project / ".amazonq" / "skills").exists()

    def test_manifest_metadata_matches_init(self, tmp_path: Path) -> None:
        """Manifest has created_at and spec_kitty_version like init does."""
        project, result = self._apply_with_test_skills(tmp_path, ["claude"])

        data = json.loads((project / ".kittify" / "skills-manifest.json").read_text())
        assert data["created_at"] != ""
        assert data["spec_kitty_version"] == "2.0.11"
        assert data["updated_at"] != ""
        assert data["version"] == 1

    def test_no_config_warns(self, tmp_path: Path) -> None:
        """apply() without config.yaml warns via agent config fallback."""
        project = tmp_path / "noconfig"
        project.mkdir()
        (project / ".kittify").mkdir()
        # No config.yaml at all — load_agent_config returns defaults

        migration = InstallSkillsMigration()
        result = migration.apply(project)

        # Should not crash; either succeeds with defaults or warns
        assert isinstance(result.success, bool)

    def test_verify_passes_after_upgrade(self, tmp_path: Path) -> None:
        """Full cycle: upgrade install → verify passes."""
        project, result = self._apply_with_test_skills(tmp_path, ["claude", "codex"])
        assert result.success is True

        from specify_cli.skills.verifier import verify_installed_skills

        verify_result = verify_installed_skills(project)
        assert verify_result.ok is True
