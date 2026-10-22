"""T020 — Tests for ClaudeCodeWriter.

Verifies that ClaudeCodeWriter delegates to both MarkdownRulesWriter and
ClaudeCodeHookRegistrar, and that has_presence() requires both artefacts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.writers.claude_code import (
    SESSION_START_CMD,
    SESSION_STOP_CMD,
    ClaudeCodeWriter,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _content() -> SessionPresenceContent:
    return SessionPresenceContent("3.2.0", "test-project", "healthy", None)


class TestWrite:
    def test_write_calls_super_and_hook_registrar(self, tmp_path: Path) -> None:
        """The real writer produces orientation and both hooks as one batch."""
        import json
        from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

        writer = ClaudeCodeWriter()
        writer.write(tmp_path, _content())
        assert (tmp_path / ".claude/CLAUDE.md").read_text() == _content().render()
        data = json.loads((tmp_path / ".claude/settings.json").read_bytes())
        assert data["hooks"] == {
            "SessionStart": [{"hooks": [{"type": "command", "command": SESSION_START_CMD}]}],
            "Stop": [{"hooks": [{"type": "command", "command": SESSION_STOP_CMD}]}],
        }
        before = snapshot({"project": tmp_path})
        writer.write(tmp_path, _content())
        assert_unchanged(before, snapshot({"project": tmp_path}))


class TestRemove:
    def test_remove_calls_super_and_hook_unregistrar(self, tmp_path: Path) -> None:
        """remove() must call MarkdownRulesWriter.remove() AND ClaudeCodeHookRegistrar.unregister()."""
        writer = ClaudeCodeWriter()
        with (
            patch("specify_cli.session_presence.writers.claude_code.MarkdownRulesWriter.remove") as mock_md_remove,
            patch("specify_cli.session_presence.writers.claude_code.ClaudeCodeHookRegistrar.unregister") as mock_hook_unreg,
        ):
            writer.remove(tmp_path)
        mock_md_remove.assert_called_once_with(tmp_path)
        unregistered = [call.args for call in mock_hook_unreg.call_args_list]
        assert (tmp_path, SESSION_START_CMD) in unregistered
        assert (tmp_path, SESSION_STOP_CMD) in unregistered


class TestHasPresenceStopHook:
    """WP06 — has_presence() additionally requires the Stop hook."""

    def test_false_when_stop_hook_missing(self, claude_project: Path) -> None:
        """A pre-WP06 project (SessionStart only) reports incomplete presence."""
        from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN

        (claude_project / ".claude" / "CLAUDE.md").write_text(f"{SECTION_OPEN}\nSome content\n{SECTION_CLOSE}\n", encoding="utf-8")
        (claude_project / ".claude" / "settings.json").write_text(
            '{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "spec-kitty session-start"}]}]}}',
            encoding="utf-8",
        )
        assert ClaudeCodeWriter().has_presence(claude_project) is False

    def test_write_registers_stop_hook(self, claude_project: Path) -> None:
        import json as _json

        ClaudeCodeWriter().write(claude_project, _content())
        data = _json.loads((claude_project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        stop_commands = [h["command"] for entry in data["hooks"]["Stop"] for h in entry["hooks"]]
        assert stop_commands == [SESSION_STOP_CMD]


class TestHasPresence:
    def test_false_when_claude_md_section_missing(self, claude_project: Path) -> None:
        """has_presence() is False when CLAUDE.md section is missing, even if hook exists."""
        # Register hook but don't write CLAUDE.md
        settings = claude_project / ".claude" / "settings.json"
        settings.write_text(
            '{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "spec-kitty session-start"}]}]}}',
            encoding="utf-8",
        )
        writer = ClaudeCodeWriter()
        assert writer.has_presence(claude_project) is False

    def test_false_when_hook_missing(self, claude_project: Path) -> None:
        """has_presence() is False when hook is missing, even if CLAUDE.md section exists."""
        from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN

        claude_md = claude_project / ".claude" / "CLAUDE.md"
        claude_md.write_text(f"{SECTION_OPEN}\nSome content\n{SECTION_CLOSE}\n", encoding="utf-8")
        # No settings.json
        writer = ClaudeCodeWriter()
        assert writer.has_presence(claude_project) is False

    def test_true_when_both_present(self, claude_project: Path) -> None:
        """has_presence() is True only when BOTH artefacts are present."""
        writer = ClaudeCodeWriter()
        writer.write(claude_project, _content())
        assert writer.has_presence(claude_project) is True

    def test_false_when_neither_present(self, claude_project: Path) -> None:
        """has_presence() is False when neither artefact is present."""
        writer = ClaudeCodeWriter()
        assert writer.has_presence(claude_project) is False


class TestCommittedSettings:
    """#6474: a settings.json the team committed is never edited."""

    @staticmethod
    def _commit_settings(project: Path, text: str) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / ".claude").mkdir()
        (project / ".claude/settings.json").write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", ".claude/settings.json"], cwd=project, check=True)

    @pytest.mark.git_repo
    def test_committed_settings_are_left_alone_and_the_notice_names_the_hooks(self, tmp_path: Path) -> None:
        from specify_cli.session_presence.writers.claude_code import committed_settings_notice

        team_settings = '{"enabledPlugins": {"team@market": true}}\n'
        self._commit_settings(tmp_path, team_settings)
        writer = ClaudeCodeWriter()

        writer.write(tmp_path, _content())

        assert (tmp_path / ".claude/settings.json").read_text(encoding="utf-8") == team_settings
        assert (tmp_path / ".claude/CLAUDE.md").read_text() == _content().render()
        settings_member = writer.prepare_batch(tmp_path, _content())[1]
        assert settings_member.disposition == "preserve"
        assert not settings_member.changed
        notice = committed_settings_notice(tmp_path)
        assert notice is not None
        assert SESSION_START_CMD in notice
        assert SESSION_STOP_CMD in notice

    @pytest.mark.git_repo
    def test_committed_settings_that_already_hold_the_hooks_need_no_notice(self, tmp_path: Path) -> None:
        import json

        from specify_cli.session_presence.writers.claude_code import committed_settings_notice

        hooks = {
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command", "command": SESSION_START_CMD}]}],
                "Stop": [{"hooks": [{"type": "command", "command": SESSION_STOP_CMD}]}],
            }
        }
        self._commit_settings(tmp_path, json.dumps(hooks))

        assert committed_settings_notice(tmp_path) is None

    @pytest.mark.git_repo
    def test_untracked_settings_still_get_the_hooks(self, tmp_path: Path) -> None:
        import subprocess

        from specify_cli.session_presence.writers.claude_code import committed_settings_notice

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude/settings.json").write_text("{}\n", encoding="utf-8")

        ClaudeCodeWriter().write(tmp_path, _content())

        assert SESSION_START_CMD in (tmp_path / ".claude/settings.json").read_text(encoding="utf-8")
        assert committed_settings_notice(tmp_path) is None

    def test_outside_a_repository_settings_are_never_committed(self, tmp_path: Path) -> None:
        from specify_cli.session_presence.writers.claude_code import committed_settings_notice

        assert committed_settings_notice(tmp_path) is None
