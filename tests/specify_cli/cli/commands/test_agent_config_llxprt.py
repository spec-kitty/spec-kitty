"""Integration tests for agent config add/remove/list llxprt.

LLxprt Code is a global slash-command agent, so ``agent config`` routes it
through the user-global command root (the envPaths('llxprt-code') config dir,
``~/Library/Preferences/llxprt-code/commands/`` on macOS, overridable via
``LLXPRT_CONFIG_HOME``) rather than the
project-local command-skill installer used by codex/vibe/pi/letta. LLxprt does
read ``SKILL.md`` Agent Skills (see ``AGENT_SKILL_CONFIG['llxprt']``); it just
does not deliver its slash commands as command skills, so the command-skill
manifest stays empty for it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import (
    GLOBAL_COMMAND_AGENTS,
    SKILL_ONLY_AGENTS,
    VALID_AGENTS,
    app,
)
from specify_cli.core.agent_config import AgentConfig, load_agent_config, save_agent_config
from specify_cli.skills import manifest_store

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox]
runner = CliRunner()


def _write_config(tmp_path: Path, agents: list[str]) -> None:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(tmp_path, AgentConfig(available=agents))


def test_llxprt_is_a_valid_global_command_agent() -> None:
    assert "llxprt" in VALID_AGENTS
    assert "llxprt" in GLOBAL_COMMAND_AGENTS
    assert "llxprt" not in SKILL_ONLY_AGENTS


def test_add_llxprt_updates_config_without_installing_command_skills(tmp_path: Path) -> None:
    _write_config(tmp_path, [])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["add", "llxprt"])

    assert result.exit_code == 0, result.output
    assert "llxprt" in load_agent_config(tmp_path).available

    # Global command agents must not claim entries in the command-skill manifest.
    assert manifest_store.load(tmp_path).entries == []
    assert not (tmp_path / ".agents" / "skills").exists()


def test_remove_llxprt_drops_it_from_config(tmp_path: Path) -> None:
    _write_config(tmp_path, ["llxprt"])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["remove", "llxprt"])

    assert result.exit_code == 0, result.output
    assert "llxprt" not in load_agent_config(tmp_path).available


def test_list_reports_llxprt_against_its_global_command_root(tmp_path: Path) -> None:
    _write_config(tmp_path, ["llxprt"])

    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0, result.output
    assert "llxprt" in result.output
    assert "global" in result.output
