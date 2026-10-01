"""Compatibility-shim infrastructure for spec-kitty.

This package owns:
- Loading and validating docs/migrations/shim-registry.yaml
- Classifying each registered shim (pending/overdue/grandfathered/removed)
- The engine behind `spec-kitty doctor shim-registry`
- The upgrade-nag and project-migration compatibility planner (WP01–WP06)

Public API (pre-existing, shim-registry domain):
    check_shim_registry, ShimRegistryReport, ShimStatus, ShimStatusEntry, RegistrySchemaError

Public API (WP01–WP06, upgrade-nag / planner domain):
    Plan, Decision, Safety, Fr023Case,
    plan, classify, register_safety,
    LatestVersionProvider, LatestVersionResult, PyPIProvider, NoNetworkProvider, FakeLatestVersionProvider,
    NagCache, NagCacheRecord,
    UpgradeConfig,
    InstallMethod, detect_runtime,
    UpgradeHint, build_upgrade_hint,
    Invocation, ProjectState, CliStatus, ProjectStatus, MigrationStep,

NOTE: src/specify_cli/shims/ is a DIFFERENT domain (agent-skill shims).
Do not confuse the two packages.

# Baseline audit (2026-04-19): zero modules under src/specify_cli/ carry
# __deprecated__ = True at mission start. Registry begins empty.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pre-existing shim-registry exports (DO NOT REMOVE)
# ---------------------------------------------------------------------------
from specify_cli.compat.registry import RegistrySchemaError
from specify_cli.compat.doctor import ShimRegistryReport, ShimStatus, ShimStatusEntry, check_shim_registry

# ---------------------------------------------------------------------------
# WP01 — Safety classification
# ---------------------------------------------------------------------------
from specify_cli.compat.safety import Safety, classify, register_safety

# ---------------------------------------------------------------------------
# WP02 — Latest-version providers
# ---------------------------------------------------------------------------
from specify_cli.compat.provider import (
    LatestVersionProvider,
    LatestVersionResult,
    PyPIProvider,
    NoNetworkProvider,
    FakeLatestVersionProvider,
)

# ---------------------------------------------------------------------------
# WP03 — Nag cache
# ---------------------------------------------------------------------------
from specify_cli.compat.cache import NagCache, NagCacheRecord

# ---------------------------------------------------------------------------
# WP04 — Upgrade configuration
# ---------------------------------------------------------------------------
from specify_cli.compat.config import UpgradeConfig

# ---------------------------------------------------------------------------
# WP05 — Install-method detection and upgrade hints
# ---------------------------------------------------------------------------
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat._detect.runtime import detect_runtime
from specify_cli.compat.upgrade_hint import UpgradeHint, build_upgrade_hint

# ---------------------------------------------------------------------------
# WP06 — Planner core (dataclasses + entry point)
# ---------------------------------------------------------------------------
from specify_cli.compat.planner import (
    Decision,
    Fr023Case,
    ProjectState,
    CliStatus,
    ProjectStatus,
    MigrationStep,
    Plan,
    Invocation,
    decide,
    plan,
    is_ci_env,
)

# ---------------------------------------------------------------------------
# WP10 — Mode-aware safety predicates for doctor and orchestrator-api
# ---------------------------------------------------------------------------
# Option A wiring: importing `compat` triggers predicate registration once.
# This is safe and non-invasive: register_mode_predicates() is idempotent
# (re-importing replaces the dict entry, no duplication).
from specify_cli.compat.safety_modes import register_mode_predicates as _register_mode_predicates

_register_mode_predicates()

__all__ = [
    # Pre-existing shim-registry domain
    "check_shim_registry",
    "ShimRegistryReport",
    "ShimStatus",
    "ShimStatusEntry",
    "RegistrySchemaError",
    # WP01 — Safety
    "Safety",
    "classify",
    "register_safety",
    # WP02 — Providers
    "LatestVersionProvider",
    "LatestVersionResult",
    "PyPIProvider",
    "NoNetworkProvider",
    "FakeLatestVersionProvider",
    # WP03 — NagCache
    "NagCache",
    "NagCacheRecord",
    # WP04 — Config
    "UpgradeConfig",
    # WP05 — Install method + hints
    "InstallMethod",
    "detect_runtime",
    "UpgradeHint",
    "build_upgrade_hint",
    # WP06 — Planner
    "Decision",
    "Fr023Case",
    "ProjectState",
    "CliStatus",
    "ProjectStatus",
    "MigrationStep",
    "Plan",
    "Invocation",
    "decide",
    "plan",
    # CI predicate (unified helper)
    "is_ci_env",
]
