"""Policy configuration schema and loader.

Reads the ``policy`` section from ``.kittify/config.yaml``.
Returns all-defaults when the section is absent, so existing
projects are never broken on upgrade.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from specify_cli.core.constants import KITTY_SPECS_DIR

logger = logging.getLogger(__name__)

VALID_MODES = frozenset({"warn", "block", "off"})
_DEFAULT_MODE = "warn"
_FAIL_CLOSED_MODE = "block"


def _resolve_mode(section: str, raw: object) -> str:
    """Resolve a policy section's mode (#5754).

    Absent/null -> ``warn``; a case/whitespace-tolerant match of a valid mode
    -> that mode; anything else fails closed to ``block`` with one warning.
    """
    if raw is None:
        return _DEFAULT_MODE
    candidate = str(raw).strip().lower()
    if candidate in VALID_MODES:
        return candidate
    logger.warning(
        "policy.%s.mode %r is not one of %s; using %r so the gate fails closed",
        section,
        raw,
        ", ".join(sorted(VALID_MODES)),
        _FAIL_CLOSED_MODE,
    )
    return _FAIL_CLOSED_MODE


@dataclass(frozen=True)
class RiskPolicyConfig:
    """Parallelization risk scoring policy."""

    _POLICY_SECTION: ClassVar[str] = "risk"

    enabled: bool = True
    mode: str = "warn"
    threshold: float = 0.6

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _resolve_mode(self._POLICY_SECTION, self.mode))


@dataclass(frozen=True, init=False)
class CommitGuardConfig:
    """Pre-commit ownership guard policy."""

    _POLICY_SECTION: ClassVar[str] = "commit_guard"

    enabled: bool = True
    mode: str = "warn"
    block_mission_specs: bool = True
    enforce_ownership: bool = True

    def __init__(
        self,
        enabled: bool = True,
        mode: str = "warn",
        block_mission_specs: bool = True,
        enforce_ownership: bool = True,
        **legacy: Any,
    ) -> None:
        legacy_block_key = "block_" + KITTY_SPECS_DIR.replace("-", "_")
        if legacy_block_key in legacy:
            block_mission_specs = bool(legacy.pop(legacy_block_key))
        if legacy:
            unexpected = next(iter(legacy))
            raise TypeError(f"Unexpected CommitGuardConfig argument: {unexpected}")
        object.__setattr__(self, "enabled", enabled)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "block_mission_specs", block_mission_specs)
        object.__setattr__(self, "enforce_ownership", enforce_ownership)
        self.__post_init__()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _resolve_mode(self._POLICY_SECTION, self.mode))


@dataclass(frozen=True)
class MergeGateConfig:
    """Evidence-based merge gate policy."""

    _POLICY_SECTION: ClassVar[str] = "merge_gates"

    enabled: bool = True
    mode: str = "warn"
    require_review_approval: bool = True
    require_risk_check: bool = True
    require_deps_complete: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _resolve_mode(self._POLICY_SECTION, self.mode))


@dataclass(frozen=True)
class PolicyConfig:
    """Top-level policy configuration."""

    risk: RiskPolicyConfig = field(default_factory=RiskPolicyConfig)
    commit_guard: CommitGuardConfig = field(default_factory=CommitGuardConfig)
    merge_gates: MergeGateConfig = field(default_factory=MergeGateConfig)


def load_policy_config(repo_root: Path) -> PolicyConfig:
    """Load policy configuration from .kittify/config.yaml.

    Returns all-defaults when the file or ``policy`` section is absent.
    """
    config_file = repo_root / ".kittify" / "config.yaml"

    if not config_file.exists():
        return PolicyConfig()

    try:
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True
        with open(config_file) as f:
            data = yaml.load(f) or {}
    except Exception as exc:
        logger.warning("Failed to read config.yaml for policy: %s", exc)
        return PolicyConfig()

    policy_data = data.get("policy")
    if not isinstance(policy_data, dict):
        return PolicyConfig()

    return _parse_policy(policy_data)


def _parse_policy(data: dict[str, Any]) -> PolicyConfig:
    """Parse the ``policy`` dict from config.yaml."""
    return PolicyConfig(
        risk=_parse_risk(data.get("risk", {})),
        commit_guard=_parse_commit_guard(data.get("commit_guard", {})),
        merge_gates=_parse_merge_gates(data.get("merge_gates", {})),
    )


def _parse_risk(data: Any) -> RiskPolicyConfig:
    if not isinstance(data, dict):
        return RiskPolicyConfig()
    return RiskPolicyConfig(
        enabled=bool(data.get("enabled", True)),
        mode=data.get("mode", "warn"),
        threshold=float(data.get("threshold", 0.6)),
    )


def _parse_commit_guard(data: Any) -> CommitGuardConfig:
    if not isinstance(data, dict):
        return CommitGuardConfig()
    legacy_block_key = "block_" + KITTY_SPECS_DIR.replace("-", "_")
    return CommitGuardConfig(
        enabled=bool(data.get("enabled", True)),
        mode=data.get("mode", "warn"),
        block_mission_specs=bool(data.get("block_mission_specs", data.get(legacy_block_key, True))),
        enforce_ownership=bool(data.get("enforce_ownership", True)),
    )


def _parse_merge_gates(data: Any) -> MergeGateConfig:
    if not isinstance(data, dict):
        return MergeGateConfig()
    return MergeGateConfig(
        enabled=bool(data.get("enabled", True)),
        mode=data.get("mode", "warn"),
        require_review_approval=bool(data.get("require_review_approval", True)),
        require_risk_check=bool(data.get("require_risk_check", True)),
        require_deps_complete=bool(data.get("require_deps_complete", True)),
    )
