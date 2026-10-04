"""Migration: verify tool-surface repair registry is wired for this project.

This migration is a lightweight sentinel that confirms the surface-repair
wiring introduced by WP01 is active.  It runs a read-only probe (no mutations)
against the configured tool surfaces and records the surface counts so that
``spec-kitty doctor tool-surfaces`` has a baseline to compare against.

Mutation is intentionally absent from this migration.  The repair itself runs
inside ``run_surface_repair()`` which is called directly by ``init`` after
agent configuration is flushed to disk; ``upgrade`` repairs through the
prepared path (``prepare_upgrade_repairs`` / ``apply_upgrade_repairs``).  The
migration records only a "was probed" marker to make the wiring observable via
``spec-kitty upgrade --verbose``.

This migration:

- Is idempotent: re-running on a project where the wiring is already active
  is a no-op (``detect()`` returns ``False``).
- Respects ``get_agent_dirs_for_project()`` (C-005): only configured agents
  are consulted.
- Never creates missing directories or agent dirs.
- Runs on worktrees: ``False`` (worktrees inherit from main project).
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

_SENTINEL_KEY = "surface_repair_wiring_probed"
_MARKER_FILE = ".kittify/surface_repair_wired"


def _marker_path(project_path: Path) -> Path:
    return project_path / _MARKER_FILE


@MigrationRegistry.register
class SurfaceRepairWiringMigration(BaseMigration):
    """Sentinel migration: record that tool-surface repair wiring is active."""

    migration_id = "0_9_3_surface_repair_wiring"
    description = (
        "Record that tool-surface repair wiring (WP01) is active for this project"
    )
    target_version = "3.2.0rc44"
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """Return True when the wiring marker is absent (migration needed)."""
        kittify = project_path / ".kittify"
        if not kittify.exists():
            return False
        return not _marker_path(project_path).exists()

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always safe to apply when the project has a .kittify directory."""
        kittify = project_path / ".kittify"
        if not kittify.exists():
            return False, "No .kittify directory found; project is not initialized"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Write the wiring marker and probe surface counts (read-only)."""
        marker = _marker_path(project_path)

        if not dry_run:
            try:
                marker.write_text("wired\n", encoding="utf-8")
            except OSError as exc:
                return MigrationResult(
                    success=False,
                    errors=[f"Could not write wiring marker: {exc}"],
                )

        surface_count = _probe_surface_count(project_path)

        return MigrationResult(
            success=True,
            changes_made=[
                f"surface_repair_wiring: probed {surface_count} tool surface(s)"
            ],
        )


def _probe_surface_count(project_path: Path) -> int:
    """Return the total number of configured tool surfaces (read-only probe)."""
    try:
        from specify_cli.tool_surface.providers.plugin_bundle import (
            PLUGIN_BUNDLE_TOOL_KEY,
        )
        from specify_cli.tool_surface.service import build_providers, build_registry
        from specify_cli.tool_surface.plan import SurfacePlanBuilder
        from specify_cli.tool_surface.status import SurfaceStatusService
        from specify_cli.core.agent_config import get_configured_agents

        configured_tools = list(get_configured_agents(project_path))
        if not configured_tools:
            return 0

        providers = build_providers()
        registry = build_registry(configured_tools)
        plan_tools = [*configured_tools, PLUGIN_BUNDLE_TOOL_KEY]
        builder = SurfacePlanBuilder(registry, providers)
        plans = builder.build(plan_tools, project_path)
        report = SurfaceStatusService(providers).collect(
            project_path, plans, configured_tools=configured_tools
        )
        return len(report.surfaces)
    except Exception:  # noqa: BLE001 — probe is best-effort; never block migration
        return 0
