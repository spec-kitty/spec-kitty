"""Tests for the global managed agent-skill bootstrap."""

from __future__ import annotations

import shutil
from pathlib import Path

from specify_cli.runtime.agent_skills import ensure_global_agent_skills
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.retired import RETIRED_STANDALONE_SKILL_NAMES


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _create_skill(root: Path, name: str, content: str | None = None) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        content or f"---\nname: {name}\ndescription: test\n---\n# {name}\n",
        encoding="utf-8",
    )


def test_global_bootstrap_preserves_non_spec_kitty_user_skills(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(skills_root, "spec-kitty-test-skill")
    registry = SkillRegistry(skills_root)

    custom_skill = home / ".claude" / "skills" / "custom-skill" / "SKILL.md"
    custom_skill.parent.mkdir(parents=True, exist_ok=True)
    custom_skill.write_text("# custom\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    managed_skill = home / ".claude" / "skills" / "spec-kitty-test-skill" / "SKILL.md"
    assert managed_skill.is_file()
    assert custom_skill.is_file()
    assert custom_skill.read_text(encoding="utf-8") == "# custom\n"

    mode = managed_skill.stat().st_mode
    assert mode & 0o200 == 0


def test_global_bootstrap_preserves_unproven_retired_paula_and_debbie_skills(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(skills_root, "spec-kitty-test-skill")
    registry = SkillRegistry(skills_root)

    for root in [
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]:
        for retired_name in ["debugger-debbie", "paula-patterns"]:
            retired_skill = root / retired_name / "SKILL.md"
            retired_skill.parent.mkdir(parents=True, exist_ok=True)
            retired_skill.write_text("# retired\n", encoding="utf-8")
        custom_skill = root / "custom-skill" / "SKILL.md"
        custom_skill.parent.mkdir(parents=True, exist_ok=True)
        custom_skill.write_text("# custom\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    for root in [
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]:
        assert (root / "debugger-debbie" / "SKILL.md").read_text() == "# retired\n"
        assert (root / "paula-patterns" / "SKILL.md").read_text() == "# retired\n"
        assert (root / "custom-skill" / "SKILL.md").is_file()


def test_global_bootstrap_preserves_unproven_retired_standalone_skill_surface(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(skills_root, "spec-kitty")
    registry = SkillRegistry(skills_root)

    retired_name = next(iter(RETIRED_STANDALONE_SKILL_NAMES))
    for root in [
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]:
        stale = root / retired_name / "SKILL.md"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("# stale standalone surface\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    for root in [
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]:
        assert (root / retired_name / "SKILL.md").read_text() == "# stale standalone surface\n"
    assert (home / ".agents" / "skills" / "spec-kitty" / "SKILL.md").is_file()


def test_global_bootstrap_preserves_unproven_retired_skill_when_marker_is_current(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    kittify_home = home / ".kittify"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))
    monkeypatch.setattr("specify_cli.runtime.agent_skills._get_cli_version", lambda: "3.2.0rc45")

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(skills_root, "spec-kitty")
    registry = SkillRegistry(skills_root)

    retired_name = next(iter(RETIRED_STANDALONE_SKILL_NAMES))
    stale = home / ".agents" / "skills" / retired_name / "SKILL.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("# stale standalone surface\n", encoding="utf-8")

    cache_dir = kittify_home / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "agent-skills.lock").write_text("3.2.0rc45", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    assert stale.read_text() == "# stale standalone surface\n"
    assert (home / ".agents" / "skills" / "spec-kitty" / "SKILL.md").is_file()


def test_global_bootstrap_preserves_unproven_readonly_retired_skill_tree(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(skills_root, "spec-kitty-test-skill")
    registry = SkillRegistry(skills_root)

    retired_skill = home / ".claude" / "skills" / "debugger-debbie" / "SKILL.md"
    retired_skill.parent.mkdir(parents=True, exist_ok=True)
    retired_skill.write_text("# retired\n", encoding="utf-8")
    retired_skill.chmod(0o444)

    def forbidden_rmtree(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unproven retired trees must never reach recursive deletion")

    monkeypatch.setattr(shutil, "rmtree", forbidden_rmtree)
    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    assert retired_skill.read_text() == "# retired\n"
    assert retired_skill.stat().st_mode & 0o222 == 0


def test_global_bootstrap_adds_frontmatter_to_plain_skill(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    skills_root = tmp_path / "doctrine_skills"
    _create_skill(
        skills_root,
        "spec-kitty",
        "# spec-kitty\n\nGet governance context for an action.\n",
    )
    registry = SkillRegistry(skills_root)

    monkeypatch.setattr(
        "specify_cli.runtime.agent_skills._discover_registry",
        lambda: registry,
    )

    ensure_global_agent_skills()

    managed_skill = home / ".agents" / "skills" / "spec-kitty" / "SKILL.md"
    content = managed_skill.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "name: spec-kitty\n" in content
    assert "description: Get governance context for an action.\n" in content
