"""Unit tests for ``tool_surface.status.SurfaceStatusService``."""

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
from specify_cli.tool_surface.findings import (
    GENERATED_SURFACE_MISSING,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    make_finding,
)
from specify_cli.tool_surface.model import (
    SurfaceDefinition,
    SurfaceInstance,
    SurfacePlan,
)
from specify_cli.tool_surface.repair import RepairResult
from specify_cli.tool_surface.status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_PRESENT,
    STATE_UNSUPPORTED,
    SurfaceStatus,
    SurfaceStatusService,
    _surface_id,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DEF = SurfaceDefinition(
    kind=ToolSurfaceKind.COMMAND_SKILL,
    source_kind=SourceKind.GENERATED,
    install_scope=InstallScope.PROJECT,
    path_pattern=".agents/skills/spec-kitty-{command}/SKILL.md",
    required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
    activation_mode=ActivationMode.SKILLS_INVOKABLE,
    provider_key="command_skills",
    repair_hint="fix",
)


def _instance(name: str) -> SurfaceInstance:
    return SurfaceInstance(
        definition=_DEF,
        path=Path("/proj") / name,
        exists=False,
        file_hash=None,
        owner="codex",
    )


class _StubProvider:
    provider_key = "command_skills"

    def __init__(self, mapping: dict[str, SurfaceStatus]) -> None:
        self._mapping = mapping

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == ToolSurfaceKind.COMMAND_SKILL)

    def expand(
        self, definition: SurfaceDefinition, tool_key: str, project_root: Path
    ) -> list[SurfaceInstance]:
        return []

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        return self._mapping[instance.path.name]

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


def _plan(instances: list[SurfaceInstance]) -> SurfacePlan:
    return SurfacePlan(tool_key="codex", instances=tuple(instances), computed_at="t")


def test_ok_when_all_present() -> None:
    inst = _instance("a")
    provider = _StubProvider({"a": SurfaceStatus(instance=inst, state=STATE_PRESENT)})
    report = SurfaceStatusService([provider]).collect(Path("/proj"), [_plan([inst])])
    assert report.ok is True
    assert report.summary.present == 1
    assert report.findings == ()


def test_missing_emits_finding_and_not_ok() -> None:
    inst = _instance("a")
    status = SurfaceStatus(
        instance=inst,
        state=STATE_MISSING,
        findings=(
            make_finding(
                GENERATED_SURFACE_MISSING,
                SEVERITY_ERROR,
                "missing",
                repair_command="spec-kitty doctor tool-surfaces --fix",
            ),
        ),
    )
    provider = _StubProvider({"a": status})
    report = SurfaceStatusService([provider]).collect(Path("/proj"), [_plan([inst])])
    assert report.ok is False
    assert report.summary.missing == 1
    assert report.summary.errors == 1
    assert report.findings[0].code == "generated-surface-missing"
    entry = report.surfaces[0].to_json()
    assert entry["repair_command"] == "spec-kitty doctor tool-surfaces --fix"


def test_drift_counts_as_warning_but_still_ok() -> None:
    inst = _instance("a")
    status = SurfaceStatus(
        instance=inst,
        state=STATE_DRIFTED,
        findings=(make_finding("managed-file-drift", SEVERITY_WARNING, "drift"),),
    )
    provider = _StubProvider({"a": status})
    report = SurfaceStatusService([provider]).collect(Path("/proj"), [_plan([inst])])
    assert report.ok is True  # warnings do not flip ok
    assert report.summary.drifted == 1
    assert report.summary.warnings == 1


def test_report_has_both_surfaces_and_findings() -> None:
    inst = _instance("a")
    status = SurfaceStatus(
        instance=inst,
        state=STATE_MISSING,
        findings=(make_finding(GENERATED_SURFACE_MISSING, SEVERITY_ERROR, "m"),),
    )
    report = SurfaceStatusService([_StubProvider({"a": status})]).collect(
        Path("/proj"), [_plan([inst])]
    )
    payload = report.to_json()
    assert isinstance(payload["surfaces"], list) and payload["surfaces"]
    assert isinstance(payload["findings"], list) and payload["findings"]
    assert payload["schema_version"] == 1


def test_unsupported_when_no_provider() -> None:
    inst = _instance("a")
    report = SurfaceStatusService([]).collect(Path("/proj"), [_plan([inst])])
    assert report.surfaces[0].state == STATE_UNSUPPORTED


def test_configured_tools_default_from_plans() -> None:
    inst = _instance("a")
    provider = _StubProvider({"a": SurfaceStatus(instance=inst, state=STATE_PRESENT)})
    report = SurfaceStatusService([provider]).collect(Path("/proj"), [_plan([inst])])
    assert report.configured_tools == ("codex",)


def test_surface_ids_are_unique_for_skill_md_siblings() -> None:
    inst_a = _instance(".agents/skills/spec-kitty-plan/SKILL.md")
    inst_b = _instance(".agents/skills/spec-kitty-review/SKILL.md")
    ids = [_surface_id(inst_a), _surface_id(inst_b)]
    assert len(ids) == len(set(ids))
