"""Unit tests for ``tool_surface.providers.command_skills``."""

from __future__ import annotations

import json
from pathlib import Path

from specify_cli.skills import command_installer
from specify_cli.skills import manifest_store
from specify_cli.tool_surface.providers.command_skills import (
    CommandSkillsProvider,
    command_skill_definition,
)
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.operations import OwnerAssessment
from specify_cli.tool_surface.status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_PRESENT,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("pointer", [False, True], ids=["legacy", "pointer"])
@pytest.mark.parametrize("missing", [True, False], ids=["missing-key", "explicit-empty"])
def test_provisioning_projection_real_composition(tmp_path: Path, pointer: bool, missing: bool) -> None:
    import os
    import sys
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.specify_cli.skills.test_command_installer import _wp04_equal_effects
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex, vibe]\n# authored setting\ncustom: keep\n", encoding="utf-8")
    target = config
    if pointer:
        config.write_text(config.read_text() + "charter: authored.yaml\n", encoding="utf-8")
        target = project / "authored.yaml"
        target.write_text("# authored charter\nactivated_paradigms: []\n", encoding="utf-8")
    if not missing:
        target.write_text(target.read_text() + "mission_type_activations: []\n", encoding="utf-8")
    target.chmod(0o640)
    before = snapshot({"project": project})
    activation = prepare_mission_type_activations(project)
    consent = ApplyConsent(automatic=True)
    provider = CommandSkillsProvider()
    selections = tuple(SurfaceSelection(agent, command_skill_definition()) for agent in ("codex", "vibe"))
    assessment = provider.assess(
        AssessmentInputs(OperationRoot("project", "project", project), projected=activation, consent=consent),
        (),
        selections=selections,
    )
    assert assessment.complete, assessment.diagnostics
    assert assessment.effects
    assert_unchanged(before, snapshot({"project": project}))
    with provider.recheck(assessment) as diagnostics:
        assert not diagnostics
    assert activation.apply() is missing
    assert target.read_bytes() == activation.write.desired_bytes
    after_provision = snapshot({"project": project})
    skill_writes: list[str] = []
    observing = True

    def observe(event: str, args: tuple[object, ...]) -> None:
        if observing and event == "open" and str(args[0]).endswith("/SKILL.md.tmp") and isinstance(args[2], int) and args[2] & os.O_CREAT:
            skill_writes.append(str(args[0]))

    sys.addaudithook(observe)
    try:
        (result,) = SurfaceRepairService([provider]).apply_assessments((assessment,), consent)
    finally:
        observing = False
    assert result.outcome == "applied", result
    assert len(skill_writes) == len(set(skill_writes)) == len(command_installer.CANONICAL_COMMANDS)
    _wp04_equal_effects(assessment, after_provision, snapshot({"project": project}))
    assert len(result.succeeded) == len(assessment.effects)
    assert all(entry.agents == ("codex", "vibe") for entry in manifest_store.load(project).entries)

    # Independently provision an equivalent project, then use ordinary installation.
    ordinary = tmp_path / "ordinary"
    ordinary_config = ordinary / ".kittify/config.yaml"
    ordinary_config.parent.mkdir(parents=True)
    ordinary_config.write_bytes(config.read_bytes())
    if pointer:
        (ordinary / "authored.yaml").write_bytes(target.read_bytes())
    command_installer.install(ordinary, "codex")
    for command in command_installer.CANONICAL_COMMANDS:
        rel = f".agents/skills/spec-kitty.{command}/SKILL.md"
        assert (project / rel).read_bytes() == (ordinary / rel).read_bytes()
    repeat = provider.assess(
        AssessmentInputs(OperationRoot("project", "project", project), projected=prepare_mission_type_activations(project), consent=consent),
        (),
        selections=selections,
    )
    assert repeat.complete and not repeat.effects
    before_repeat = snapshot({"project": project})
    repeated = SurfaceRepairService([provider]).apply_assessments((repeat,), consent)[0]
    assert repeated.outcome == "skipped" and not repeated.succeeded
    assert_unchanged(before_repeat, snapshot({"project": project}))


