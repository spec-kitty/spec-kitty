"""T022 — Tests for the SessionPresenceClaudeCodeMigration.

Covers detect/apply/idempotency, dry_run, runs_on_worktrees, and registry registration.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Force import of the migration module so its @register decorator fires
import specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code  # noqa: F401
from specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code import (
    SessionPresenceClaudeCodeMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.session_presence.content import SECTION_OPEN

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_project(tmp_path: Path, with_claude: bool = True) -> Path:
    """Create a minimal spec-kitty project directory."""
    (tmp_path / ".kittify").mkdir()
    if with_claude:
        (tmp_path / ".claude").mkdir()
        config_yaml = tmp_path / ".kittify" / "config.yaml"
        config_yaml.write_text(
            "agents:\n  available:\n    - claude\n", encoding="utf-8"
        )
    return tmp_path


@pytest.fixture
def claude_project(tmp_path: Path) -> Path:
    """A minimal spec-kitty project with claude configured."""
    return _make_project(tmp_path, with_claude=True)


class TestDetect:
    def test_false_for_project_without_kittify(self, tmp_path: Path) -> None:
        migration = SessionPresenceClaudeCodeMigration()
        assert migration.detect(tmp_path) is False

    def test_false_when_claude_not_configured(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        config = tmp_path / ".kittify" / "config.yaml"
        config.write_text("agents:\n  available:\n    - gemini\n", encoding="utf-8")
        migration = SessionPresenceClaudeCodeMigration()
        assert migration.detect(tmp_path) is False

    def test_true_when_claude_md_section_missing(self, claude_project: Path) -> None:
        """detect() returns True when CLAUDE.md section is missing (even if hook present)."""
        settings = claude_project / ".claude" / "settings.json"
        settings.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "spec-kitty session-start",
                                    }
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        # No CLAUDE.md, so presence is incomplete
        migration = SessionPresenceClaudeCodeMigration()
        assert migration.detect(claude_project) is True

    def test_true_when_hook_missing(self, claude_project: Path) -> None:
        """detect() returns True when hook is missing (even if CLAUDE.md section exists)."""
        from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN

        claude_md = claude_project / ".claude" / "CLAUDE.md"
        claude_md.write_text(
            f"{SECTION_OPEN}\nSome content\n{SECTION_CLOSE}\n", encoding="utf-8"
        )
        # No settings.json
        migration = SessionPresenceClaudeCodeMigration()
        assert migration.detect(claude_project) is True

    def test_false_when_both_artefacts_present(self, claude_project: Path) -> None:
        """detect() returns False when both CLAUDE.md section and hook are present."""
        from specify_cli.session_presence.writers.claude_code import ClaudeCodeWriter
        from specify_cli.session_presence.content import SessionPresenceContent

        content = SessionPresenceContent("3.2.0", "test-project", "healthy", None)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch(
                "importlib.metadata.version",
                return_value="3.2.0",
            ),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            ClaudeCodeWriter().write(claude_project, content)

        migration = SessionPresenceClaudeCodeMigration()
        assert migration.detect(claude_project) is False


class TestApply:
    def test_apply_writes_claude_md_section(self, claude_project: Path) -> None:
        migration = SessionPresenceClaudeCodeMigration()
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch(
                "importlib.metadata.version",
                return_value="3.2.0",
            ),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = migration.apply(claude_project)

        assert result.success
        claude_md = claude_project / ".claude" / "CLAUDE.md"
        assert claude_md.exists()
        assert SECTION_OPEN in claude_md.read_text(encoding="utf-8")

    def test_apply_writes_settings_json_hook(self, claude_project: Path) -> None:
        migration = SessionPresenceClaudeCodeMigration()
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch(
                "importlib.metadata.version",
                return_value="3.2.0",
            ),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            migration.apply(claude_project)

        settings = claude_project / ".claude" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text(encoding="utf-8"))
        entries = data.get("hooks", {}).get("SessionStart", [])
        commands = [
            h.get("command")
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert "spec-kitty session-start" in commands

    def test_apply_dry_run_no_filesystem_changes(self, claude_project: Path) -> None:
        """apply(dry_run=True) produces no filesystem changes."""
        migration = SessionPresenceClaudeCodeMigration()
        result = migration.apply(claude_project, dry_run=True)
        assert result.success
        # CLAUDE.md must not have been created
        assert not (claude_project / ".claude" / "CLAUDE.md").exists()
        assert not (claude_project / ".claude" / "settings.json").exists()

    def test_apply_idempotent(self, claude_project: Path) -> None:
        """apply() twice leaves files in the same state (no duplicates)."""
        migration = SessionPresenceClaudeCodeMigration()
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch(
                "importlib.metadata.version",
                return_value="3.2.0",
            ),
            patch(
                "specify_cli.compat.plan",
                side_effect=Exception("no compat"),
            ),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            migration.apply(claude_project)
            migration.apply(claude_project)

        claude_md = claude_project / ".claude" / "CLAUDE.md"
        text = claude_md.read_text(encoding="utf-8")
        assert text.count(SECTION_OPEN) == 1

        settings = claude_project / ".claude" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        entries = data.get("hooks", {}).get("SessionStart", [])
        commands = [
            h.get("command")
            for entry in entries
            for h in entry.get("hooks", [])
            if h.get("command") == "spec-kitty session-start"
        ]
        assert len(commands) == 1


class TestMigrationAttributes:
    def test_runs_on_worktrees_is_false(self) -> None:
        assert SessionPresenceClaudeCodeMigration.runs_on_worktrees is False

    def test_migration_registered_in_registry(self) -> None:
        """Migration is registered in MigrationRegistry (test via registry lookup)."""
        migration_ids = {m.migration_id for m in MigrationRegistry.get_all()}
        assert "3_3_0_session_presence_claude_code" in migration_ids


class TestStopHookBackfill:
    """WP06 T024/T027 — existing projects get the Stop hook on upgrade."""

    def _write_presence(self, project: Path) -> None:
        from specify_cli.session_presence.content import SessionPresenceContent
        from specify_cli.session_presence.writers.claude_code import ClaudeCodeWriter

        content = SessionPresenceContent("3.2.0", "test-project", "healthy", None)
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            ClaudeCodeWriter().write(project, content)

    def _strip_stop_hook(self, project: Path) -> None:
        """Simulate a pre-WP06 project: presence written, but no Stop hook."""
        settings = project / ".claude" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        data["hooks"].pop("Stop", None)
        settings.write_text(json.dumps(data), encoding="utf-8")

    def test_detect_true_when_stop_hook_missing(self, claude_project: Path) -> None:
        self._write_presence(claude_project)
        self._strip_stop_hook(claude_project)
        assert SessionPresenceClaudeCodeMigration().detect(claude_project) is True

    def test_detect_false_on_current_project(self, claude_project: Path) -> None:
        self._write_presence(claude_project)
        assert SessionPresenceClaudeCodeMigration().detect(claude_project) is False

    def test_apply_backfills_stop_hook_preserving_session_start(
        self, claude_project: Path
    ) -> None:
        self._write_presence(claude_project)
        self._strip_stop_hook(claude_project)
        migration = SessionPresenceClaudeCodeMigration()
        with (
            patch(
                "specify_cli.session_presence.manager.UpgradeChecker"
            ) as mock_checker_cls,
            patch("importlib.metadata.version", return_value="3.2.0"),
            patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
        ):
            mock_checker_cls.return_value.get_available_version.return_value = None
            result = migration.apply(claude_project)
        assert result.success
        data = json.loads(
            (claude_project / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        stop_commands = [
            h["command"] for entry in data["hooks"]["Stop"] for h in entry["hooks"]
        ]
        assert stop_commands == ["spec-kitty session-stop"]
        start_commands = [
            h["command"]
            for entry in data["hooks"]["SessionStart"]
            for h in entry["hooks"]
        ]
        assert start_commands.count("spec-kitty session-start") == 1
        # Migration is now satisfied — no-ops on a current project.
        assert migration.detect(claude_project) is False
