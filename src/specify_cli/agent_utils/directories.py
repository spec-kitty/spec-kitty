"""Agent directory configuration utilities.

This module provides constants and functions for working with AI agent directories
across the spec-kitty project. All migrations and commands should import from here
rather than from migration files.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


# Canonical list of all supported agent directories and their subdirectories
# This is the single source of truth for agent directory configuration
AGENT_DIRS: list[tuple[str, str]] = [
    (".claude", "commands"),
    (".github", "prompts"),
    (".gemini", "commands"),
    (".cursor", "commands"),
    (".qwen", "commands"),
    (".opencode", "command"),
    (".windsurf", "workflows"),
    (".kilocode", "workflows"),
    (".augment", "commands"),
    # ".roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    (".amazonq", "prompts"),
    (".kiro", "prompts"),
    (".agent", "workflows"),
    (".llxprt", "commands"),
]

# Mapping from agent directory to agent key (for config.yaml)
# Note: Some agents have different keys than their directory names
AGENT_DIR_TO_KEY = {
    ".claude": "claude",
    ".github": "copilot",  # copilot, not github
    ".gemini": "gemini",
    ".cursor": "cursor",
    ".qwen": "qwen",
    ".opencode": "opencode",
    ".windsurf": "windsurf",
    ".kilocode": "kilocode",
    ".augment": "auggie",  # auggie, not augment
    # ".roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    ".amazonq": "q",  # q, not amazonq (legacy — Kiro rebrand migrates to .kiro)
    ".kiro": "kiro",
    ".agent": "antigravity",
    ".llxprt": "llxprt",
}


def get_agent_dirs_for_project(project_path: Path) -> list[tuple[str, str]]:
    """Get agent directories to process based on project config.

    Reads config.yaml to determine which agents are enabled.
    Only returns directories for configured agents.
    Falls back to all agents for legacy projects without config.

    Args:
        project_path: Path to project root

    Returns:
        List of (agent_root, subdir) tuples for configured agents

    Examples:
        >>> # Project with only Claude configured
        >>> dirs = get_agent_dirs_for_project(Path("/path/to/project"))
        >>> dirs
        [('.claude', 'commands')]

        >>> # Legacy project without config.yaml
        >>> dirs = get_agent_dirs_for_project(Path("/path/to/legacy"))
        >>> len(dirs)
        13  # All command-layer agents (codex and vibe use AGENT_SKILL_CONFIG; roo removed)
    """
    try:
        from specify_cli.core.agent_config import (
            AgentConfigError,
            get_configured_agents,
        )

        available = get_configured_agents(project_path)

        if not available:
            # Empty config - fallback to all agents
            return list(AGENT_DIRS)

        # Filter AGENT_DIRS to only include configured agents
        configured_dirs = []
        for agent_root, subdir in AGENT_DIRS:
            agent_key = AGENT_DIR_TO_KEY.get(agent_root)
            if agent_key in available:
                configured_dirs.append((agent_root, subdir))

        return configured_dirs

    except AgentConfigError:
        raise
    except Exception:
        # Config missing or error reading - fallback to all agents
        # This handles legacy projects gracefully
        return list(AGENT_DIRS)