def _projection_project(tmp_path: Path, pointer: bool) -> tuple[Path, Path]:
    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex, vibe]\ncustom: keep\n", encoding="utf-8")
    target = config
    if pointer:
        config.write_text(config.read_text() + "charter: custom-authority.yaml\n", encoding="utf-8")
        target = project / "custom-authority.yaml"
        target.write_text("# custom authority\n", encoding="utf-8")
    target.write_text(target.read_text() + "activated_paradigms: []\nactivated_tactics: []\nactivated_directives: []\n", encoding="utf-8")
    return project, target


def _projection_assess(project: Path, projected: object) -> tuple[CommandSkillsProvider, OwnerAssessment]:
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.registry import ToolSurfaceRegistry

    provider = CommandSkillsProvider()
    registry = ToolSurfaceRegistry()
    for agent in ("codex", "vibe"):
        registry.register_definition(agent, command_skill_definition())
    inputs = AssessmentInputs(OperationRoot("project", "project", project), projected=projected, consent=ApplyConsent(automatic=True))
    (assessment,) = SurfacePlanBuilder(registry, [provider]).assess(("codex", "vibe"), inputs).assessments
    return provider, assessment


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("after", [False, True], ids=["before-provision", "after-provision"])
@pytest.mark.parametrize("damage", ["bytes", "selector", "agents", "pointer", "mode", "inode", "symlink", "mtime"])
def test_provisioning_projection_drift_refuses_without_writes(tmp_path: Path, pointer: bool, after: bool, damage: str) -> None:
    import os
    import sys
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from tests.upgrade.preview_support.write_observer import EVENTS

    project, target = _projection_project(tmp_path, pointer)
    config = project / ".kittify/config.yaml"
    foreign = project / "foreign.yaml"
    foreign.write_bytes(target.read_bytes())
    activation = prepare_mission_type_activations(project)
    provider, assessment = _projection_assess(project, activation)
    assert assessment.complete, assessment.diagnostics
    if after:
        assert activation.apply()
    if damage == "bytes":
        target.write_bytes(target.read_bytes() + b"# unrelated edit\n")
    elif damage == "selector":
        target.write_text(target.read_text().replace("activated_paradigms: []", "activated_paradigms: [structured-prompt-driven-development]"))
    elif damage == "agents":
        config.write_text(config.read_text().replace("[codex, vibe]", "[vibe]"))
    elif damage == "pointer":
        config.write_text(config.read_text().replace("charter: custom-authority.yaml\n", "") + "charter: foreign.yaml\n")
    elif damage == "mode":
        target.chmod(0o400)
    elif damage == "inode":
        replacement = project / "replacement.yaml"
        replacement.write_bytes(target.read_bytes())
        os.replace(replacement, target)
    elif damage == "symlink":
        target.unlink()
        target.symlink_to(foreign)
    else:
        os.utime(target, ns=(1, 1))
    before = snapshot({"project": project})
    events: list[str] = []
    active = True

    def observe(event: str, args: tuple[object, ...]) -> None:
        write_open = event == "open" and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if active and (event in EVENTS or write_open):
            events.append(event)

    sys.addaudithook(observe)
    try:
        (result,) = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)
        assert result.outcome == "precondition_changed" and result.diagnostics
        assert not result.succeeded and not events
        assert_unchanged(before, snapshot({"project": project}))
        control = project / "observer-control"
        control.write_bytes(b"transient")
        control.unlink()
        assert "open" in events and "os.remove" in events
    finally:
        active = False


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("damage", ["bytes", "rehash", "selector", "agents", "values", "reason", "target", "descriptor", "stale"])
def test_provisioning_projection_rejects_forged_preparation(tmp_path: Path, pointer: bool, damage: str) -> None:
    from dataclasses import replace
    from charter.activation.compiler import prepare_mission_type_activations
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, target = _projection_project(tmp_path, pointer)
    prepared = prepare_mission_type_activations(project)
    write = prepared.write
    if damage in {"bytes", "rehash", "selector", "agents"}:
        desired = write.desired_bytes + b"# forged\n"
        if damage == "selector":
            desired = write.desired_bytes.replace(b"activated_tactics: []", b"activated_tactics: [reasons-canvas-fill]")
        elif damage == "agents":
            desired = write.desired_bytes + b"agents: {available: [vibe]}\n"
        write = replace(write, desired_bytes=desired)
        if damage != "bytes":
            write = replace(write, desired_sha256=manifest_store.fingerprint(desired))
        prepared = replace(prepared, write=write)
    elif damage == "values":
        prepared = replace(prepared, mission_type_activations=())
    elif damage == "reason":
        prepared = replace(prepared, reason="key_present")
    elif damage == "target":
        prepared = replace(prepared, write=replace(write, target=target.parent / "foreign.yaml"))
    elif damage == "descriptor":
        prepared = write
    else:
        target.write_bytes(target.read_bytes() + b"# changed after compiler preparation\n")
    before = snapshot({"project": project})
    _, assessment = _projection_assess(project, prepared)
    assert not assessment.complete and assessment.diagnostics and not assessment.effects
    assert_unchanged(before, snapshot({"project": project}))


