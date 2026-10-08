"""Unit tests for the tool surface registry and provider protocol."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import SurfaceDefinition, SurfaceInstance
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.registry import ToolSurfaceRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _definition(provider_key: str = "command-skill") -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=ToolSurfaceKind.COMMAND_SKILL,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=".agents/skills/spec-kitty.{command}/SKILL.md",
        required_policy=RequiredPolicy.REQUIRED,
        activation_mode=ActivationMode.USER_INVOKED,
        provider_key=provider_key,
        repair_hint="run spec-kitty upgrade",
    )


def test_registry_starts_empty() -> None:
    registry = ToolSurfaceRegistry()
    assert registry.all_tool_keys() == []
    assert registry.get_definitions("claude") == []


def test_register_and_get_roundtrip() -> None:
    registry = ToolSurfaceRegistry()
    definition = _definition()
    registry.register_definition("claude", definition)
    assert registry.get_definitions("claude") == [definition]
    assert registry.all_tool_keys() == ["claude"]


def test_get_definitions_unknown_key_returns_empty_list() -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("claude", _definition())
    assert registry.get_definitions("unknown") == []


def test_get_definitions_returns_copy() -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("claude", _definition())
    returned = registry.get_definitions("claude")
    returned.clear()
    # Mutating the returned list must not affect registry state.
    assert registry.get_definitions("claude") == [_definition()]


def test_multiple_definitions_for_same_tool() -> None:
    registry = ToolSurfaceRegistry()
    first = _definition("command-skill")
    second = _definition("charter-skill")
    registry.register_definition("claude", first)
    registry.register_definition("claude", second)
    assert registry.get_definitions("claude") == [first, second]


class _StubProvider:
    """Minimal structural implementation of the provider protocol."""

    provider_key = "stub"

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return definition.provider_key == self.provider_key

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        return []

    def probe(self, instance: SurfaceInstance) -> object:
        return instance

    def repair(self, *args: object, **kwargs: object) -> object:
        return None


def test_provider_protocol_is_runtime_checkable() -> None:
    assert isinstance(_StubProvider(), ReportingSurfaceProvider)


def test_non_provider_fails_protocol_check() -> None:
    assert not isinstance(object(), ReportingSurfaceProvider)


def _assert_required_registry_floor() -> None:
    from specify_cli.tool_surface.service import build_providers, build_registry

    expected = {
        ToolSurfaceKind.COMMAND_SKILL: "command_skills",
        ToolSurfaceKind.CHARTER_SKILL: "managed_skills",
        ToolSurfaceKind.AGENT_PROFILE: "agent_profiles",
        ToolSurfaceKind.COMMAND_FILE: "slash_commands",
        ToolSurfaceKind.CONTEXT_FILE: "session_presence",
        ToolSurfaceKind.HOOK: "session_presence",
        ToolSurfaceKind.RULE: "session_presence",
        ToolSurfaceKind.NATIVE_CONFIG: "native_config",
    }
    registry = build_registry(("codex", "claude", "vibe"))
    actual = {(d.kind, d.provider_key) for d in registry.get_definitions("codex")}
    assert set(expected.items()) <= actual
    assert set(expected.values()) <= {p.provider_key for p in build_providers()}


def test_concrete_registry_contains_required_owner_floor() -> None:
    _assert_required_registry_floor()


def test_required_registration_removal_breaks_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.providers._registry import SurfaceProviderRegistry

    _assert_required_registry_floor()
    registrations = SurfaceProviderRegistry._registrations
    reduced = [r for r in registrations if r.provider_class.provider_key != "command_skills"]
    assert len(reduced) < len(registrations)
    monkeypatch.setattr(SurfaceProviderRegistry, "_registrations", reduced)
    with pytest.raises(AssertionError):
        _assert_required_registry_floor()


def test_reporting_provider_does_not_imply_assessment_support() -> None:
    from specify_cli.tool_surface.providers.protocol import AssessingSurfaceProvider

    provider = _StubProvider()
    assert isinstance(provider, ReportingSurfaceProvider)
    assert not isinstance(provider, AssessingSurfaceProvider)
