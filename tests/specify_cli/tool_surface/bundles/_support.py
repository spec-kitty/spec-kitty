"""Shared fixtures for plugin bundle tests.

Builds in-memory :class:`SurfacePlan` objects whose instances point at real
files inside a ``tmp_path`` project tree, so projectors can read and stage them.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import (
    SurfaceDefinition,
    SurfaceInstance,
    SurfacePlan,
)


def _definition(kind: ToolSurfaceKind) -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern="x",
        required_policy=RequiredPolicy.OPTIONAL,
        activation_mode=ActivationMode.USER_INVOKED,
        provider_key="test",
        repair_hint="",
    )


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _instance(kind: ToolSurfaceKind, path: Path, owner: str) -> SurfaceInstance:
    return SurfaceInstance(
        definition=_definition(kind),
        path=path,
        exists=path.exists(),
        file_hash=None,
        owner=owner,
    )


def full_plans(project_root: Path) -> list[SurfacePlan]:
    """Build plans carrying every bundleable surface kind, all on disk."""
    skill = _write(
        project_root / ".agents/skills/spec-kitty.plan/SKILL.md", "# plan skill\n"
    )
    doctrine = _write(
        project_root / ".agents/skills/spec-kitty.charter/SKILL.md", "# charter\n"
    )
    agent = _write(project_root / ".claude/agents/architect-alphonso.md", "# arch\n")
    hook = _write(project_root / ".kittify/hooks/hooks.json", "{}\n")
    mcp = _write(project_root / ".mcp.json", "{}\n")
    instances = (
        _instance(ToolSurfaceKind.COMMAND_SKILL, skill, "codex"),
        _instance(ToolSurfaceKind.CHARTER_SKILL, doctrine, "codex"),
        _instance(ToolSurfaceKind.AGENT_PROFILE, agent, "claude"),
        _instance(ToolSurfaceKind.HOOK, hook, "vibe"),
        _instance(ToolSurfaceKind.NATIVE_CONFIG, mcp, "vibe"),
    )
    return [SurfacePlan(tool_key="all", instances=instances, computed_at="t")]


def skills_only_plans(project_root: Path) -> list[SurfacePlan]:
    """Build plans with command skills but NO agent profiles (incomplete)."""
    skill = _write(
        project_root / ".agents/skills/spec-kitty.plan/SKILL.md", "# plan skill\n"
    )
    instances = (_instance(ToolSurfaceKind.COMMAND_SKILL, skill, "codex"),)
    return [SurfacePlan(tool_key="all", instances=instances, computed_at="t")]
