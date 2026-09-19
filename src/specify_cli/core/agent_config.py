"""Agent configuration (canonical location in core).

This module manages agent configuration that is set during `spec-kitty init`
and used by commands and migrations to select agents for implementation and review.

The configuration is stored in .kittify/config.yaml under the `agents` key
(or `tools` key for projects that ran migration 2.0.1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from kernel.errors import GuardedReadError
from specify_cli.core.config import AI_CHOICES

logger = logging.getLogger(__name__)


class AgentConfigError(GuardedReadError, RuntimeError):
    """Raised when .kittify/config.yaml cannot be parsed or validated."""


@dataclass
class AgentConfig:
    """Full agent configuration.

    Attributes:
        available: List of agent IDs that are available for use
        auto_commit: Whether agents should auto-commit status changes.
            When False, agents may stage changes but MUST NOT create
            commits unless explicitly instructed. Per-command flags
            (--auto-commit/--no-auto-commit) override this setting.
        lint_on_edit: Whether agents should receive automatic linting
            and type-checking feedback after editing files.
    """

    available: list[str] = field(default_factory=list)
    auto_commit: bool = True
    lint_on_edit: bool = False


def load_agent_config(repo_root: Path) -> AgentConfig:
    """Load agent configuration from .kittify/config.yaml.

    Reads from 'agents' key first, then falls back to 'tools' key for
    projects that ran migration 2.0.1 (which renamed 'agents' -> 'tools').

    Args:
        repo_root: Repository root directory

    Returns:
        AgentConfig instance (defaults if not configured)
    """
    config_file = repo_root / ".kittify" / "config.yaml"

    if not config_file.exists():
        logger.warning(f"Config file not found: {config_file}")
        return AgentConfig()

    yaml = YAML()
    yaml.preserve_quotes = True

    try:
        with open(config_file) as f:
            data = yaml.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise AgentConfigError(f"Invalid YAML in {config_file}: {e}") from e

    if data is None:
        data = {}

    # A YAML document need not be a mapping -- a bare scalar or a list parses
    # without error but is not a dict, and the unguarded `data.get(...)` below
    # raised a bare `AttributeError` on it (same defect class as ledger SK-16,
    # `charter status --json`'s leaked-exception bug). Treat a non-mapping top
    # level as a config error, matching the sibling raise two lines above --
    # not a silent default, so the operator learns their config is corrupt
    # instead of getting an unexplained "no agents configured".
    if not isinstance(data, dict):
        raise AgentConfigError(f"Invalid config shape in {config_file}: expected a YAML mapping at the top level, got {type(data).__name__}")

    section = "agents"
    agents_data = data.get(section)
    if agents_data is None or agents_data == {}:
        section = "tools"
        agents_data = data.get(section)
    if agents_data is None:
        agents_data = {}
    if not isinstance(agents_data, dict):
        raise AgentConfigError(f"Invalid config shape in {config_file}: expected a YAML mapping for {section}, got {type(agents_data).__name__}")

    # Parse settings from either the agents/tools dict or the top level
    auto_commit_raw = agents_data.get("auto_commit")
    lint_on_edit_raw = agents_data.get("lint_on_edit")

    if auto_commit_raw is None:
        auto_commit_raw = data.get("auto_commit")
    if lint_on_edit_raw is None:
        lint_on_edit_raw = data.get("lint_on_edit")

    auto_commit = auto_commit_raw if isinstance(auto_commit_raw, bool) else True
    lint_on_edit = lint_on_edit_raw if isinstance(lint_on_edit_raw, bool) else False

    if not agents_data:
        logger.info("No agents section in config.yaml")
        return AgentConfig(auto_commit=auto_commit, lint_on_edit=lint_on_edit)

    # Parse available agents
    available = agents_data.get("available", [])
    if isinstance(available, str):
        available = [available]
    if not isinstance(available, list):
        raise AgentConfigError("Invalid agents.available in config.yaml: expected a list of agent keys")

    invalid_agents = [agent for agent in available if agent not in AI_CHOICES]
    if invalid_agents:
        valid_agents = ", ".join(sorted(AI_CHOICES.keys()))
        unknown = ", ".join(sorted(invalid_agents))
        raise AgentConfigError(f"Unknown agent key(s) in config.yaml: {unknown}. Valid agents: {valid_agents}")

    return AgentConfig(available=available, auto_commit=auto_commit, lint_on_edit=lint_on_edit)


def save_agent_config(repo_root: Path, config: AgentConfig) -> None:
    """Save agent configuration to .kittify/config.yaml.

    Merges with existing config (preserves other sections like vcs).

    Args:
        repo_root: Repository root directory
        config: AgentConfig to save
    """
    config_dir = repo_root / ".kittify"
    config_file = config_dir / "config.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    # Load existing config or create new
    if config_file.exists():
        with open(config_file) as f:
            data = yaml.load(f) or {}
    else:
        data = {}
        config_dir.mkdir(parents=True, exist_ok=True)

    # Update agents section
    data["agents"] = {
        "available": config.available,
        "auto_commit": config.auto_commit,
        "lint_on_edit": config.lint_on_edit,
    }

    # Write back
    with open(config_file, "w") as f:
        yaml.dump(data, f)

    logger.info(f"Saved agent config to {config_file}")


def get_configured_agents(repo_root: Path) -> list[str]:
    """Get list of configured agents.

    This is the DEFINITIVE list of available agents, set during init.

    Args:
        repo_root: Repository root directory

    Returns:
        List of agent IDs, empty if not configured
    """
    config = load_agent_config(repo_root)
    return config.available


def get_auto_commit_default(repo_root: Path) -> bool:
    """Get the auto_commit default from project config.

    This is the project-level setting that commands should use as their
    default for auto-commit behavior. Per-command flags (--auto-commit/
    --no-auto-commit) override this value.

    Args:
        repo_root: Repository root directory

    Returns:
        True if auto-commit is enabled (the default), False if disabled
    """
    config = load_agent_config(repo_root)
    return config.auto_commit


__all__ = [
    "AgentConfig",
    "AgentConfigError",
    "load_agent_config",
    "save_agent_config",
    "get_configured_agents",
    "get_auto_commit_default",
]
