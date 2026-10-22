"""Agent directory configuration utilities.

This module provides constants and functions for working with AI agent directories
across the spec-kitty project. All migrations and commands should import from here
rather than from migration files.
"""

from __future__ import annotations

from pathlib import Path


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
    # (".agent", "workflows") removed (#6470) — Antigravity is a command-skill agent now.
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
    # ".agent" removed (#6470) — Antigravity has no slash-command directory any more.
    ".llxprt": "llxprt",
}


def get_agent_dirs_for_project(project_path: Path) -> list[tuple[str, str]]:
    """Get agent directories to process based on project config.

    Reads config.yaml to determine which agents are enabled and returns
    directories for configured agents only:

    - ``available: [claude]`` returns ``[(".claude", "commands")]``.
    - ``available: []`` returns ``[]``: an explicit empty list means no
      CLI-managed agents (#6494), never every agent.
    - No ``available`` list at all (no config file, or no ``agents``/``tools``
      section) still returns every agent, for legacy projects; #6501 owns
      that case.
    - An unreadable or invalid config raises
      :class:`~specify_cli.core.agent_config.AgentConfigError` naming the
      remedy. It never widens to every agent.

    Args:
        project_path: Path to project root

    Returns:
        List of (agent_root, subdir) tuples for configured agents

    Raises:
        AgentConfigError: ``.kittify/config.yaml`` cannot be read or validated.
    """
    from specify_cli.core.agent_config import load_agent_config

    config = load_agent_config(project_path)
    if not config.available:
        return [] if config.explicit_agent_list else list(AGENT_DIRS)

    return [(agent_root, subdir) for agent_root, subdir in AGENT_DIRS if AGENT_DIR_TO_KEY.get(agent_root) in config.available]
