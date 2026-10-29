"""The ``ledger.retention`` limits for local event-log cleanup (#6610, FR-005).

``spec-kitty doctor event-logs`` deletes gitignored run journals and
per-Mission logs only when BOTH limits are exceeded: an item is outside the
newest ``keep_runs`` of its kind and older than ``max_age_days``. The limits
live in the project's ``.kittify/config.yaml``::

    ledger:
      retention:
        keep_runs: 20
        max_age_days: 30

An absent file, ``ledger`` section or ``retention`` block reads as the
defaults. Unlike the fail-open ``ledger.projection`` reader
(:mod:`specify_cli.core.ledger_posture`), every invalid value refuses with
:class:`RetentionConfigError`: the limits gate a destructive command, so a typo
must never be guessed into a deletion (the ``consolidation/config.py``
precedent).

**Call-site style.** :mod:`~specify_cli.core.ledger_posture` asks callers to
reach its reader through the module attribute so tests can monkeypatch it.
That convention does not apply here: the one caller (``doctor event-logs``)
is tested against a real ``.kittify/config.yaml`` in a temporary project, so
a plain ``from ... import load_retention_limits`` is fine.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

# Only what ``doctor event-logs`` imports is exported; the constants below stay
# public module names (tests read them) without claiming a cross-module caller.
__all__ = [
    "RetentionConfigError",
    "RetentionLimits",
    "load_retention_limits",
]

#: Protect the newest N items of each kind (runs, per-Mission logs).
DEFAULT_KEEP_RUNS = 20
#: And everything younger than this many days.
DEFAULT_MAX_AGE_DAYS = 30
#: ``RetentionLimits.source`` when no ``ledger.retention`` block is configured.
DEFAULT_SOURCE = "default"
#: ``RetentionLimits.source`` when the limits come from the project config.
CONFIG_SOURCE = ".kittify/config.yaml"

_KEEP_RUNS_KEY = "keep_runs"
_MAX_AGE_DAYS_KEY = "max_age_days"
_KNOWN_KEYS = (_KEEP_RUNS_KEY, _MAX_AGE_DAYS_KEY)
_SECTION_KEY = "ledger"
_RETENTION_KEY = "retention"
_FIX_HINT = f"Fix it in {CONFIG_SOURCE}"


class RetentionConfigError(ValueError):
    """``ledger.retention`` is present but invalid; nothing may be scanned or deleted."""


@dataclass(frozen=True)
class RetentionLimits:
    """The effective retention limits and where they came from."""

    keep_runs: int = DEFAULT_KEEP_RUNS
    max_age_days: int = DEFAULT_MAX_AGE_DAYS
    source: str = DEFAULT_SOURCE

    def to_dict(self) -> dict[str, Any]:
        """Return the ``limits`` object of the ``doctor event-logs --json`` report."""
        return {_KEEP_RUNS_KEY: self.keep_runs, _MAX_AGE_DAYS_KEY: self.max_age_days, "source": self.source}


def _load_yaml(config_path: Path) -> object:
    try:
        return YAML(typ="safe").load(config_path)
    except (YAMLError, OSError, UnicodeDecodeError) as exc:
        raise RetentionConfigError(f"{config_path}: could not read the YAML ({exc}). {_FIX_HINT}, then retry.") from exc


def _retention_block(data: object) -> Mapping[str, object] | None:
    """Return the ``ledger.retention`` mapping, ``None`` when absent; refuse a wrong shape."""
    if not isinstance(data, Mapping):
        return None
    ledger = data.get(_SECTION_KEY)
    if ledger is None:
        return None
    if not isinstance(ledger, Mapping):
        raise RetentionConfigError(f"{_SECTION_KEY} must be a mapping, got {ledger!r}. {_FIX_HINT}.")
    block = ledger.get(_RETENTION_KEY)
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise RetentionConfigError(
            f"{_SECTION_KEY}.{_RETENTION_KEY} must be a mapping with {_KEEP_RUNS_KEY} and/or {_MAX_AGE_DAYS_KEY}, got {block!r}. {_FIX_HINT}."
        )
    return block


def _limit_value(block: Mapping[str, object], key: str, default: int) -> int:
    value = block.get(key, default)
    # bool is an int subclass: ``keep_runs: true`` must not read as 1.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RetentionConfigError(f"{_SECTION_KEY}.{_RETENTION_KEY}.{key} must be a whole number >= 0, got {value!r}. {_FIX_HINT} (default {default}).")
    return value


def load_retention_limits(repo_root: Path) -> RetentionLimits:
    """Read ``ledger.retention`` from ``repo_root/.kittify/config.yaml``.

    Raises:
        RetentionConfigError: the YAML cannot be parsed, ``ledger`` or
            ``ledger.retention`` is not a mapping, the block has an unknown
            key, or a limit is not a non-negative integer.
    """
    config_path = repo_root / CONFIG_SOURCE
    if not config_path.exists():
        return RetentionLimits()
    block = _retention_block(_load_yaml(config_path))
    if block is None:
        return RetentionLimits()
    unknown = sorted(str(key) for key in block if key not in _KNOWN_KEYS)
    if unknown:
        raise RetentionConfigError(
            f"{_SECTION_KEY}.{_RETENTION_KEY} has unknown key(s) {', '.join(unknown)}; the known keys are {', '.join(_KNOWN_KEYS)}. {_FIX_HINT}."
        )
    return RetentionLimits(
        keep_runs=_limit_value(block, _KEEP_RUNS_KEY, DEFAULT_KEEP_RUNS),
        max_age_days=_limit_value(block, _MAX_AGE_DAYS_KEY, DEFAULT_MAX_AGE_DAYS),
        source=CONFIG_SOURCE,
    )