def test_provisioning_projection_preflight_is_original_state_only(tmp_path: Path) -> None:
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, _ = _projection_project(tmp_path, True)
    prepared = prepare_mission_type_activations(project)
    provider, assessment = _projection_assess(project, prepared)
    assert assessment.complete and not provider.preflight(assessment)
    before = snapshot({"project": project})
    (premature,) = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)
    assert premature.outcome == "precondition_changed" and not premature.succeeded
    assert_unchanged(before, snapshot({"project": project}))
    assert prepared.apply()
    assert provider.preflight(assessment)
    (applied,) = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)
    assert applied.outcome == "applied"


@pytest.mark.parametrize("retain_hash", [False, True])
def test_provisioning_projection_retained_payload_tampering(tmp_path: Path, retain_hash: bool) -> None:
    from dataclasses import replace
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, _ = _projection_project(tmp_path, False)
    provisioning = prepare_mission_type_activations(project)
    provider, assessment = _projection_assess(project, provisioning)
    assert provisioning.apply()
    assert isinstance(assessment.prepared, command_installer.PreparedCommands)
    modified = provisioning.write.desired_bytes + b"# tampered after assessment\n"
    altered = replace(provisioning.write, desired_bytes=modified)
    if not retain_hash:
        altered = replace(altered, desired_sha256=manifest_store.fingerprint(modified))
    assessment = replace(assessment, prepared=replace(assessment.prepared, provisioning=replace(provisioning, write=altered)))
    before = snapshot({"project": project})
    (result,) = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)
    assert result.outcome == "precondition_changed" and not result.succeeded
    assert_unchanged(before, snapshot({"project": project}))


def test_provisioning_projection_cannot_remove_retained_dependency(tmp_path: Path) -> None:
    from dataclasses import replace
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, _ = _projection_project(tmp_path, False)
    provider, assessment = _projection_assess(project, prepare_mission_type_activations(project))
    assert isinstance(assessment.prepared, command_installer.PreparedCommands)
    assessment = replace(assessment, prepared=replace(assessment.prepared, provisioning=None))
    before = snapshot({"project": project})
    (result,) = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)
    assert result.outcome == "precondition_changed" and not result.succeeded
    assert_unchanged(before, snapshot({"project": project}))


def test_provisioning_projection_absent_authority_requires_canonical_apply(tmp_path: Path) -> None:
    from charter.activation.compiler import prepare_mission_type_activations
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    prepared = prepare_mission_type_activations(project)
    before = snapshot({"project": project})
    provider, assessment = _projection_assess(project, prepared)
    assert assessment.complete and assessment.effects
    assert_unchanged(before, snapshot({"project": project}))
    from specify_cli.tool_surface.repair import SurfaceRepairService

    refused = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)[0]
    assert refused.outcome == "precondition_changed" and not refused.succeeded
    assert_unchanged(before, snapshot({"project": project}))
    assert prepared.apply()
    applied = SurfaceRepairService([provider]).apply_assessments((assessment,), assessment.consent)[0]
    assert applied.outcome == "applied", applied.diagnostics
    assert (project / ".kittify/config.yaml").read_bytes() == prepared.write.desired_bytes
    assert (project / ".kittify/command-skills-manifest.json").exists()


