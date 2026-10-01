"""Charter preflight — verify charter-derived state before a governed session.

This package implements ``spec-kitty charter preflight`` (FR-006, FR-007,
FR-008) and the matching callable ``run_charter_preflight(...)`` consumed
by ``spec-kitty next`` and ``spec-kitty implement``.

Public surface:

* :class:`CharterPreflightCheck` — one row of the preflight result.
* :class:`CharterPreflightResult` — aggregate result + JSON serialisation.
* :func:`run_charter_preflight` — entry point; never raises.

Performance contract (NFR-001): < 300 ms warm, < 1 s cold.
"""

from specify_cli.charter_runtime.preflight.config import (
    PreflightConfig,
    load_preflight_config,
)
from specify_cli.charter_runtime.preflight.result import (
    CharterPreflightCheck,
    CharterPreflightResult,
)
from specify_cli.charter_runtime.preflight.runner import run_charter_preflight

__all__ = [
    "CharterPreflightCheck",
    "CharterPreflightResult",
    "PreflightConfig",
    "load_preflight_config",
    "run_charter_preflight",
]
