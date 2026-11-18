"""Tool availability helpers for Spec Kitty."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from collections.abc import Mapping

if TYPE_CHECKING:
    from specify_cli.cli import StepTracker

from specify_cli.core.config import AGENT_TOOL_REQUIREMENTS, IDE_AGENTS

# Deliberately outside ``agent_user_config_root`` (#7709, D3): Claude Code's docs say
# CLAUDE_CONFIG_DIR moves "settings, session history, and plugins"
# (code.claude.com/docs/en/settings) and name no local-install location under it;
# the native launcher is ~/.local/bin/claude (code.claude.com/docs/en/setup).
CLAUDE_LOCAL_PATH = Path.home() / ".claude" / "local" / "claude"


def check_tool_for_tracker(tool: str, tracker: StepTracker) -> bool:
    """Check if a tool is installed and update the provided StepTracker instance."""
    if shutil.which(tool):
        tracker.complete(tool, "available")
        return True
    tracker.error(tool, "not found")
    return False


def check_tool(tool: str, install_hint: str, agent_name: str | None = None) -> bool:  # noqa: ARG001
    """Return True when the tool is available on PATH (with Claude CLI override and IDE agent bypass).

    IDE-integrated agents (cursor, windsurf, copilot, kilocode) don't require CLI
    installation, so we skip the availability check for them.
    """
    # Skip CLI checks for IDE agents - they run within the IDE, not as CLI tools
    if agent_name and agent_name in IDE_AGENTS:
        return True

    # Special case: Claude local installation
    if tool == "claude" and CLAUDE_LOCAL_PATH.exists() and CLAUDE_LOCAL_PATH.is_file():
        return True

    return shutil.which(tool) is not None


def get_tool_version(command: str) -> str | None:
    """Return the version string for a tool if the convention '<tool> --version' succeeds."""
    try:
        result = subprocess.run(
            [command, "--version"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None

    output = (result.stdout or result.stderr or "").strip()
    return output or None


def check_all_tools(
    requirements: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, tuple[bool, str]]:
    """Check tool availability for all known agents, returning {agent: (ok, detail)}."""
    results: dict[str, tuple[bool, str]] = {}
    entries = requirements or AGENT_TOOL_REQUIREMENTS
    for agent, (tool, url) in entries.items():
        ok = check_tool(tool, url)
        detail = get_tool_version(tool) if ok else url
        results[agent] = (ok, detail or url)
    return results


__all__ = [
    "check_all_tools",
    "check_tool",
    "check_tool_for_tracker",
    "get_tool_version",
]