@pytest.mark.parametrize("missing", [False, True])
def test_provisioning_projection_hardlinked_authority_admission(tmp_path: Path, missing: bool) -> None:
    import os
    from charter.activation.compiler import prepare_mission_type_activations
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, target = _projection_project(tmp_path, True)
    if not missing:
        target.write_bytes(target.read_bytes() + b"mission_type_activations: []\n")
    os.link(target, project / "other-name.yaml")
    before = snapshot({"project": project})
    _, assessment = _projection_assess(project, prepare_mission_type_activations(project))
    assert assessment.complete is not missing
    if missing:
        assert not assessment.effects and "single-link" in assessment.diagnostics[0].message
    assert_unchanged(before, snapshot({"project": project}))


def test_provisioning_projection_assessment_has_no_write_attempts(tmp_path: Path) -> None:
    import os
    import sys
    from charter.activation.compiler import prepare_mission_type_activations
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from tests.upgrade.preview_support.write_observer import EVENTS

    project, _ = _projection_project(tmp_path, True)
    before = snapshot({"project": project})
    events: list[str] = []
    active = True

    def observe(event: str, args: tuple[object, ...]) -> None:
        write_open = event == "open" and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if active and (event in EVENTS or write_open):
            events.append(event)

    sys.addaudithook(observe)
    try:
        provider, assessment = _projection_assess(project, prepare_mission_type_activations(project))
        assert assessment.complete and not provider.preflight(assessment)
        assert not events
        assert_unchanged(before, snapshot({"project": project}))
        control = project / "observer-control"
        control.write_bytes(b"transient")
        control.unlink()
        assert "open" in events and "os.remove" in events
    finally:
        active = False


@pytest.mark.parametrize("enabled", [("codex",), ("codex", "vibe"), ()])
@pytest.mark.parametrize("empty_catalog", [False, True])
def test_wp04_dispatch_respects_disabled_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: tuple[str, ...], empty_catalog: bool) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.enums import ActivationMode
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.registry import ToolSurfaceRegistry
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged
    from tests.specify_cli.skills.test_command_installer import _wp04_equal_effects

    if empty_catalog:
        for agent in ("codex", "vibe"):
            rel = f".agents/skills/spec-kitty.old-{agent}/SKILL.md"
            path = tmp_path / rel
            path.parent.mkdir(parents=True)
            path.write_bytes(agent.encode())
            manifest = manifest_store.load(tmp_path)
            manifest.upsert(manifest_store.ManifestEntry(rel, manifest_store.fingerprint_file(path), (agent,), "2026-09-06", "test"))
            manifest_store.save(tmp_path, manifest)
        monkeypatch.setattr(command_installer, "CANONICAL_COMMANDS", ())
    provider = CommandSkillsProvider()
    registry = ToolSurfaceRegistry()
    for agent in ("codex", "vibe"):
        definition = command_skill_definition()
        if agent not in enabled:
            definition = replace(definition, activation_mode=ActivationMode.DISABLED)
        registry.register_definition(agent, definition)
    consent = ApplyConsent(automatic=True)
    before = snapshot({"project": tmp_path})
    assessed = SurfacePlanBuilder(registry, [provider]).assess(("codex", "vibe"), AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent))
    (assessment,) = assessed.assessments
    assert assessment.complete, assessment.diagnostics
    assert not provider.preflight(assessment)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    results = SurfaceRepairService([provider]).apply_assessments(assessed.assessments, consent)
    assert all(result.outcome in {"applied", "skipped"} for result in results)
    _wp04_equal_effects(assessment, before, snapshot({"project": tmp_path}))
    entries = manifest_store.load(tmp_path).entries
    if empty_catalog:
        assert {entry.agents for entry in entries} == {(agent,) for agent in ("codex", "vibe") if agent not in enabled}
    elif enabled:
        assert len(entries) == len(command_installer.CANONICAL_COMMANDS)
        assert all(entry.agents == enabled for entry in entries)
        files = [effect for effect in assessment.effects if effect.path.endswith("/SKILL.md")]
        assert len(files) == len(command_installer.CANONICAL_COMMANDS)
        assert all(effect.logical_owners == enabled for effect in files)
        assert all(len(effect.surface_ids) == len(enabled) for effect in files)
    else:
        assert not entries and not assessment.effects
        assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("config_kind", ["loop", "pointer-loop", "missing", "corrupt", "pointer", "regular-link"])
