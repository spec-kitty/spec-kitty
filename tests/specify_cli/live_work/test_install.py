"""Hook installation — idempotent merge, sibling preservation, clean removal."""

from __future__ import annotations

import json
import tomllib
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


def _top_level_notify(config: Path) -> object:
    return tomllib.loads(config.read_text(encoding="utf-8")).get("notify")


def test_codex_install_inserts_at_top_level_without_destroying_comments(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text('# user comment\nmodel = "gpt-5"\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    text = config.read_text(encoding="utf-8")
    assert "# user comment" in text  # textual merge, never a TOML re-serialize
    assert CODEX_NOTIFY_LINE in text
    assert _top_level_notify(config) is not None  # top-level scope, not inside a table


def test_codex_install_lands_top_level_in_a_sectioned_config(tmp_path: Path) -> None:
    """Squad pass-2 MAJOR repro: tables-last is the normal Codex config shape.

    A textual EOF append lands the key inside ``[mcp_servers.fetch]``, where
    Codex never reads it, while the install still reports success.
    """
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text(
        'model = "gpt-5-codex"\napproval_policy = "on-request"\n\n[mcp_servers.fetch]\ncommand = "uvx"\nargs = ["mcp-server-fetch"]\n',
        encoding="utf-8",
    )
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    assert "inserted the live-work notify entry at the top" in outcome.detail
    notify = _top_level_notify(config)
    assert isinstance(notify, list) and "spec-kitty live-work hook codex" in notify
    parsed = tomllib.loads(config.read_text(encoding="utf-8"))
    assert "notify" not in parsed["mcp_servers"]["fetch"]  # never scoped inside the table
    assert parsed["mcp_servers"]["fetch"]["command"] == "uvx"  # the table itself is untouched


def test_codex_install_moves_a_misplaced_notify_line_to_the_top_level(tmp_path: Path) -> None:
    """A pre-scope-fix install's EOF append is repaired, not duplicated."""
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text(f'[mcp_servers.fetch]\ncommand = "uvx"\n{CODEX_NOTIFY_LINE}\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    assert "moved a misplaced live-work notify entry" in outcome.detail
    text = config.read_text(encoding="utf-8")
    assert text.count(CODEX_NOTIFY_LINE) == 1
    assert text.startswith(CODEX_NOTIFY_LINE)  # exactly one copy, at the top
    assert _top_level_notify(config) == ["spec-kitty live-work hook codex"]


def test_codex_install_ignores_a_notify_nested_in_a_table(tmp_path: Path) -> None:
    """Squad pass-2 mirror repro: [tui.notifications] notify is not the notify key."""
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text("[tui.notifications]\nnotify = true\n", encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed  # no false refusal — the nested key is not ours to clobber
    assert _top_level_notify(config) == ["spec-kitty live-work hook codex"]
    parsed = tomllib.loads(config.read_text(encoding="utf-8"))
    assert parsed["tui"]["notifications"]["notify"] is True  # the TUI setting is untouched


def test_codex_install_refuses_to_clobber_an_existing_notify(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text('notify = ["my-own-hook"]\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert not outcome.installed
    assert "refusing to clobber" in outcome.detail
    assert (codex / "config.toml").read_text(encoding="utf-8") == 'notify = ["my-own-hook"]\n'


def test_codex_install_is_idempotent_for_a_hand_merged_notify(tmp_path: Path) -> None:
    """A user who hand-merged our command into their own list is already installed."""
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text('notify = [\n  "my-own-hook",\n  "spec-kitty live-work hook codex",\n]\n', encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    assert "already present" in outcome.detail
    assert config.read_text(encoding="utf-8") == before  # their formatting is never rewritten


def test_codex_install_is_idempotent_for_the_exact_line(tmp_path: Path) -> None:
    codex = tmp_path / ".codex"
    codex.mkdir()
    config = codex / "config.toml"
    config.write_text(f'{CODEX_NOTIFY_LINE}\nmodel = "x"\n', encoding="utf-8")
    before = config.read_text(encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    assert "already present" in outcome.detail
    assert config.read_text(encoding="utf-8") == before


def test_codex_install_refuses_on_invalid_toml(tmp_path: Path) -> None:
    """Scope cannot be decided in a file that does not parse — refuse, never guess."""
    codex = tmp_path / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text("model = \nnot toml at all\n", encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert not outcome.installed
    assert "not valid TOML" in outcome.detail
    assert "not toml at all" in (codex / "config.toml").read_text(encoding="utf-8")


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
    assert _top_level_notify(config) is None


def test_codex_install_then_matrix_health_agrees(tmp_path: Path) -> None:
    """The no-silent-green gate: install success and harness health must agree."""
    from specify_cli.live_work.capability import harness_health

    codex = tmp_path / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text('model = "gpt-5-codex"\n\n[mcp_servers.fetch]\ncommand = "uvx"\n', encoding="utf-8")
    outcome = install_hooks("codex", tmp_path)
    assert outcome.installed
    health = harness_health("codex", tmp_path)
    assert health is not None and health.hooks_installed, health
