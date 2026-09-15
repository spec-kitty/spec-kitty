"""Unit tests for ``tool_surface.repair.SurfaceRepairService``."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.tool_surface.model import SurfaceSelection

from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import SurfaceDefinition, SurfaceInstance
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, Diagnostic, OwnerApplyResult, OwnerAssessment
from specify_cli.tool_surface.repair import RepairResult, SurfaceRepairService
from specify_cli.tool_surface.status import STATE_MISSING, SurfaceStatus, _surface_id

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _definition(kind: ToolSurfaceKind) -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern="x/{command}",
        required_policy=RequiredPolicy.REPAIRABLE_REQUIRED,
        activation_mode=ActivationMode.ALWAYS,
        provider_key="p",
        repair_hint="fix",
    )


def _status(kind: ToolSurfaceKind, name: str) -> SurfaceStatus:
    inst = SurfaceInstance(
        definition=_definition(kind),
        path=Path("/proj") / name,
        exists=False,
        file_hash=None,
        owner="codex",
    )
    return SurfaceStatus(instance=inst, state=STATE_MISSING)


class _RecordingProvider:
    provider_key = "p"

    def __init__(self, kind: ToolSurfaceKind) -> None:
        self._kind = kind
        self.received: list[SurfaceStatus] = []

    def can_handle(self, definition: SurfaceDefinition) -> bool:
        return bool(definition.kind == self._kind)

    def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
        return []

    def probe(self, instance: SurfaceInstance) -> SurfaceStatus:
        return SurfaceStatus(instance=instance, state=STATE_MISSING)

    def repair(
        self,
        project_root: Path,
        statuses: Sequence[SurfaceStatus],
        *,
        dry_run: bool = False,
    ) -> RepairResult:
        self.received.extend(statuses)
        return RepairResult(
            repaired=tuple(_surface_id(s.instance) for s in statuses),
            dry_run=dry_run,
        )

    def remove(self, instance: SurfaceInstance) -> bool:
        return True


def test_no_provider_records_failure_not_raise() -> None:
    service = SurfaceRepairService([])
    result = service.repair(Path("/proj"), [_status(ToolSurfaceKind.COMMAND_SKILL, "a")])
    assert isinstance(result, RepairResult)
    assert len(result.failed) == 1
    assert result.repaired == ()


def test_delegates_to_provider() -> None:
    provider = _RecordingProvider(ToolSurfaceKind.COMMAND_SKILL)
    service = SurfaceRepairService([provider])
    status = _status(ToolSurfaceKind.COMMAND_SKILL, "a")
    result = service.repair(Path("/proj"), [status])
    assert provider.received == [status]
    assert len(result.repaired) == 1


def test_takes_status_objects_and_preserves_instance() -> None:
    provider = _RecordingProvider(ToolSurfaceKind.COMMAND_SKILL)
    service = SurfaceRepairService([provider])
    status = _status(ToolSurfaceKind.COMMAND_SKILL, "a")
    service.repair(Path("/proj"), [status])
    # The provider received the original SurfaceStatus, carrying its instance.
    assert provider.received[0].instance is status.instance


def test_kind_filter_selects_subset() -> None:
    provider = _RecordingProvider(ToolSurfaceKind.COMMAND_SKILL)
    service = SurfaceRepairService([provider])
    skill = _status(ToolSurfaceKind.COMMAND_SKILL, "a")
    other = _status(ToolSurfaceKind.COMMAND_FILE, "b")
    service.repair(Path("/proj"), [skill, other], kinds={ToolSurfaceKind.COMMAND_SKILL})
    assert provider.received == [skill]


def test_dry_run_passed_through() -> None:
    provider = _RecordingProvider(ToolSurfaceKind.COMMAND_SKILL)
    service = SurfaceRepairService([provider])
    result = service.repair(Path("/proj"), [_status(ToolSurfaceKind.COMMAND_SKILL, "a")], dry_run=True)
    assert result.dry_run is True


def test_shared_owner_legacy_repair_keeps_both_original_statuses() -> None:
    from dataclasses import replace

    provider = _RecordingProvider(ToolSurfaceKind.COMMAND_SKILL)
    codex = _status(ToolSurfaceKind.COMMAND_SKILL, "shared")
    vibe = replace(codex, instance=replace(codex.instance, owner="vibe", file_hash="source-context"))
    result = SurfaceRepairService([provider]).repair(Path("/proj"), [codex, vibe])
    assert provider.received[0] is codex
    assert provider.received[1] is vibe
    assert set(result.repaired) == {_surface_id(codex.instance), _surface_id(vibe.instance)}


# Recording owners prove dispatch mechanics; concrete filesystem races belong to owner WPs.
class _AssessmentProvider(_RecordingProvider):
    def __init__(self) -> None:
        super().__init__(ToolSurfaceKind.COMMAND_SKILL)
        self.inputs: AssessmentInputs | None = None
        self.assessment: OwnerAssessment | None = None
        self.checked = False
        self.locked = False
        self.changed = False
        self.write_calls = 0
        self.partial = False

    def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
        return [SurfaceInstance(definition, project_root / "shared", False, None, tool_key)]

    def assess(self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...] = ()) -> OwnerAssessment:
        from hashlib import sha256  # noqa: TID251 - exact prepared file-byte integrity, not charter hashing.
        from specify_cli.tool_surface.operations import FileState, OwnerAssessment, OwnershipProof, PhysicalEffect

        self.inputs = inputs
        self.received.extend(statuses)
        effects = tuple(
            PhysicalEffect(
                "p",
                "surface_repair",
                inputs.root,
                status.instance.path.name,
                "create",
                FileState("absent"),
                FileState("file", sha256=sha256(b"T1").hexdigest(), mode=0o644),
                "Missing",
                (OwnershipProof("managed_path", "catalog:" + status.instance.path.name),),
                (status.instance.owner,),
                (_surface_id(status.instance),),
            )
            for status in statuses
        )
        self.assessment = OwnerAssessment("p", inputs.root, effects=effects, prepared=b"T1")
        return self.assessment

    def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
        from contextlib import contextmanager
        from specify_cli.tool_surface.operations import Diagnostic

        @contextmanager
        def locked_batch() -> Iterator[tuple[Diagnostic, ...]]:
            self.checked = True
            self.locked = True
            try:
                yield (Diagnostic("precondition_changed", "p", "error", "Source changed"),) if self.changed else ()
            finally:
                self.locked = False

        return locked_batch()

    def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        from specify_cli.tool_surface.operations import Diagnostic, OwnerApplyResult

        assert self.checked and self.locked, "writer called without whole-batch locked recheck"
        assert explicit_consent.automatic
        assert assessment.prepared == b"T1"
        self.write_calls += 1
        ids = tuple(effect.id for effect in assessment.effects)
        if self.partial:
            return OwnerApplyResult(
                "p", succeeded=ids[:1], failed=ids[1:2], skipped=ids[2:], outcome="partial", diagnostics=(Diagnostic("io_error", "p", "error", "Disk full"),)
            )
        return OwnerApplyResult("p", succeeded=ids)


def _assess(provider: _AssessmentProvider, statuses: Sequence[SurfaceStatus]) -> tuple[SurfaceRepairService, tuple[OwnerAssessment, ...], AssessmentInputs]:
    from specify_cli.tool_surface.model import SurfacePlan
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    root = OperationRoot("project", "project", Path("/proj"))
    inputs = AssessmentInputs(root, projected=(("activation", ("commands",)),))
    plan = SurfacePlan("codex", tuple(s.instance for s in statuses), "T1", definitions=(_definition(ToolSurfaceKind.COMMAND_SKILL),))
    service = SurfaceRepairService([provider])
    return service, service.assess(inputs, statuses, plans=(plan,)), inputs


def test_assessment_dispatch_preserves_original_context_and_projected_inputs() -> None:
    provider = _AssessmentProvider()
    status = _status(ToolSurfaceKind.COMMAND_SKILL, "a")
    _, assessments, inputs = _assess(provider, (status,))
    assert provider.inputs is inputs
    assert provider.received[0] is status
    assert provider.assessment is not None
    assert assessments[0].prepared is provider.assessment.prepared


def test_apply_rechecks_whole_batch_and_returns_actual_partial_ids() -> None:
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    provider.partial = True
    statuses = tuple(_status(ToolSurfaceKind.COMMAND_SKILL, name) for name in ("a", "b", "c"))
    service, assessments, _ = _assess(provider, statuses)
    result = service.apply_assessments(assessments, ApplyConsent(automatic=True))[0]
    ids = tuple(e.id for e in assessments[0].effects)
    assert result.succeeded == ids[:1]
    assert result.failed == ids[1:2]
    assert result.skipped == ids[2:]
    assert result.outcome == "partial"
    assert provider.write_calls == 1
    assert not provider.locked


def test_changed_precondition_stops_writer_and_never_retries() -> None:
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    provider.changed = True
    result = service.apply_assessments(assessments, ApplyConsent(automatic=True))[0]
    assert result.outcome == "precondition_changed"
    assert not result.succeeded
    assert provider.write_calls == 0
    assert provider.checked


def test_recheck_bypass_negative_control_is_detected() -> None:
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    _, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    with pytest.raises(AssertionError, match="without whole-batch"):
        provider.apply(assessments[0], ApplyConsent(automatic=True))


def test_unchanged_batch_does_not_recheck_or_invoke_writer() -> None:
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, ())
    result = service.apply_assessments(assessments, ApplyConsent(automatic=True))[0]
    assert not result.succeeded
    assert provider.write_calls == 0
    assert not provider.checked


def test_shared_destination_applies_once_retaining_both_logical_owners() -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    codex = _status(ToolSurfaceKind.COMMAND_SKILL, "a")
    vibe = replace(codex, instance=replace(codex.instance, owner="vibe"))
    service, assessments, _ = _assess(provider, (vibe, codex))
    assert len(assessments[0].effects) == 1
    assert assessments[0].effects[0].logical_owners == ("codex", "vibe")
    results = service.apply_assessments(assessments, ApplyConsent(automatic=True))
    assert len(results[0].succeeded) == 1
    assert provider.write_calls == 1


def test_conflicting_assessments_refuse_application() -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import ApplyConsent, FileState

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    conflict = replace(assessments[0], effects=(replace(assessments[0].effects[0], after=FileState("file", sha256="f" * 64, mode=0o644)),))
    results = service.apply_assessments((*assessments, conflict), ApplyConsent(automatic=True))
    assert all(not result.succeeded for result in results)
    assert any(d.code == "owner_conflict" for r in results for d in r.diagnostics)
    assert provider.write_calls == 0


def test_no_automatic_consent_invokes_no_writer() -> None:
    from specify_cli.tool_surface.operations import ApplyConsent

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    result = service.apply_assessments(assessments, ApplyConsent())[0]
    assert result.skipped == tuple(e.id for e in assessments[0].effects)
    assert provider.write_calls == 0


def test_registered_service_assesses_shared_root_through_real_builder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import OperationRoot
    from specify_cli.tool_surface.providers._registry import SurfaceProviderRegistry, SurfaceRegistration
    from specify_cli.tool_surface.service import run_tool_surfaces

    registration = SurfaceRegistration(_AssessmentProvider, (_definition(ToolSurfaceKind.COMMAND_SKILL),), {})
    monkeypatch.setattr(SurfaceProviderRegistry, "_registrations", [registration])
    outcome = run_tool_surfaces(tmp_path, ("vibe", "codex"), assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path)))
    assessments = outcome.assessments
    assert outcome.report.surfaces[0].instance.owner == "vibe"
    assert "assessments" not in outcome.to_json(), "Pinned legacy report JSON stays unchanged"
    assert len(assessments) == 1
    assert assessments[0].complete
    assert len(assessments[0].effects) == 1
    assert assessments[0].effects[0].logical_owners == ("codex", "vibe")


@pytest.mark.parametrize("scenario", ["incomplete", "consent_changed", "provider_missing", "preparation_changed"])
def test_refused_batch_does_not_enter_writer(scenario: str) -> None:
    from dataclasses import replace

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    consent = ApplyConsent(automatic=True)
    if scenario == "incomplete":
        assessments = (replace(assessments[0], complete=False),)
    elif scenario == "consent_changed":
        consent = ApplyConsent(automatic=True, overwrite_paths=("a",))
    elif scenario == "provider_missing":
        service = SurfaceRepairService([])
    else:
        assessments = (*assessments, replace(assessments[0], prepared=b"T2"))
    results = service.apply_assessments(assessments, consent)
    assert all(r.outcome == "failed" and not r.succeeded for r in results)
    assert provider.write_calls == 0


def test_existing_service_rejects_assessment_plus_fix(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces

    with pytest.raises(ValueError, match="cannot be combined with fix"):
        run_tool_surfaces(tmp_path, ("codex",), fix=True, assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path)))


def test_overlapping_owner_root_batches_cannot_write_same_destination_twice() -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import OperationRoot

    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    other = replace(assessments[0], root=OperationRoot("global", "global", Path("/")))
    results = service.apply_assessments((*assessments, other), ApplyConsent(automatic=True))
    assert any(d.code == "owner_conflict" for r in results for d in r.diagnostics)
    assert provider.write_calls == 0


def test_duplicate_prepared_batch_is_applied_once() -> None:
    provider = _AssessmentProvider()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    results = service.apply_assessments((*assessments, *assessments), ApplyConsent(automatic=True))
    assert len(results) == 1
    assert provider.write_calls == 1


def test_omitted_result_ids_cannot_report_full_success() -> None:
    class OmittingOwner(_AssessmentProvider):
        def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
            result = super().apply(assessment, explicit_consent)
            return OwnerApplyResult("p", succeeded=result.succeeded[:1])

    provider = OmittingOwner()
    service, assessments, _ = _assess(provider, tuple(_status(ToolSurfaceKind.COMMAND_SKILL, n) for n in ("a", "b")))
    result = service.apply_assessments(assessments, ApplyConsent(automatic=True))[0]
    assert result.outcome == "partial"
    assert result.succeeded == (assessments[0].effects[0].id,)
    assert result.skipped == (assessments[0].effects[1].id,)
    assert result.diagnostics[0].code == "unreported_effects"


def test_foreign_result_ids_are_rejected() -> None:
    class WrongOwner(_AssessmentProvider):
        def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
            return OwnerApplyResult("p", succeeded=("not-an-assessed-id",))

    service, assessments, _ = _assess(WrongOwner(), (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    with pytest.raises(ValueError, match="outside its assessed batch"):
        service.apply_assessments(assessments, ApplyConsent(automatic=True))


def test_unreadable_owner_source_reports_incomplete() -> None:
    class UnreadableOwner(_AssessmentProvider):
        def assess(self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...] = ()) -> OwnerAssessment:
            raise OSError("source unavailable")

    provider = UnreadableOwner()
    _, assessments, _ = _assess(provider, ())
    assert not assessments[0].complete
    assert assessments[0].diagnostics[0].code == "assessment_failed"


def test_conflict_inside_single_owner_stays_incomplete_and_refuses_apply() -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import FileState

    class ConflictingOwner(_AssessmentProvider):
        def assess(self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...] = ()) -> OwnerAssessment:
            assessment = super().assess(inputs, statuses, selections=selections)
            contradictory = replace(assessment.effects[0], after=FileState("file", sha256="f" * 64, mode=0o644))
            return replace(assessment, effects=(*assessment.effects, contradictory))

    provider = ConflictingOwner()
    service, assessments, _ = _assess(provider, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    assert not assessments[0].complete
    assert assessments[0].diagnostics[0].code == "owner_conflict"
    result = service.apply_assessments(assessments, ApplyConsent(automatic=True))[0]
    assert not result.succeeded
    assert provider.write_calls == 0


@pytest.mark.parametrize("tool", [None, "codex", "vibe"])
@pytest.mark.parametrize("kind", [None, ToolSurfaceKind.COMMAND_SKILL, ToolSurfaceKind.COMMAND_FILE])
def test_empty_expansion_retains_canonical_selection_for_orphan_pruning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tool: str | None, kind: ToolSurfaceKind | None
) -> None:
    from dataclasses import FrozenInstanceError
    from hashlib import sha256  # noqa: TID251 - exact fixture file-byte integrity, not charter hashing.
    from specify_cli.tool_surface.operations import FileState, OperationRoot, OwnershipProof, PhysicalEffect
    from specify_cli.tool_surface.providers._registry import SurfaceProviderRegistry, SurfaceRegistration
    from specify_cli.tool_surface.service import run_tool_surfaces

    definitions = (_definition(ToolSurfaceKind.COMMAND_SKILL), _definition(ToolSurfaceKind.COMMAND_FILE))
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), projected=b"owner-manifest")
    received: list[tuple[SurfaceSelection, ...]] = []
    for owner in ("codex", "vibe"):
        for definition in definitions:
            (tmp_path / f"{owner}-{definition.kind}.orphan").write_bytes(b"orphan")

    class EmptyOwner(_AssessmentProvider):
        def can_handle(self, definition: SurfaceDefinition) -> bool:
            return definition.provider_key == self.provider_key

        def expand(self, definition: SurfaceDefinition, tool_key: str, project_root: Path) -> list[SurfaceInstance]:
            return []

        def assess(self, inputs: AssessmentInputs, statuses: Sequence[SurfaceStatus], *, selections: tuple[SurfaceSelection, ...] = ()) -> OwnerAssessment:
            assert inputs.projected == b"owner-manifest"
            assert not statuses
            received.append(selections)
            effects = tuple(
                PhysicalEffect(
                    "p",
                    "surface_repair",
                    inputs.root,
                    f"{selection.tool_key}-{selection.definition.kind}.orphan",
                    "delete",
                    FileState("file", sha256=sha256(b"orphan").hexdigest(), mode=0o644),
                    FileState("absent"),
                    "Owned orphan",
                    (OwnershipProof("manifest", f"{selection.tool_key}:{selection.definition.path_pattern}"),),
                    (selection.tool_key,),
                )
                for selection in selections
            )
            return OwnerAssessment("p", inputs.root, effects=effects)

    monkeypatch.setattr(SurfaceProviderRegistry, "_registrations", [SurfaceRegistration(EmptyOwner, definitions, {})])
    outcome = run_tool_surfaces(tmp_path, ("codex", "vibe"), tool_filter=tool, kinds=(kind,) if kind is not None else None, assessment_inputs=inputs)
    assert len(outcome.assessments) == 1
    assessment = outcome.assessments[0]
    assert assessment.complete
    expected = {
        (owner, definition.kind)
        for owner in ("codex", "vibe")
        if tool is None or tool == owner
        for definition in definitions
        if kind is None or kind == definition.kind
    }
    assert {effect.path for effect in assessment.effects} == {f"{owner}-{selected_kind}.orphan" for owner, selected_kind in expected}
    assert len(received) == 1 and isinstance(received[0], tuple)
    assert {(s.tool_key, s.definition.kind) for s in received[0]} == expected
    for selection in received[0]:
        assert selection.definition is next(d for d in definitions if d.kind == selection.definition.kind)
        assert selection.definition.required_policy == RequiredPolicy.REPAIRABLE_REQUIRED
        for attribute, value in (("tool_key", "different"), ("definition", definitions[0])):
            with pytest.raises(FrozenInstanceError):
                setattr(selection, attribute, value)
    assert len(list(tmp_path.glob("*.orphan"))) == 4, "Assessment must not prune on disk"


@pytest.mark.parametrize("failure_at", ["factory", "enter"])
def test_later_prewrite_recheck_failure_retains_known_batch_success(tmp_path: Path, failure_at: str) -> None:
    from contextlib import contextmanager
    from dataclasses import replace
    from specify_cli.tool_surface.operations import OperationRoot

    class DiskOwner(_AssessmentProvider):
        def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
            @contextmanager
            def unavailable() -> Iterator[tuple[Diagnostic, ...]]:
                yield fail()

            def fail() -> tuple[Diagnostic, ...]:
                raise OSError("lock unavailable")

            if assessment.root.root_id == "second":
                if failure_at == "factory":
                    raise OSError("lock unavailable")
                return unavailable()
            return super().recheck(assessment)

        def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
            result = super().apply(assessment, explicit_consent)
            for effect in assessment.effects:
                effect.destination.write_bytes(b"T1")
            return result

    owner = DiskOwner()
    service, template, _ = _assess(owner, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    batches = []
    for name in ("first", "second", "third"):
        path = tmp_path / name
        path.mkdir()
        root = OperationRoot(name, "project", path)
        batches.append(replace(template[0], root=root, effects=(replace(template[0].effects[0], root=root),)))
    try:
        results = service.apply_assessments(tuple(reversed(batches)), ApplyConsent(automatic=True))
    finally:
        assert (tmp_path / "first/a").read_bytes() == b"T1"
        assert not (tmp_path / "second/a").exists()
    assert len(results) == 3
    assert results[0].succeeded == (batches[0].effects[0].id,)
    assert results[1].outcome == "failed"
    assert results[1].skipped == (batches[1].effects[0].id,)
    assert not results[1].succeeded and not results[1].failed
    assert results[1].diagnostics[0].code == "recheck_failed"
    assert results[1].diagnostics[0].message == "lock unavailable"
    assert results[2].succeeded == (batches[2].effects[0].id,)
    assert (tmp_path / "third/a").read_bytes() == b"T1"
    assert owner.write_calls == 2
    assert not owner.locked


@pytest.mark.parametrize("failure_at", ["apply", "exit"])
def test_postwrite_exceptions_are_not_reclassified_as_prewrite_skips(tmp_path: Path, failure_at: str) -> None:
    from contextlib import contextmanager
    from dataclasses import replace
    from specify_cli.tool_surface.operations import OperationRoot

    class UnknownWriteOwner(_AssessmentProvider):
        def recheck(self, assessment: OwnerAssessment) -> AbstractContextManager[tuple[Diagnostic, ...]]:
            @contextmanager
            def locked() -> Iterator[tuple[Diagnostic, ...]]:
                with super(UnknownWriteOwner, self).recheck(assessment) as diagnostics:
                    yield diagnostics
                    if failure_at == "exit":
                        raise OSError("post-write failure")

            return locked()

        def apply(self, assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
            result = super().apply(assessment, explicit_consent)
            assessment.effects[0].destination.write_bytes(b"T1")
            if failure_at == "apply":
                raise OSError("post-write failure")
            return result

    owner = UnknownWriteOwner()
    service, assessments, _ = _assess(owner, (_status(ToolSurfaceKind.COMMAND_SKILL, "a"),))
    root = OperationRoot("project", "project", tmp_path)
    assessment = replace(assessments[0], root=root, effects=(replace(assessments[0].effects[0], root=root),))
    with pytest.raises(OSError, match="post-write failure"):
        service.apply_assessments((assessment,), ApplyConsent(automatic=True))
    assert (tmp_path / "a").read_bytes() == b"T1"
    assert owner.write_calls == 1
    assert not owner.locked
