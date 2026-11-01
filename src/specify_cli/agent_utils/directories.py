"""Agent directory configuration utilities.

This module provides constants and functions for working with AI agent directories
across the spec-kitty project. All migrations and commands should import from here
rather than from migration files.
"""

from __future__ import annotations

import logging
from pathlib import Path


logger = logging.getLogger(__name__)

#: Appended to the legacy no-list warning. A config with no ``agents.available``
#: list is a legacy project; the operator is told how to record the set instead
#: of the read guessing it (#6501).
LEGACY_AGENT_LIST_REMEDY = (
    "Record the agents this project uses with `spec-kitty agent config add <agent>` (see `spec-kitty agent config list`); an explicit list is authoritative."
)


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


#: Agent roots shared with a non-agent tool. ``.github`` is a GitHub directory in
#: every repository with CI, so its presence is not evidence that the project uses
#: Copilot; its managed ``prompts/`` surface is the signal instead (#6501).
_SHARED_AGENT_ROOTS = frozenset({".github"})


def observed_agent_dirs(project_path: Path) -> list[tuple[str, str]]:
    """Return the registered agent directories the project already has.

    The project's own agent directory (``.claude/``, ``.gemini/``) is the
    evidence: those names are agent-specific, and a legacy project may hold one
    without its managed ``<subdir>`` yet (a pre-``3.1.2`` layout whose command
    files still want repairing). ``.github`` is the exception — every repository
    with CI has one — so for it the managed surface (``.github/prompts``) is the
    signal. The probe is project-local, so a migration read never depends on
    ``$HOME`` or on the user-global command directories (#6501, NFR-001).

    Args:
        project_path: Path to project root

    Returns:
        Observed ``(agent_root, subdir)`` pairs, in :data:`AGENT_DIRS` order
    """
    observed: list[tuple[str, str]] = []
    for agent_root, subdir in AGENT_DIRS:
        agent_dir = project_path / agent_root
        surface_present = (agent_dir / subdir).is_dir()
        if surface_present or (agent_root not in _SHARED_AGENT_ROOTS and agent_dir.is_dir()):
            observed.append((agent_root, subdir))
    return observed


def get_agent_dirs_for_project(project_path: Path) -> list[tuple[str, str]]:
    """Get agent directories to process based on project config.

    Reads config.yaml to determine which agents are enabled and returns
    directories for configured agents only:

    - ``available: [claude]`` returns ``[(".claude", "commands")]``.
    - ``available: []`` returns ``[]``: an explicit empty list means no
      CLI-managed agents (#6494), never every agent.
    - No ``available`` list at all (no config file, or no ``agents``/``tools``
      section) is a legacy project: it returns only the agent surfaces already
      present in the project (:func:`observed_agent_dirs`), never the whole
      registry, and warns once naming the file, the key and the remedy
      (#6501). A legacy project that has no agent surface gets no agents; the
      read never invents one.
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
        if config.explicit_agent_list:
            return []
        return _legacy_observed_agent_dirs(project_path)

    return [(agent_root, subdir) for agent_root, subdir in AGENT_DIRS if AGENT_DIR_TO_KEY.get(agent_root) in config.available]


#: Projects already warned about in this process. The upgrade chain reads this
#: helper once per migration (~27 times), and repeating one log line adds nothing
#: (#6501, NFR-002); a second process warns again, and a config that gains a list
#: leaves this set unused.
_LEGACY_PROJECTS_WARNED: set[Path] = set()


def _legacy_observed_agent_dirs(project_path: Path) -> list[tuple[str, str]]:
    """Resolve the legacy no-list case to the project's observed agents (#6501).

    Returns the observed set and logs one warning naming the config file, the
    ``agents.available`` key, the agents found and the remedy. Never raises: the
    upgrade migration chain reads this before any list could be recorded, and a
    refusal there would abort a legacy project's upgrade (C-001).
    """
    observed = observed_agent_dirs(project_path)
    warn_key = project_path.resolve()
    if warn_key not in _LEGACY_PROJECTS_WARNED:
        _LEGACY_PROJECTS_WARNED.add(warn_key)
        found = ", ".join(AGENT_DIR_TO_KEY[agent_root] for agent_root, _ in observed) or "none found"
        logger.warning(
            "%s has no agents.available list (legacy project). Using the agents whose project surface already exists: %s. %s",
            project_path / ".kittify" / "config.yaml",
            found,
            LEGACY_AGENT_LIST_REMEDY,
        )
    return observed
