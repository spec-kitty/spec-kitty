"""Merge configuration types and loader.

Provides MergeStrategy enum, MergeConfig dataclass, and load_merge_config()
for reading the ``merge.strategy`` key from ``.kittify/config.yaml``.

Resolution order (FR-005, FR-008):
  CLI --strategy flag > .kittify/config.yaml merge.strategy > default (SQUASH)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class MergeStrategy(StrEnum):
    """Supported merge strategies for the mission→target step.

    Lane→mission merges always use merge commits regardless of this value.
    """

    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass
class MergeConfig:
    """Project-level merge configuration read from .kittify/config.yaml."""

    strategy: MergeStrategy | None = None


class ConfigError(ValueError):
    """Raised when .kittify/config.yaml contains an invalid merge configuration."""


def load_merge_config(repo_root: Path) -> MergeConfig:
    """Read .kittify/config.yaml and return the merge section.

    Args:
        repo_root: Repository root containing ``.kittify/config.yaml``.

    Returns:
        MergeConfig with ``strategy`` populated if set, or ``None`` if absent.

    Raises:
        ConfigError: If ``merge.strategy`` is present but not one of the
            allowed values (merge | squash | rebase). No silent fallback.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return MergeConfig()

    try:
        from ruamel.yaml import YAML
        yaml = YAML(typ="safe")
        data = yaml.load(config_path)
    except Exception:
        # Corrupt or unreadable config — return empty config (fail on merge.strategy
        # validation only, not on yaml parse errors, to avoid breaking unrelated commands).
        return MergeConfig()

    if not isinstance(data, dict):
        return MergeConfig()

    merge_section = data.get("merge")
    if not isinstance(merge_section, dict):
        return MergeConfig()

    raw_strategy = merge_section.get("strategy")
    if raw_strategy is None:
        return MergeConfig()

    allowed = {s.value for s in MergeStrategy}
    if str(raw_strategy) not in allowed:
        raise ConfigError(
            f"Invalid merge.strategy {raw_strategy!r} in .kittify/config.yaml. "
            f"Allowed values: {', '.join(sorted(allowed))}. "
            "No silent fallback — fix the config before merging."
        )

    return MergeConfig(strategy=MergeStrategy(str(raw_strategy)))
