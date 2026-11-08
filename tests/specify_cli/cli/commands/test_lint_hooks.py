"""Tests for the lint stdin-bridge and harness hook-sync remediation (#1858).

Covers the behaviour that the original PR shipped broken or untested:
- ``spec-kitty lint`` resolving the target file from a harness stdin payload
  (Claude ``tool_input.file_path`` / Cursor ``file_path``) and from an absolute
  path so ruff/mypy run from any cwd;
- the mypy summary-line filter not swallowing real diagnostics;
- Claude hook sync delegating to the canonical ``ClaudeCodeHookRegistrar``
  (atomic, sibling-hook-preserving, invalid-JSON-backup);
- Cursor hook sync refusing to clobber a corrupt config;
- config.available being the single source of truth for which harness is synced.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import register_commands
from specify_cli.cli.commands.agent import config as config_mod
from specify_cli.cli.commands.agent.config import (
    LINT_HOOK_COMMAND,
    _load_cursor_hooks,
    _parse_bool_value,
    _sync_claude_hooks,
    _sync_cursor_hooks,
    _sync_harness_hooks,
)
from specify_cli.cli.commands.lint import _path_from_payload, _run_mypy
from specify_cli.core.agent_config import AgentConfig

pytestmark = [pytest.mark.integration]


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def app() -> typer.Typer:
    _app = typer.Typer()
    register_commands(_app)
    return _app


# --------------------------------------------------------------------------
# lint: stdin bridge + path resolution
# --------------------------------------------------------------------------


def test_path_from_payload_claude_shape() -> None:
    assert _path_from_payload({"tool_input": {"file_path": "/x/a.py"}}) == Path("/x/a.py")


def test_path_from_payload_cursor_generic_shape() -> None:
    assert _path_from_payload({"file_path": "/x/b.py"}) == Path("/x/b.py")


def test_path_from_payload_list_variant() -> None:
    assert _path_from_payload({"tool_input": {"file_paths": ["/x/c.py"]}}) == Path("/x/c.py")


def test_path_from_payload_no_path_returns_none() -> None:
    assert _path_from_payload({"tool_input": {}}) is None
    assert _path_from_payload({"unrelated": 1}) is None
    assert _path_from_payload("not-a-dict") is None


@patch("subprocess.run")
def test_lint_reads_path_from_claude_stdin(
    mock_run: MagicMock, runner: CliRunner, app: typer.Typer, tmp_path: Path
) -> None:
    """The wired hook form `lint --json` (no argv) resolves the file from stdin."""
    target = tmp_path / "edited.py"
    target.write_text("x = 1\n")
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    payload = json.dumps({"tool_input": {"file_path": str(target)}})
    result = runner.invoke(app, ["lint", "--json"], input=payload)

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["success"] is True


def test_lint_no_path_and_no_stdin_is_noop(runner: CliRunner, app: typer.Typer) -> None:
    """A hook firing without a file path must be a benign no-op, not an error."""
    result = runner.invoke(app, ["lint", "--json"], input="")
    assert result.exit_code == 0
    assert json.loads(result.output)["skipped"] is True


def test_lint_stdin_non_json_is_noop(runner: CliRunner, app: typer.Typer) -> None:
    result = runner.invoke(app, ["lint", "--json"], input="not json at all")
    assert result.exit_code == 0
    assert json.loads(result.output)["skipped"] is True


@patch("subprocess.run")
def test_lint_passes_absolute_path_to_tools(
    mock_run: MagicMock, runner: CliRunner, app: typer.Typer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ruff/mypy must receive the resolved absolute path, not the caller-relative one."""
    target = tmp_path / "rel.py"
    target.write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    result = runner.invoke(app, ["lint", "rel.py", "--json"])
    assert result.exit_code == 0
    # Every subprocess invocation got the absolute path as its last arg.
    for call in mock_run.call_args_list:
        assert call.args[0][-1] == str(target.resolve())


@patch("subprocess.run")
def test_mypy_filter_keeps_real_errors_drops_summary(mock_run: MagicMock, tmp_path: Path) -> None:
    """A real diagnostic beginning with 'Found' is kept; mypy's summary is dropped."""
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="a.py:1: error: Found a problem here\nFound 1 error in 1 file (checked 1)\n",
        stderr="",
    )
    errors = _run_mypy(tmp_path / "a.py", tmp_path)
    assert "a.py:1: error: Found a problem here" in errors
    assert all("Found 1 error" not in line for line in errors)


