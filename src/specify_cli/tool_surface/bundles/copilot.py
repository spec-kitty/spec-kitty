"""GitHub Copilot CLI plugin bundle projection and validation.

Projects the canonical tool surfaces into the Copilot CLI / VS Code bundle
layout: a root-level ``plugin.json`` manifest, ``skills/<name>/SKILL.md`` command
skills, ``agents/<profile-id>.agent.md`` native agent profiles, a root
``hooks.json``, and a root ``.mcp.json``. Session-presence files are excluded.

**Scope guard (FR-016, C-006):** projection writes only staging files under the
caller-supplied ``output_dir`` and returns an inert :class:`PluginBundle`. It
never installs, registers, enables, or publishes the bundle to any marketplace.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..enums import ToolSurfaceKind
from ..model import SurfacePlan
from .claude import _validate_bundle
from .model import (
    TARGET_COPILOT,
    BundleEntry,
    BundleValidationResult,
    PluginBundle,
)
from .projection import (
    BUNDLE_SURFACE_KINDS,
    bundle_entries_for_plans,
    plugin_manifest_payload,
    write_bundle,
)

# Copilot / VS Code layout: ``plugin.json`` at the package root, ``hooks.json``
# at root (NOT under ``hooks/``), and ``.mcp.json`` at root.
_MANIFEST_NAME = "plugin.json"

_COPILOT_LAYOUT: dict[ToolSurfaceKind, str] = {
    ToolSurfaceKind.COMMAND_SKILL: "skills",
    ToolSurfaceKind.CHARTER_SKILL: "skills",
    ToolSurfaceKind.AGENT_PROFILE: "agents",
    ToolSurfaceKind.HOOK: "",
    ToolSurfaceKind.NATIVE_CONFIG: "",
}

_REQUIRED_KINDS: frozenset[ToolSurfaceKind] = frozenset(
    {
        ToolSurfaceKind.COMMAND_SKILL,
        ToolSurfaceKind.CHARTER_SKILL,
        ToolSurfaceKind.AGENT_PROFILE,
    }
)


def _agent_filename(profile_id: str) -> str:
    """Copilot / VS Code use the ``<profile-id>.agent.md`` agent file suffix."""
    return f"{profile_id}.agent.md"


class CopilotBundleProjector:
    """Project + validate Copilot CLI plugin bundles (staging only)."""

    distribution_target = TARGET_COPILOT
    # Copilot / VS Code keep the manifest at the package root.
    manifest_relative_path = _MANIFEST_NAME
    layout: dict[ToolSurfaceKind, str] = _COPILOT_LAYOUT

    def entries(self, plan: Sequence[SurfacePlan], project_root: Path) -> tuple[BundleEntry, ...]:
        """Select the canonical members without writing the staging tree."""
        return bundle_entries_for_plans(
            plan, project_root, layout=self.layout,
            agent_filename=_agent_filename, bundle_kinds=BUNDLE_SURFACE_KINDS,
        )

    def project(
        self,
        plan: Sequence[SurfacePlan],
        project_root: Path,
        output_dir: Path,
    ) -> PluginBundle:
        """Project all bundleable surfaces into the Copilot/VS Code layout."""
        entries = self.entries(plan, project_root)
        manifest = plugin_manifest_payload(self.distribution_target)
        write_bundle(output_dir, entries, _MANIFEST_NAME, manifest)
        return PluginBundle(
            distribution_target=self.distribution_target,
            entries=entries,
            manifest_path=output_dir / _MANIFEST_NAME,
        )

    def validate(
        self,
        bundle: PluginBundle,
        required_surface_kinds: set[ToolSurfaceKind] | None = None,
    ) -> BundleValidationResult:
        """Validate that every required surface kind is present in ``bundle``."""
        required = (
            frozenset(required_surface_kinds)
            if required_surface_kinds is not None
            else _REQUIRED_KINDS
        )
        return _validate_bundle(bundle, required)