def test_wp04_dispatch_config_observation_boundary(tmp_path: Path, config_kind: str) -> None:
    import os
    import sys
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.registry import ToolSurfaceRegistry
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged
    from tests.upgrade.preview_support.write_observer import EVENTS

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    if config_kind == "loop":
        config.symlink_to("config.yaml")
    elif config_kind == "corrupt":
        config.write_text("agents: [", encoding="utf-8")
    elif config_kind in {"pointer", "pointer-loop"}:
        config.write_text("agents:\n  available: [codex]\ncharter: .kittify/charter.yaml\n", encoding="utf-8")
        target = config.parent / "charter.yaml"
        if config_kind == "pointer-loop":
            target.symlink_to("charter.yaml")
        else:
            target.write_text("activated_paradigms: []\n", encoding="utf-8")
    elif config_kind == "regular-link":
        target = tmp_path / "authored.yaml"
        target.write_text("agents:\n  available: [codex]\n", encoding="utf-8")
        config.symlink_to(target)
    provider = CommandSkillsProvider()
    registry = ToolSurfaceRegistry()
    registry.register_definition("codex", command_skill_definition())
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent)
    before = snapshot({"project": tmp_path})
    events: list[str] = []
    active = True

    def observe(event: str, args: tuple[object, ...]) -> None:
        write_open = event == "open" and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        if active and (event in EVENTS or write_open):
            events.append(event)

    sys.addaudithook(observe)
    try:
        assessed = SurfacePlanBuilder(registry, [provider]).assess(("codex",), inputs)
        (assessment,) = assessed.assessments
        broken = config_kind in {"loop", "pointer-loop", "corrupt"}
        assert assessment.complete is not broken, assessment.diagnostics
        if broken:
            assert assessment.diagnostics and not assessment.effects
            (result,) = SurfaceRepairService([provider]).apply_assessments(assessed.assessments, consent)
            assert result.outcome != "applied" and result.diagnostics
        else:
            assert assessment.effects and not assessment.diagnostics
        assert not events
        assert_unchanged(before, snapshot({"project": tmp_path}))
        control = tmp_path / "transient-control"
        control.write_bytes(b"control")
        control.unlink()
        assert "open" in events and "os.remove" in events
    finally:
        active = False


def test_wp04_dispatch_does_not_hide_programmer_runtime_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_renderer
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    def broken_renderer(root: Path) -> tuple[Path, ...]:
        raise RuntimeError("programmer defect, not a filesystem loop")

    monkeypatch.setattr(command_renderer, "rendering_inputs", broken_renderer)
    with pytest.raises(RuntimeError, match="programmer defect"):
        CommandSkillsProvider().assess(
            AssessmentInputs(OperationRoot("project", "project", tmp_path)),
            (),
            selections=(SurfaceSelection("codex", command_skill_definition()),),
        )