# --------------------------------------------------------------------------
# Claude hook sync (canonical registrar)
# --------------------------------------------------------------------------


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_claude_enable_adds_matcher_and_command(tmp_path: Path) -> None:
    assert _sync_claude_hooks(tmp_path, enabled=True) is True
    data = _read(tmp_path / ".claude" / "settings.json")
    entries = data["hooks"]["PostToolUse"]
    assert any(
        e.get("matcher") == "Edit|Write"
        and any(h.get("command") == LINT_HOOK_COMMAND for h in e.get("hooks", []))
        for e in entries
    )


def test_claude_disable_preserves_sibling_hooks(tmp_path: Path) -> None:
    """Removing the lint hook must not delete co-located hooks in the same event."""
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "prettier --write"}]},
                        {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": LINT_HOOK_COMMAND}]},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    assert _sync_claude_hooks(tmp_path, enabled=False) is True

    commands = [
        h.get("command")
        for e in _read(settings)["hooks"]["PostToolUse"]
        for h in e.get("hooks", [])
    ]
    assert "prettier --write" in commands
    assert LINT_HOOK_COMMAND not in commands


def test_claude_corrupt_settings_backed_up_not_lost(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{ not valid json", encoding="utf-8")

    assert _sync_claude_hooks(tmp_path, enabled=True) is True
    # Original corrupt content preserved to a sibling .invalid backup.
    backups = list(settings.parent.glob("settings.json.invalid*"))
    assert backups, "corrupt settings must be backed up, not silently discarded"
    assert _read(settings)["hooks"]["PostToolUse"]  # valid structure written


def test_claude_idempotent_enable(tmp_path: Path) -> None:
    assert _sync_claude_hooks(tmp_path, enabled=True) is True
    assert _sync_claude_hooks(tmp_path, enabled=True) is False  # no second change


# --------------------------------------------------------------------------
# Cursor hook sync (safe writer)
# --------------------------------------------------------------------------


def test_cursor_enable_then_disable_roundtrip(tmp_path: Path) -> None:
    assert _sync_cursor_hooks(tmp_path, enabled=True) is True
    hooks = tmp_path / ".cursor" / "hooks.json"
    assert any(h["command"] == LINT_HOOK_COMMAND for h in _read(hooks)["hooks"]["afterFileEdit"])

    assert _sync_cursor_hooks(tmp_path, enabled=False) is True
    assert all(h["command"] != LINT_HOOK_COMMAND for h in _read(hooks)["hooks"]["afterFileEdit"])


def test_cursor_corrupt_config_refused(tmp_path: Path) -> None:
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text("}}corrupt", encoding="utf-8")

    assert _load_cursor_hooks(hooks) is None
    assert _sync_cursor_hooks(tmp_path, enabled=True) is False  # refused
    assert hooks.read_text(encoding="utf-8") == "}}corrupt"  # untouched


def test_cursor_non_utf8_config_refused_not_crashed(tmp_path: Path) -> None:
    """#5293: a hooks.json holding non-UTF-8 bytes used to crash the sync with
    a raw ``UnicodeDecodeError`` traceback instead of the same refusal the
    JSON-corrupt case gets."""
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_bytes(b'{"version": 1, "hooks": {\xff\xfe}}')

    assert _load_cursor_hooks(hooks) is None
    assert _sync_cursor_hooks(tmp_path, enabled=True) is False  # refused
    assert hooks.read_bytes() == b'{"version": 1, "hooks": {\xff\xfe}}'  # untouched


def test_cursor_valid_json_non_object_refused_not_clobbered(tmp_path: Path) -> None:
    """#5293: a hooks.json holding a valid JSON non-object (here: an array)
    used to be silently REPLACED by the empty default -- data loss. It must
    get the same refusal as corrupt JSON: never clobbered."""
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text('[{"command": "precious-user-hook"}]', encoding="utf-8")

    assert _load_cursor_hooks(hooks) is None
    assert _sync_cursor_hooks(tmp_path, enabled=True) is False  # refused
    assert hooks.read_text(encoding="utf-8") == '[{"command": "precious-user-hook"}]'  # untouched


# --------------------------------------------------------------------------
# config.available is the source of truth
# --------------------------------------------------------------------------


def test_sync_skips_unconfigured_cursor_even_if_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()  # stray dir, but cursor not configured
    config = AgentConfig(available=["claude"], lint_on_edit=True)

    with patch.object(config_mod, "_sync_cursor_hooks") as cursor_mock:
        _sync_harness_hooks(tmp_path, config)
        cursor_mock.assert_not_called()
    assert not (tmp_path / ".cursor" / "hooks.json").exists()


def test_parse_bool_value() -> None:
    assert _parse_bool_value("TRUE") is True
    assert _parse_bool_value("off") is False
    assert _parse_bool_value("maybe") is None
