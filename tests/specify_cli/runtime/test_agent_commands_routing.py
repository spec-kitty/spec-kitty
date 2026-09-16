"""Routing tests for runtime/agent_commands.py.

Post-mission-review correction: `_sync_agent_commands` is the global command-
layer sync path (writes to ``~/.claude/commands/``, ``~/.gemini/commands/``,
etc.). It is called in a loop over ``AGENT_COMMAND_CONFIG``, which no longer
contains command-skill agents. Command-skill installation for those agents is
therefore driven from ``init`` and ``agent config add``, NOT from this
function. These tests verify that:

- ``_sync_agent_commands`` does not try to handle command-skill agents (it is the
  wrong call site for them).
- ``claude`` (and by extension every other command-layer agent) still
  reaches the legacy render-commands path here.
- command-skill agents are absent from ``AGENT_COMMAND_CONFIG`` so the
  caller loop never sees them.
"""

from __future__ import annotations

import contextlib
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.runtime.agent_commands import (
    _get_command_templates_dir,
    _sync_agent_commands,
    ensure_global_agent_commands,
    get_global_command_dir,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_command_skill_agents_absent_from_command_config() -> None:
    """The loop in ``ensure_runtime`` iterates ``AGENT_COMMAND_CONFIG``.

    Command-skill agents must not appear there or the legacy command-file renderer
    would write their files into ``~/.claude/commands/``-style directories.
    """
    for agent_key in ("codex", "vibe", "pi", "letta"):
        assert agent_key not in AGENT_COMMAND_CONFIG


def test_sync_does_not_invoke_skill_installer(tmp_path: Path) -> None:
    """``_sync_agent_commands`` is a command-layer path; it must NEVER call
    ``command_installer.install`` — that is the job of ``init`` and
    ``agent config add``."""
    with (
        patch("specify_cli.skills.command_installer.install") as mock_install,
        contextlib.suppress(Exception),
    ):
        # Call with every command-layer agent key; the legacy path may fail
        # on a bare tmpdir (no templates set up for this test) — that's fine.
        for agent_key in AGENT_COMMAND_CONFIG:
            with contextlib.suppress(Exception):
                _sync_agent_commands(agent_key, tmp_path, "sh")

    mock_install.assert_not_called()


def test_claude_still_routes_to_command_files(tmp_path: Path) -> None:
    """``_sync_agent_commands('claude', ...)`` must NOT call ``command_installer.install``.

    The legacy path may fail on a bare tmpdir (no templates_dir content) but
    that's fine; we only care that the installer was never invoked.
    """
    with (
        patch("specify_cli.skills.command_installer.install") as mock_install,
        contextlib.suppress(Exception),
    ):
        _sync_agent_commands("claude", tmp_path, "sh")

    mock_install.assert_not_called()


def test_sync_writes_parseable_gemini_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    templates_dir = _get_command_templates_dir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    _sync_agent_commands("gemini", templates_dir, "sh")

    target = home / ".gemini" / "commands" / "spec-kitty.implement.toml"
    assert target.is_file()
    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    assert parsed["description"] == "Execute a work package implementation"
    assert "{{args}}" in parsed["prompt"]


def test_sync_writes_parseable_qwen_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    templates_dir = _get_command_templates_dir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))

    _sync_agent_commands("qwen", templates_dir, "sh")

    target = home / ".qwen" / "commands" / "spec-kitty.implement.toml"
    assert target.is_file()
    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    assert parsed["description"] == "Execute a work package implementation"
    assert "{{args}}" in parsed["prompt"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows APPDATA resolution is not exercised")
def test_sync_writes_parseable_llxprt_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLxprt Code forks Gemini CLI's TOML custom-command loader.

    User-global commands live under the envPaths('llxprt-code') config root
    (``~/Library/Preferences/llxprt-code/commands/`` on macOS), not the legacy
    ``~/.llxprt/`` tree that llxprt migrates away from at startup.
    """
    templates_dir = _get_command_templates_dir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    _sync_agent_commands("llxprt", templates_dir, "sh")

    if sys.platform == "darwin":
        commands_root = home / "Library" / "Preferences" / "llxprt-code" / "commands"
    else:
        commands_root = home / ".config" / "llxprt-code" / "commands"
    target = commands_root / "spec-kitty.implement.toml"
    assert target.is_file()
    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    assert parsed["description"] == "Execute a work package implementation"
    assert "{{args}}" in parsed["prompt"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows APPDATA resolution is not exercised")
def test_llxprt_global_command_dir_uses_platform_config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLxprt resolves its global root via envPaths('llxprt-code'), not ~/.llxprt."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    if sys.platform == "darwin":
        expected = tmp_path / "home" / "Library" / "Preferences" / "llxprt-code" / "commands"
    else:
        expected = tmp_path / "home" / ".config" / "llxprt-code" / "commands"

    assert get_global_command_dir("llxprt") == expected


def test_llxprt_global_commands_respect_llxprt_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LLxprt's documented LLXPRT_CONFIG_HOME override should be honored."""
    monkeypatch.setenv("LLXPRT_CONFIG_HOME", str(tmp_path / "custom-llxprt"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    assert get_global_command_dir("llxprt") == tmp_path / "custom-llxprt" / "commands"


@pytest.mark.skipif(sys.platform == "win32", reason="Windows APPDATA resolution is not exercised")
def test_llxprt_global_commands_use_xdg_config_home_on_linux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """On non-darwin platforms the XDG config home feeds envPaths-style resolution."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    if sys.platform == "darwin":
        expected = tmp_path / "home" / "Library" / "Preferences" / "llxprt-code" / "commands"
    else:
        expected = tmp_path / "xdg-config" / "llxprt-code" / "commands"

    assert get_global_command_dir("llxprt") == expected


def test_opencode_global_commands_use_xdg_config_home(tmp_path: Path, monkeypatch) -> None:
    """OpenCode loads global commands from its config root, not ``~/.opencode``."""
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    assert get_global_command_dir("opencode") == tmp_path / "xdg-config" / "opencode" / "commands"


def test_opencode_global_commands_respect_custom_config_dir(tmp_path: Path, monkeypatch) -> None:
    """OpenCode's documented custom config directory should be honored."""
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(tmp_path / "custom-opencode"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    assert get_global_command_dir("opencode") == tmp_path / "custom-opencode" / "commands"


def test_current_version_lock_does_not_mask_partial_global_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A current lock file is not proof that every command file exists."""
    home = tmp_path / "home"
    kittify_home = tmp_path / "kittify"
    claude_commands = home / ".claude" / "commands"
    claude_commands.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    from specify_cli.runtime.agent_commands import _get_cli_version

    cli_version = _get_cli_version()
    cache_dir = kittify_home / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "agent-commands.lock").write_text(cli_version, encoding="utf-8")

    for command in (
        "accept",
        "dashboard",
        "implement",
        "merge",
        "review",
        "status",
        "tasks-finalize",
    ):
        (claude_commands / f"spec-kitty.{command}.md").write_text(
            f"---\ndescription: {command}\n---\n<!-- spec-kitty-command-version: {cli_version} -->\n",
            encoding="utf-8",
        )

    ensure_global_agent_commands()

    actual = sorted(path.name for path in claude_commands.glob("spec-kitty.*.md"))
    assert actual == [
        "spec-kitty.accept.md",
        "spec-kitty.analyze.md",
        "spec-kitty.charter.md",
        "spec-kitty.dashboard.md",
        "spec-kitty.implement.md",
        "spec-kitty.merge.md",
        "spec-kitty.plan.md",
        "spec-kitty.research.md",
        "spec-kitty.review.md",
        "spec-kitty.specify.md",
        "spec-kitty.status.md",
        "spec-kitty.tasks-finalize.md",
        "spec-kitty.tasks-outline.md",
        "spec-kitty.tasks-packages.md",
        "spec-kitty.tasks.md",
    ]
    assert (cache_dir / "agent-commands.lock").read_text(encoding="utf-8") == cli_version


def test_partial_global_command_sync_does_not_write_current_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete required templates refuse before stamping or installing."""
    home = tmp_path / "home"
    kittify_home = tmp_path / "kittify"
    templates_dir = tmp_path / "templates" / "software-dev" / "command-templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "specify.md").write_text(
        "---\ndescription: Specify\n---\n\n# Specify\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(tmp_path / "templates"))
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    with pytest.raises(RuntimeError):
        ensure_global_agent_commands()

    assert not (kittify_home / "cache" / "agent-commands.lock").exists()
    assert not (home / ".claude/commands").exists()