def test_wp04_provider_retains_empty_expansion_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    codex = ".agents/skills/spec-kitty.old-codex/SKILL.md"
    vibe = ".agents/skills/spec-kitty.old-vibe/SKILL.md"
    _write_manifest_entry(tmp_path, codex, "owned codex")
    manifest = manifest_store.load(tmp_path)
    path = tmp_path / vibe
    path.parent.mkdir()
    path.write_bytes(b"owned vibe")
    manifest.upsert(manifest_store.ManifestEntry(vibe, manifest_store.fingerprint_file(path), ("vibe",), "2026-09-06T00:00:00+00:00", "test"))
    manifest_store.save(tmp_path, manifest)
    monkeypatch.setattr(command_installer, "CANONICAL_COMMANDS", ())
    provider = CommandSkillsProvider()
    definition = command_skill_definition()
    selection = SurfaceSelection("codex", definition)
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=ApplyConsent(automatic=True))
    before = snapshot({"project": tmp_path})
    assessment = provider.assess(inputs, (), selections=(selection,))
    assert assessment.complete, assessment.diagnostics
    assert any(e.path == codex and e.action == "delete" for e in assessment.effects)
    assert not any(e.path == vibe for e in assessment.effects)
    retained = next(o.value for o in assessment.inputs_fingerprint if o.name == "selections")
    assert retained == (selection,)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    with provider.recheck(assessment) as diagnostics:
        assert not diagnostics
        assert provider.apply(assessment, inputs.consent).outcome == "applied"
    assert not (tmp_path / codex).exists()
    assert path.read_bytes() == b"owned vibe"


def test_wp04_provider_preserves_status_identity_and_shared_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.model import SurfaceInstance
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.protocol import AssessingSurfaceProvider
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.registry import ToolSurfaceRegistry
    from specify_cli.tool_surface.status import SurfaceStatus
    from tests.upgrade.preview_support.snapshot import snapshot
    from tests.specify_cli.skills.test_command_installer import _wp04_equal_effects

    provider = CommandSkillsProvider()
    assert isinstance(provider, AssessingSurfaceProvider)
    definition = command_skill_definition()
    registry = ToolSurfaceRegistry()
    for agent in ("codex", "vibe"):
        registry.register_definition(agent, definition)
    statuses: list[SurfaceStatus] = []
    original_probe = provider.probe

    def record_probe(instance: SurfaceInstance) -> SurfaceStatus:
        status = original_probe(instance)
        statuses.append(status)
        return status

    monkeypatch.setattr(provider, "probe", record_probe)
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=ApplyConsent(automatic=True))
    before = snapshot({"project": tmp_path})
    assessed = SurfacePlanBuilder(registry, [provider]).assess(("codex", "vibe"), inputs)
    assessment = assessed.assessments[0]
    assert assessment.complete, assessment.diagnostics
    assert all(actual is original for actual, original in zip(assessed.report.surfaces, statuses, strict=True))
    retained = next(o.value for o in assessment.inputs_fingerprint if o.name == "instances")
    assert isinstance(retained, tuple)
    assert all(instance is status.instance for instance, status in zip(retained, statuses, strict=True))
    command_effects = [e for e in assessment.effects if e.after.kind == "file" and e.path.endswith("SKILL.md")]
    assert len(command_effects) == len(command_installer.CANONICAL_COMMANDS)
    assert all(e.logical_owners == ("codex", "vibe") and len(e.surface_ids) == 2 for e in command_effects)
    assert provider.apply(assessment, inputs.consent).outcome == "applied"
    _wp04_equal_effects(assessment, before, snapshot({"project": tmp_path}))


def test_wp04_ordinary_repair_keeps_drift_and_repairs_missing(tmp_path: Path) -> None:
    command_installer.install(tmp_path, "codex")
    missing = tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md"
    drift = tmp_path / ".agents/skills/spec-kitty.status/SKILL.md"
    missing.unlink()
    drift.write_bytes(b"custom edited command")
    provider = CommandSkillsProvider()
    statuses = tuple(provider.probe(i) for i in provider.expand(command_skill_definition(), "codex", tmp_path))
    result = provider.repair(tmp_path, statuses)
    assert result.repaired and result.failed
    assert missing.is_file()
    assert drift.read_bytes() == b"custom edited command"


def _empty_manifest(project: Path) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "command-skills-manifest.json").write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")


def _write_manifest_entry(project: Path, rel: str, body: str) -> None:
    target = project / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    manifest_store.save(
        project,
        manifest_store.SkillsManifest(
            entries=[
                manifest_store.ManifestEntry(
                    path=rel,
                    content_hash=manifest_store.fingerprint_file(target),
                    agents=("codex",),
                    installed_at="2026-06-14T00:00:00+00:00",
                    spec_kitty_version="test",
                )
            ]
        ),
    )


