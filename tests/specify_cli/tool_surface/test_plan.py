"""Unit tests for ``tool_surface.plan.SurfacePlanBuilder``."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import SurfaceDefinition, SurfaceInstance
from specify_cli.tool_surface.plan import SurfacePlanBuilder
from specify_cli.tool_surface.registry import ToolSurfaceRegistry
from specify_cli.tool_surface.repair import RepairResult
from specify_cli.tool_surface.status import SurfaceStatus

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_bundle_plans_respect_configured_tools(tmp_path: Path) -> None:
    from specify_cli.tool_surface.service import build_plans_for_bundles

    configured_tools = ("gemini", "codex")
    plans = build_plans_for_bundles(tmp_path, tool_keys=configured_tools)
    assert tuple(plan.tool_key for plan in plans) == configured_tools


@pytest.mark.parametrize("tool_keys", [None, ("gemini", "codex"), (), ["codex", "gemini", "codex"]])
def test_bundle_plans_match_real_assembly_without_writes(tmp_path: Path, canonical_home: None, tool_keys: Sequence[str] | None) -> None:
    from dataclasses import replace

    from specify_cli.tool_surface.service import build_plans_for_bundles, build_providers, build_registry
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    tools = ("codex", "claude", "copilot", "vibe") if tool_keys is None else tuple(tool_keys)
    (tmp_path / "user-notes.txt").write_text("Preserve user bytes.\n", encoding="utf-8")
    roots = {"project": tmp_path, "user-home": Path.home()}
    before = snapshot(roots)
    plans = build_plans_for_bundles(tmp_path, tool_keys=tool_keys)
    assert_unchanged(before, snapshot(roots))
    expected = SurfacePlanBuilder(build_registry(tools), build_providers()).build(tools, tmp_path)
    assert tuple(plan.tool_key for plan in plans) == tools
    assert [replace(plan, computed_at="") for plan in plans] == [replace(plan, computed_at="") for plan in expected]
    if tools:
        assert all(plan.definitions and plan.instances and not plan.diagnostics for plan in plans)
        assert all(instance.owner == plan.tool_key for plan in plans for instance in plan.instances)
    else:
        assert plans == []
    if tool_keys is None:
        defaults = build_plans_for_bundles(tmp_path)
        assert [replace(plan, computed_at="") for plan in defaults] == [replace(plan, computed_at="") for plan in plans]
    assert_unchanged(before, snapshot(roots))


def test_bundle_plans_retain_healthy_configured_surface(tmp_path: Path, canonical_home: None) -> None:
    from importlib.metadata import version

    from specify_cli.session_presence.content import SessionPresenceContent
    from specify_cli.tool_surface.service import build_plans_for_bundles, build_providers
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    target = tmp_path / "GEMINI.md"
    target.write_text(SessionPresenceContent(version("spec-kitty-cli"), "project", "healthy", None).render(), encoding="utf-8")
    roots = {"project": tmp_path, "user-home": Path.home()}
    before = snapshot(roots)
    plans = build_plans_for_bundles(tmp_path, tool_keys=("gemini",))
    assert len(plans) == 1 and plans[0].tool_key == "gemini"
    instances = [instance for instance in plans[0].instances if instance.path == target]
    assert len(instances) == 1
    instance = instances[0]
    assert instance.exists and instance.definition.kind == ToolSurfaceKind.CONTEXT_FILE
    provider = next(provider for provider in build_providers() if provider.can_handle(instance.definition))
    status = provider.probe(instance)
    assert status.state == "present" and not status.findings
    assert_unchanged(before, snapshot(roots))


def _definition(kind: ToolSurfaceKind, provider_key: str) -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern="x/{command}",
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.ALWAYS,
        provider_key=provider_key,
        repair_hint="fix it",
    )


class _FakeProvider:
    """Minimal reporting provider that emits one instance per expand call."""

    provider_key = "fake"

    def __init__(self, kind: ToolSurfaceKind) -> None:
        self._kind = kind

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == self._kind)

    def expand(
        self,
        definition: SurfaceDefinition,
        tool_key: str,
        project_root: Path,
    ) -> list[SurfaceInstance]:
        return [
            SurfaceInstance(
                definition=definition,
                path=project_root / f"{tool_key}.txt",
                exists=False,
                file_hash=None,
                owner=tool_key,
            )
        ]

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(instance=instance, state="missing")

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        return RepairResult(dry_run=dry_run)

    def remove(self, instance: SurfaceInstance) -> bool:
        return True


def test_empty_plan_for_tool_with_no_definitions(tmp_path: Path) -> None:
    builder = SurfacePlanBuilder(ToolSurfaceRegistry(), [_FakeProvider(ToolSurfaceKind.COMMAND_SKILL)])
    plans = builder.build(["codex"], tmp_path)
    assert len(plans) == 1
    assert plans[0].tool_key == "codex"
    assert plans[0].instances == ()


def test_build_expands_definitions(tmp_path: Path) -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_SKILL, "fake"))
    builder = SurfacePlanBuilder(registry, [_FakeProvider(ToolSurfaceKind.COMMAND_SKILL)])
    plans = builder.build(["codex"], tmp_path)
    assert len(plans[0].instances) == 1
    assert plans[0].instances[0].owner == "codex"


def test_kind_filter_excludes_other_kinds(tmp_path: Path) -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_SKILL, "fake"))
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_FILE, "other"))
    builder = SurfacePlanBuilder(registry, [_FakeProvider(ToolSurfaceKind.COMMAND_SKILL)])
    plans = builder.build(["codex"], tmp_path, ToolSurfaceKind.COMMAND_FILE)
    # Filter keeps only COMMAND_FILE definitions, but no provider handles them.
    assert plans[0].instances == ()


def test_no_provider_yields_no_instances(tmp_path: Path) -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.AGENT_PROFILE, "none"))
    builder = SurfacePlanBuilder(registry, [_FakeProvider(ToolSurfaceKind.COMMAND_SKILL)])
    plans = builder.build(["codex"], tmp_path)
    assert plans[0].instances == ()


def test_required_definition_cannot_disappear_from_existing_builder(tmp_path: Path) -> None:
    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_SKILL, "missing"))
    assert registry.get_definitions("codex")
    plan = SurfacePlanBuilder(registry, []).build(["codex"], tmp_path)[0]
    assert plan.instances or getattr(plan, "diagnostics", ()), "A selected required definition vanished without an instance or diagnostic"


@pytest.mark.parametrize("registered", [False, True])
def test_required_missing_or_legacy_owner_is_explicitly_incomplete(tmp_path: Path, registered: bool) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_SKILL, "fake"))
    providers = [_FakeProvider(ToolSurfaceKind.COMMAND_SKILL)] if registered else []
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path))
    assessments = SurfacePlanBuilder(registry, providers).assess(["codex"], inputs).assessments
    assert len(assessments) == 1
    assert not assessments[0].complete
    expected = "assessment_unsupported" if registered else "missing_provider"
    assert assessments[0].diagnostics[0].code == expected


@pytest.mark.parametrize(
    "policy,activation",
    [
        (RequiredPolicy.OPTIONAL, ActivationMode.MANUAL),
        (RequiredPolicy.RESEARCH_GAP, ActivationMode.MANUAL),
        (RequiredPolicy.REPAIRABLE_REQUIRED, ActivationMode.DISABLED),
    ],
)
def test_advisory_or_disabled_absent_owner_is_a_disposition(tmp_path: Path, policy: RequiredPolicy, activation: ActivationMode) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    registry = ToolSurfaceRegistry()
    definition = replace(_definition(ToolSurfaceKind.COMMAND_SKILL, "fake"), required_policy=policy, activation_mode=activation)
    registry.register_definition("codex", definition)
    assessments = (
        SurfacePlanBuilder(registry, [])
        .assess(
            ["codex"],
            AssessmentInputs(OperationRoot("project", "project", tmp_path)),
        )
        .assessments
    )
    assert assessments[0].complete
    assert not assessments[0].effects
    assert assessments[0].dispositions[0].state == "not_applicable"


def test_unreadable_inventory_is_incomplete_not_empty_success(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    class BrokenSource(_FakeProvider):
        def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
            raise OSError("Required source unavailable")

    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", _definition(ToolSurfaceKind.COMMAND_SKILL, "fake"))
    builder = SurfacePlanBuilder(registry, [BrokenSource(ToolSurfaceKind.COMMAND_SKILL)])
    assessments = builder.assess(("codex",), AssessmentInputs(OperationRoot("project", "project", tmp_path))).assessments
    assert not assessments[0].complete
    assert assessments[0].diagnostics[0].code == "inventory_unreadable"


def test_removing_real_required_provider_keeps_definition_coverage(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.service import build_providers, build_registry

    registry = build_registry(("codex",))
    providers = build_providers()
    assert any(p.provider_key == "command_skills" for p in providers)
    providers = [p for p in providers if p.provider_key != "command_skills"]
    assessments = (
        SurfacePlanBuilder(registry, providers)
        .assess(
            ("codex",),
            AssessmentInputs(OperationRoot("project", "project", tmp_path)),
            ToolSurfaceKind.COMMAND_SKILL,
        )
        .assessments
    )
    assert len(assessments) == 1
    assert not assessments[0].complete
    assert assessments[0].owner_key == "command_skills"
    assert assessments[0].diagnostics[0].code == "missing_provider"


@pytest.mark.parametrize("stage", ["expand", "probe"])
@pytest.mark.parametrize("error_type", [OSError, ValueError])
def test_service_assessment_guards_inventory_errors_without_changing_legacy_behavior(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str, error_type: type[Exception]
) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers._registry import SurfaceProviderRegistry, SurfaceRegistration
    from specify_cli.tool_surface.service import run_tool_surfaces

    calls: list[str] = []

    class BrokenInventory(_FakeProvider):
        def __init__(self) -> None:
            super().__init__(ToolSurfaceKind.COMMAND_SKILL)

        def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
            calls.append("expand")
            if stage == "expand":
                raise error_type("required inventory unreadable")
            return super().expand(definition, tool_key, project_root)

        def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
            calls.append("probe")
            raise error_type("required inventory unreadable")

    definition = _definition(ToolSurfaceKind.COMMAND_SKILL, "fake")
    monkeypatch.setattr(SurfaceProviderRegistry, "_registrations", [SurfaceRegistration(BrokenInventory, (definition,), {})])
    with pytest.raises(error_type, match="required inventory unreadable"):
        run_tool_surfaces(tmp_path, ("codex",))
    calls.clear()
    outcome = run_tool_surfaces(tmp_path, ("codex",), assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path)))
    assert len(outcome.assessments) == 1
    assert not outcome.assessments[0].complete
    assert not outcome.assessments[0].effects
    assert outcome.assessments[0].diagnostics[0].code == "inventory_unreadable"
    assert not outcome.report.ok
    assert outcome.report.configured_tools == ("codex",)
    assert outcome.report.summary.errors == 1
    assert outcome.report.findings[0].message == "required inventory unreadable"
    assert calls == (["expand"] if stage == "expand" else ["expand", "probe"])


def test_assessment_kind_selection_does_not_expand_excluded_unreadable_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers._registry import SurfaceProviderRegistry, SurfaceRegistration
    from specify_cli.tool_surface.service import run_tool_surfaces

    expanded: list[ToolSurfaceKind] = []

    class SelectedInventory(_FakeProvider):
        def __init__(self) -> None:
            super().__init__(ToolSurfaceKind.COMMAND_SKILL)

        def can_handle(self, definition: SurfaceDefinition) -> bool:
            return definition.provider_key == self.provider_key

        def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
            expanded.append(definition.kind)
            if definition.kind == ToolSurfaceKind.COMMAND_FILE:
                raise OSError("excluded source unreadable")
            return super().expand(definition, tool_key, project_root)

    definitions = tuple(_definition(kind, "fake") for kind in (ToolSurfaceKind.COMMAND_SKILL, ToolSurfaceKind.COMMAND_FILE))
    monkeypatch.setattr(SurfaceProviderRegistry, "_registrations", [SurfaceRegistration(SelectedInventory, definitions, {})])
    outcome = run_tool_surfaces(
        tmp_path,
        ("codex",),
        kinds=(ToolSurfaceKind.COMMAND_SKILL,),
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path)),
    )
    assert expanded == [ToolSurfaceKind.COMMAND_SKILL]
    assert outcome.assessments[0].diagnostics[0].code == "assessment_unsupported"
    assert len(outcome.report.surfaces) == 1
