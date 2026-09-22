"""Tests for destructive clarify command cleanup migration."""

from __future__ import annotations

from pathlib import Path

from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.upgrade.migrations.m_2_0_11_remove_clarify_command import (
    RemoveClarifyCommandMigration,
)


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: A genuinely package-shipped clarify command carries the version marker, which
#: is what proves ownership now that the retirement is routed through the guard
#: (a bare ``spec-kitty.clarify*`` name match is no longer treated as proof).
_OWNED = "<!-- spec-kitty-command-version: 4.0.0 -->\nclarify command body\n"


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".kittify").mkdir()
    save_agent_config(project, AgentConfig(available=["opencode"]))
    return project


def test_detects_templates_and_orphaned_agent_prompts(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / ".kittify" / "templates" / "command-templates").mkdir(parents=True)
    (project / ".kittify" / "missions" / "software-dev" / "command-templates").mkdir(parents=True)
    (project / ".kittify" / "templates" / ".merged-software-dev").mkdir(parents=True)
    (project / ".codex" / "prompts").mkdir(parents=True)

    (project / ".kittify" / "templates" / "command-templates" / "clarify.md").write_text("x", encoding="utf-8")
    (project / ".kittify" / "missions" / "software-dev" / "command-templates" / "clarify.md").write_text("x", encoding="utf-8")
    (project / ".kittify" / "templates" / ".merged-software-dev" / "clarify.md").write_text("x", encoding="utf-8")
    # Codex is intentionally not configured. The migration should still clean it up.
    (project / ".codex" / "prompts" / "spec-kitty.clarify.md").write_text("x", encoding="utf-8")

    migration = RemoveClarifyCommandMigration()
    assert migration.detect(project) is True


def test_apply_removes_all_known_clarify_artifacts(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / ".kittify" / "templates" / "command-templates").mkdir(parents=True)
    (project / ".kittify" / "missions" / "software-dev" / "command-templates").mkdir(parents=True)
    (project / ".opencode" / "command").mkdir(parents=True)
    (project / ".gemini" / "commands").mkdir(parents=True)
    (project / ".github" / "prompts").mkdir(parents=True)

    targets = [
        project / ".kittify" / "templates" / "command-templates" / "clarify.md",
        project / ".kittify" / "missions" / "software-dev" / "command-templates" / "clarify.md",
        project / ".opencode" / "command" / "spec-kitty.clarify.md",
        project / ".gemini" / "commands" / "spec-kitty.clarify.toml",
        project / ".github" / "prompts" / "spec-kitty.clarify.prompt.md",
    ]
    for target in targets:
        target.write_text(_OWNED, encoding="utf-8")

    migration = RemoveClarifyCommandMigration()
    result = migration.apply(project, dry_run=False)

    assert result.success is True
    assert result.errors == []
    assert any(change == "Removed 5 clarify command artifacts" for change in result.changes_made)
    for target in targets:
        assert not target.exists()


def test_dry_run_reports_without_removing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    target = project / ".opencode" / "command" / "spec-kitty.clarify.md"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")

    migration = RemoveClarifyCommandMigration()
    result = migration.apply(project, dry_run=True)

    assert result.success is True
    assert any("Would remove:" in change for change in result.changes_made)
    assert target.exists()


def test_noop_when_no_clarify_artifacts_exist(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    migration = RemoveClarifyCommandMigration()
    assert migration.detect(project) is False
    result = migration.apply(project, dry_run=False)

    assert result.success is True
    assert result.changes_made == ["No clarify command artifacts found"]
