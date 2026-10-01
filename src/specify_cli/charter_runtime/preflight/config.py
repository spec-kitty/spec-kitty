"""Preflight configuration loader (T022 / FR-006 caller contract).

Reads ``preflight.enabled`` and ``preflight.auto_refresh`` from
``.kittify/config.yaml``. The contract
in ``contracts/charter-preflight-json.md`` § "Hook caller contract" says
every consumer (``next``, ``implement``) MUST read this flag
and pass it to :func:`run_charter_preflight`. A consumer MUST NOT pass
``auto_refresh=True`` unconditionally — so the loader's default is
``False``.

Behaviour:

* Missing ``.kittify/config.yaml`` → default config
  (``enabled=True``, ``auto_refresh=False``).
  Pre-existing projects without a ``preflight`` section continue to load.
* Missing ``preflight`` section → default config.
* Corrupt YAML / unreadable file → default config (best-effort; we never
  break unrelated commands because the config is malformed).
* Null / value-less ``preflight.enabled`` → default ``True``. A missing value
  is a reset-to-default, not a safety-gate opt-out.
* Other non-bool values for ``preflight.enabled`` / ``preflight.auto_refresh`` → coerced via
  ``bool()``, matching the lenient policy of the merge-config loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["PreflightConfig", "load_preflight_config"]


@dataclass(frozen=True)
class PreflightConfig:
    """Project-level preflight configuration.

    Attributes:
        enabled: When ``False``, callers skip preflight and proceed. This is a
            project policy knob, not an environment bypass.
        auto_refresh: When ``True`` and the worktree is clean, consumers
            MAY run the safe refresh sequence automatically. Default is
            ``False`` so adoption is opt-in.
    """

    enabled: bool = True
    auto_refresh: bool = False


def load_preflight_config(repo_root: Path) -> PreflightConfig:
    """Read the ``preflight`` section of ``.kittify/config.yaml``.

    Args:
        repo_root: Repository root containing ``.kittify/config.yaml``.

    Returns:
        :class:`PreflightConfig` with ``enabled`` and ``auto_refresh`` populated.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return PreflightConfig()

    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        data = yaml.load(config_path)
    except Exception:  # noqa: BLE001 — best-effort; never break callers.
        return PreflightConfig()

    if not isinstance(data, dict):
        return PreflightConfig()

    section = data.get("preflight")
    if not isinstance(section, dict):
        return PreflightConfig()

    raw_enabled = section.get("enabled", True)
    raw_auto_refresh = section.get("auto_refresh", False)
    return PreflightConfig(
        enabled=True if raw_enabled is None else bool(raw_enabled),
        auto_refresh=bool(raw_auto_refresh),
    )