def test_provider_satisfies_reporting_protocol() -> None:
    provider = CommandSkillsProvider()
    assert isinstance(provider, ReportingSurfaceProvider)
    assert provider.provider_key == "command_skills"


def test_can_handle_only_command_skill() -> None:
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.providers.slash_commands import (
        slash_command_definition,
    )

    provider = CommandSkillsProvider()
    assert provider.can_handle(command_skill_definition()) is True
    other = slash_command_definition()
    assert other.kind == ToolSurfaceKind.COMMAND_FILE
    assert provider.can_handle(other) is False


def test_expand_unsupported_agent_returns_empty(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instances = provider.expand(command_skill_definition(), "claude", tmp_path)
    assert instances == []


def test_expand_supported_agent_one_per_command(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instances = provider.expand(command_skill_definition(), "codex", tmp_path)
    assert len(instances) == len(command_installer.CANONICAL_COMMANDS)
    assert all(i.owner == "codex" for i in instances)
    assert all(i.path.name == "SKILL.md" for i in instances)


def test_probe_missing(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "generated-surface-missing"
    assert status.findings[0].repair_command is not None


def test_probe_present(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    _write_manifest_entry(tmp_path, instance.path.relative_to(tmp_path).as_posix(), "content")
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_PRESENT
    assert status.findings == ()


def test_probe_drift(tmp_path: Path) -> None:
    from dataclasses import replace

    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    _write_manifest_entry(tmp_path, instance.path.relative_to(tmp_path).as_posix(), "real content")
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    # Force a mismatched expected hash to simulate manifest drift.
    drifted = replace(instance, exists=True, file_hash="deadbeef" * 8)
    status = provider.probe(drifted)
    assert status.state == STATE_DRIFTED
    assert status.findings[0].code == "managed-file-drift"


def test_repair_no_actionable_returns_clean(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    # Materialize the file so probe reports PRESENT (nothing to repair).
    _write_manifest_entry(tmp_path, instance.path.relative_to(tmp_path).as_posix(), "content")
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    present = provider.probe(instance)
    assert present.state == STATE_PRESENT
    result = provider.repair(tmp_path, [present])
    assert result.repaired == ()
    assert result.failed == ()


def test_repair_dry_run_reports_without_install(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    provider = CommandSkillsProvider()
    instance = provider.expand(command_skill_definition(), "codex", tmp_path)[0]
    status = provider.probe(instance)  # missing
    result = provider.repair(tmp_path, [status], dry_run=True)
    assert result.dry_run is True
    # No file was created during a dry run.
    assert not instance.path.exists()


def test_expand_reports_unmanaged_spec_kitty_orphan(tmp_path: Path) -> None:
    _empty_manifest(tmp_path)
    orphan = tmp_path / ".agents" / "skills" / "spec-kitty.fake" / "SKILL.md"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("orphan", encoding="utf-8")
    provider = CommandSkillsProvider()

    statuses = [provider.probe(i) for i in provider.expand(command_skill_definition(), "codex", tmp_path)]

    assert any(f.code == "unmanaged-spec-kitty-surface" for status in statuses for f in status.findings)


def test_expand_reports_stale_manifest_command(tmp_path: Path) -> None:
    stale_rel = ".agents/skills/spec-kitty.checklist/SKILL.md"
    stale = tmp_path / stale_rel
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale", encoding="utf-8")
    manifest = manifest_store.SkillsManifest(
        entries=[
            manifest_store.ManifestEntry(
                path=stale_rel,
                content_hash=manifest_store.fingerprint_file(stale),
                agents=("codex",),
                installed_at="2026-06-14T00:00:00+00:00",
                spec_kitty_version="test",
            ),
        ]
    )
    manifest_store.save(tmp_path, manifest)
    provider = CommandSkillsProvider()

    statuses = [provider.probe(i) for i in provider.expand(command_skill_definition(), "codex", tmp_path)]

    assert any(f.code == "stale-generated-surface" for status in statuses for f in status.findings)
