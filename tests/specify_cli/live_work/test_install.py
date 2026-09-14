"""Hook installation — idempotent merge, sibling preservation, clean removal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.live_work.install import (
    CLAUDE_LIVE_WORK_COMMAND,
    CODEX_NOTIFY_LINE,
    install_hooks,
    uninstall_hooks,
)

pytestmark = pytest.mark.fast


@pytest.fixture
def claude_project(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "model": "opus",
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": "spec-kitty session-start"}]}],
                    "PostToolUse": [
                        {
                            "matcher": "Edit|Write",
                            "hooks": [{"type": "command", "command": "spec-kitty lint --json"}],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def _hooks(project: Path) -> dict:
    return json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]


def test_install_adds_live_work_hooks_and_preserves_siblings(claude_project: Path) -> None:
    outcome = install_hooks("claude", claude_project)
    assert outcome.installed
    hooks = _hooks(claude_project)
    assert "SessionStart" in hooks and "PreToolUse" in hooks
    # The pre-existing sibling hooks are untouched.
    commands = [h["command"] for entry in hooks["SessionStart"] for h in entry["hooks"]]
    assert "spec-kitty session-start" in commands
    assert CLAUDE_LIVE_WORK_COMMAND in commands
    lint_commands = [h["command"] for entry in hooks["PostToolUse"] for h in entry["hooks"]]
    assert "spec-kitty lint --json" in lint_commands


def test_install_is_idempotent(claude_project: Path) -> None:
    install_hooks("claude", claude_project)
    before = _hooks(claude_project)
    outcome = install_hooks("claude", claude_project)
    assert "already registered" in outcome.detail
    assert _hooks(claude_project) == before


def test_uninstall_removes_only_live_work(claude_project: Path) -> None:
    install_hooks("claude", claude_project)
    outcome = uninstall_hooks("claude", claude_project)
    assert outcome.installed
    hooks = _hooks(claude_project)
    all_commands = [h["command"] for entries in hooks.values() for entry in entries for h in entry["hooks"]]
    assert CLAUDE_LIVE_WORK_COMMAND not in all_commands
    assert "spec-kitty session-start" in all_commands
    assert "spec-kitty lint --json" in all_commands


def test_missing_settings_json_is_respected_not_created(tmp_path: Path) -> None:
    outcome = install_hooks("claude", tmp_path)
    assert not outcome.installed
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_unknown_harness_reports_no_adapter(tmp_path: Path) -> None:
    outcome = install_hooks("cursor", tmp_path)
    assert not outcome.installed
    assert "no Live Work adapter" in outcome.detail


# ── Codex config.toml ───────────────────────────────────────────────────────


def test_codex_install_appends_without_destroying_comments(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text('# user comment\nmodel = "gpt-5"\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    text = config.read_text(encoding="utf-8")
    assert "# user comment" in text  # textual merge, never a TOML re-serialize
    assert CODEX_NOTIFY_LINE in text


def test_codex_install_refuses_to_clobber_an_existing_notify(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text('notify = ["my-own-hook"]\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert not outcome.installed
    assert "refusing to clobber" in outcome.detail
    assert (codex / "config.toml").read_text(encoding="utf-8") == 'notify = ["my-own-hook"]\n'


def test_codex_install_creates_config_when_codex_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir()
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    assert (tmp_path / ".codex" / "config.toml").exists()


def test_codex_install_skips_when_no_codex_dir(tmp_path: Path) -> None:
    outcome = install_hooks("codex", tmp_path)
    assert not outcome.installed
    assert ".codex/ not present" in outcome.detail


def test_codex_uninstall_removes_only_the_live_work_line(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text(f'# user comment\n{CODEX_NOTIFY_LINE}\nmodel = "x"\n', encoding="utf-8")
    outcome = uninstall_hooks("codex", tmp_path)
    assert outcome.installed
    text = config.read_text(encoding="utf-8")
    assert CODEX_NOTIFY_LINE not in text
    assert "# user comment" in text
    assert 'model = "x"' in text
