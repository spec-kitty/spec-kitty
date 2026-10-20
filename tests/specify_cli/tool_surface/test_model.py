"""Unit tests for tool surface contract data structures."""

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
    NativeAgentProfile,
    SurfaceDefinition,
    SurfaceInstance,
    SurfacePlan,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _definition() -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=ToolSurfaceKind.COMMAND_SKILL,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=".agents/skills/spec-kitty-{command}/SKILL.md",
        required_policy=RequiredPolicy.REQUIRED,
        activation_mode=ActivationMode.USER_INVOKED,
        provider_key="command-skill",
        repair_hint="run spec-kitty upgrade",
    )


def test_surface_definition_is_hashable() -> None:
    definition = _definition()
    # Frozen dataclasses are hashable; this raises if it is not.
    assert hash(definition) == hash(_definition())
    assert {definition: 1}[definition] == 1


def test_surface_instance_absent_has_none_hash() -> None:
    instance = SurfaceInstance(
        definition=_definition(),
        path=Path(".agents/skills/spec-kitty-specify/SKILL.md"),
        exists=False,
        file_hash=None,
        owner="command-skill",
    )
    assert instance.exists is False
    assert instance.file_hash is None


def test_surface_plan_accepts_empty_instances() -> None:
    plan = SurfacePlan(
        tool_key="claude",
        instances=(),
        computed_at="2026-06-14T00:00:00+00:00",
    )
    assert plan.instances == ()
    assert plan.tool_key == "claude"


def test_native_agent_profile_fields() -> None:
    profile = NativeAgentProfile(
        profile_urn="agent_profile:architect-alphonso",
        source_layer="built-in",
        tool_key="claude",
        output_path=Path(".claude/agents/architect-alphonso.md"),
        format="markdown",
        file_hash=None,
    )
    assert profile.source_layer == "built-in"
    assert profile.tool_key == "claude"
