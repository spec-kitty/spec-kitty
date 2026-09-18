"""Configuration loader for the upgrade-nag throttle subsystem.

Public surface
--------------
UpgradeConfig  -- dataclass with ``throttle_seconds`` and ``nag_enabled``.

Resolution order: environment variable > YAML file > default.

Environment variables
---------------------
``SPEC_KITTY_NAG_THROTTLE_SECONDS``
    Integer seconds for the throttle window.  Must satisfy
    ``60 ≤ x ≤ 31_536_000``; out-of-range values fall back to the default
    without raising (CHK025).

``SPEC_KITTY_NO_NAG``
    When set to a truthy string (``1``, ``true``, ``yes``, ``on``), the nag
    is disabled entirely.

YAML file
---------
Path: ``$XDG_CONFIG_HOME/spec-kitty/upgrade.yaml`` (Linux) or the
``platformdirs`` equivalent for the current OS.  If the file is missing,
unreadable, or malformed, defaults apply silently.

Expected schema::

    nag:
      throttle_seconds: 86400
      enabled: true
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.paths import is_windows
from specify_cli.core.env import is_truthy

_LOG = logging.getLogger(__name__)

_DEFAULT_THROTTLE_SECONDS: int = 86_400
_MIN_THROTTLE_SECONDS: int = 60
_MAX_THROTTLE_SECONDS: int = 31_536_000


# ---------------------------------------------------------------------------
# UpgradeConfig
# ---------------------------------------------------------------------------


@dataclass
class UpgradeConfig:
    """Configuration knobs for the upgrade-nag subsystem.

    Attributes:
        throttle_seconds: Minimum seconds between successive nag displays.
            Validated to the range ``[60, 31_536_000]``; out-of-range values
            fall back to the default ``86400`` (CHK025).
        nag_enabled: When ``False``, the nag is suppressed unconditionally.
    """

    throttle_seconds: int
    nag_enabled: bool

    @classmethod
    def load(cls) -> UpgradeConfig:
        """Build an :class:`UpgradeConfig` by resolving env > YAML file > defaults.

        Resolution order:
        1. ``SPEC_KITTY_NAG_THROTTLE_SECONDS`` env var overrides throttle.
        2. ``SPEC_KITTY_NO_NAG`` env var (truthy) disables nag.
        3. YAML file ``$XDG_CONFIG_HOME/spec-kitty/upgrade.yaml`` for both
           ``nag.throttle_seconds`` and ``nag.enabled``.
        4. Defaults: ``throttle_seconds=86400``, ``nag_enabled=True``.

        Missing or malformed YAML is silently ignored.  Out-of-range throttle
        values fall back to the default (no exception, no user-visible output).

        Returns:
            A populated :class:`UpgradeConfig`.
        """
        yaml_data = _load_yaml_config()

        throttle_seconds = _resolve_throttle(yaml_data)
        nag_enabled = _resolve_nag_enabled(yaml_data)

        return cls(throttle_seconds=throttle_seconds, nag_enabled=nag_enabled)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_config_dir() -> str:
    """Resolve the per-user config directory for spec-kitty."""
    try:
        from platformdirs import user_config_dir  # type: ignore[import-untyped,unused-ignore]

        return str(user_config_dir("spec-kitty"))  # type: ignore[no-untyped-call,unused-ignore]
    except ImportError:
        pass

    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "spec-kitty")
    if is_windows():
        app_data = os.environ.get("APPDATA", "")
        if app_data:
            return str(Path(app_data) / "spec-kitty")
        return str(Path.home() / "AppData" / "Roaming" / "spec-kitty")
    # Linux / WSL / other POSIX.
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = xdg if xdg else str(Path.home() / ".config")
    return str(Path(base) / "spec-kitty")


def _load_yaml_config() -> dict[str, Any]:
    """Load and parse the upgrade YAML config file.

    Returns an empty dict if the file is missing, unreadable, or malformed.
    Uses ``ruamel.yaml`` in safe mode.
    """
    config_dir = _resolve_config_dir()
    config_path = Path(config_dir) / "upgrade.yaml"

    if not config_path.exists():
        return {}

    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        with config_path.open(encoding="utf-8") as fh:
            data = yaml.load(fh)

        if not isinstance(data, dict):
            _LOG.debug("UpgradeConfig: YAML root is not a mapping — using defaults")
            return {}
        return dict(data)
    except Exception:  # noqa: BLE001
        _LOG.debug("UpgradeConfig: failed to load YAML config — using defaults", exc_info=True)
        return {}


def _resolve_throttle(yaml_data: dict[str, Any]) -> int:
    """Resolve the throttle window from env > YAML > default.

    Args:
        yaml_data: Parsed YAML config (may be empty).

    Returns:
        A validated throttle in seconds.
    """
    # 1. Environment variable.
    env_val = os.environ.get("SPEC_KITTY_NAG_THROTTLE_SECONDS")
    if env_val is not None:
        parsed = _parse_throttle(env_val, source="env SPEC_KITTY_NAG_THROTTLE_SECONDS")
        if parsed is not None:
            return parsed

    # 2. YAML file.
    nag_section = yaml_data.get("nag")
    if isinstance(nag_section, dict):
        yaml_throttle = nag_section.get("throttle_seconds")
        if yaml_throttle is not None:
            parsed = _parse_throttle(yaml_throttle, source="YAML nag.throttle_seconds")
            if parsed is not None:
                return parsed

    # 3. Default.
    return _DEFAULT_THROTTLE_SECONDS


def _parse_throttle(value: object, *, source: str) -> int | None:
    """Convert *value* to a validated throttle integer or ``None``.

    Returns ``None`` (with a debug log) if the value is not an integer in the
    allowed range.  Does not raise.

    Args:
        value: Raw value from env or YAML.
        source: Description for debug messages.

    Returns:
        Validated integer, or ``None``.
    """
    try:
        int_value = int(str(value))
    except (TypeError, ValueError):
        _LOG.debug(
            "UpgradeConfig: %s=%r is not a valid integer — falling back to default",
            source,
            value,
        )
        return None

    if not (_MIN_THROTTLE_SECONDS <= int_value <= _MAX_THROTTLE_SECONDS):
        _LOG.debug(
            "UpgradeConfig: %s=%d is out of range [%d, %d] — falling back to default",
            source,
            int_value,
            _MIN_THROTTLE_SECONDS,
            _MAX_THROTTLE_SECONDS,
        )
        return None

    return int_value


def _resolve_nag_enabled(yaml_data: dict[str, Any]) -> bool:
    """Resolve ``nag_enabled`` from env > YAML > default (``True``).

    Args:
        yaml_data: Parsed YAML config (may be empty).

    Returns:
        ``False`` if the nag should be disabled; ``True`` otherwise.
    """
    # 1. Environment variable: truthy → disabled.
    env_val = os.environ.get("SPEC_KITTY_NO_NAG", "")
    if is_truthy(env_val):
        return False

    # 2. YAML file.
    nag_section = yaml_data.get("nag")
    if isinstance(nag_section, dict):
        yaml_enabled = nag_section.get("enabled")
        if yaml_enabled is not None:
            return bool(yaml_enabled)

    # 3. Default: enabled.
    return True
