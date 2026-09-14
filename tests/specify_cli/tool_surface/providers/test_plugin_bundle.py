"""Live-path safety contract for plugin-bundle staging."""

from __future__ import annotations

from pathlib import Path
import json
from typing import TYPE_CHECKING
from collections.abc import Callable

if TYPE_CHECKING:
    from charter.activation.compiler import _PreparedMissionTypeActivations
    from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider, SkillCommandComposition
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import Snapshot

import pytest
import shutil
from dataclasses import replace
from contextlib import contextmanager
from collections.abc import Iterator

from specify_cli.tool_surface.operations import OwnerAssessment

from specify_cli.tool_surface.providers.plugin_bundle import (
    PLUGIN_BUNDLE_TOOL_KEY,
    PluginBundleProvider,
    plugin_manifest_definition,
)
from specify_cli.tool_surface.status import STATE_MISSING, STATE_PRESENT

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@contextmanager
def _write_attempts() -> Iterator[list[str]]:
    import os
    import sys
    from tests.upgrade.preview_support.write_observer import EVENTS

    attempts: list[str] = []
    active = True

    def observe(event: str, values: tuple[object, ...]) -> None:
        if not active:
            return
        writing = event == "open" and (
            isinstance(values[1], str)
            and any(flag in values[1] for flag in "wax+")
            or isinstance(values[2], int)
            and bool(values[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        )
        if event in EVENTS or writing:
            attempts.append(f"{event}: {values}")

    sys.addaudithook(observe)
    try:
        yield attempts
    finally:
        active = False


@pytest.fixture(scope="module")
def canonical_bundle_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from typer.testing import CliRunner
    from specify_cli import app

    project = tmp_path_factory.mktemp("wp08-canonical") / "project"
    result = CliRunner().invoke(app, ["init", str(project), "--ai", "claude,codex,vibe", "--non-interactive"])
    assert result.exit_code == 0, f"{result.output}\n{result.exception}"
    assert (project / ".kittify/config.yaml").is_file()
    assert (project / ".agents/skills/spec-kitty.plan/SKILL.md").is_file()
    return project


def _selected(provider: PluginBundleProvider, project: Path, targets: tuple[str, ...] = ()) -> OwnerAssessment:
    from specify_cli.tool_surface.bundles.model import BundleSources
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    return provider.assess(
        AssessmentInputs(
            OperationRoot("project", "project", project),
            projected=BundleSources(
                selected_targets=targets or tuple(i.owner for i in provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, project))
            ),
            consent=ApplyConsent(automatic=True),
        ),
        (),
        selections=(),
    )


@pytest.mark.parametrize("configured", [("gemini", "codex"), (), ("codex", "gemini", "codex")])
def test_configured_consumer_calls_approved_helper_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: tuple[str, ...],
) -> None:
    from collections.abc import Sequence
    from specify_cli.core.agent_config import AgentConfig, save_agent_config
    from specify_cli.tool_surface import service
    from specify_cli.tool_surface.model import SurfacePlan
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    save_agent_config(tmp_path, AgentConfig(available=list(configured), auto_commit=False))
    real_helper = service.build_plans_for_bundles
    calls: list[tuple[str, ...] | None] = []

    def observing_helper(project_root: Path, *, tool_keys: Sequence[str] | None = None) -> list[SurfacePlan]:
        calls.append(None if tool_keys is None else tuple(tool_keys))
        return real_helper(project_root, tool_keys=tool_keys)

    monkeypatch.setattr(service, "build_plans_for_bundles", observing_helper)
    before = snapshot({"project": tmp_path, "home": Path.home()})
    with _write_attempts() as attempted:
        plans = PluginBundleProvider()._plans_for_projection(tmp_path)
    assert calls == [configured]
    assert tuple(plan.tool_key for plan in plans) == configured
    if configured:
        assert all(plan.instances and plan.definitions for plan in plans)
        assert {instance.owner for plan in plans for instance in plan.instances} == set(configured)
    else:
        assert plans == []
    assert not attempted, attempted
    assert_unchanged(before, snapshot({"project": tmp_path, "home": Path.home()}))


def test_canonical_selected_bundle_exact_effects_and_read_only_assessment(
    tmp_path: Path,
    canonical_bundle_tree: Path,
) -> None:
    from specify_cli.tool_surface.operations import OwnerAssessment
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    project = tmp_path / "project"
    shutil.copytree(canonical_bundle_tree, project)
    from specify_cli.core.agent_config import AgentConfig, save_agent_config

    save_agent_config(project, AgentConfig(available=["claude"], auto_commit=False))
    from specify_cli.skills.paths import get_primary_project_skill_root

    skill_root = get_primary_project_skill_root("claude")
    assert skill_root is not None
    skills = sorted((project / skill_root).glob("*/SKILL.md"))
    profiles = sorted((project / ".claude/agents").glob("*.md"))
    assert len(skills) >= 2 and profiles
    missing_sources = (skills[0], profiles[0])
    for source in missing_sources:
        source.unlink()
    provider = PluginBundleProvider()
    before = snapshot({"project": project, "home": Path.home()})
    with _write_attempts() as attempted:
        assessment = _selected(provider, project)
    assert not attempted, attempted
    assert isinstance(assessment, OwnerAssessment)
    assert assessment.complete, assessment.diagnostics
    assert assessment.effects
    assert_unchanged(before, snapshot({"project": project, "home": Path.home()}))
    result = provider.apply(assessment, assessment.consent)
    assert result.outcome == "applied", result
    assert set(result.succeeded) == {effect.id for effect in assessment.effects}
    actual = net_delta(before, snapshot({"project": project, "home": Path.home()}))
    expected = {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects}
    assert expected == {(e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in actual}
    assert any(e.path.endswith("plugin.json") for e in assessment.effects)
    assert any("/skills/" in e.path for e in assessment.effects)
    assert any("/agents/" in e.path for e in assessment.effects)
    assert all(not source.exists() for source in missing_sources)
    assert not any("marketplace.json" in e.path or "/bin/" in e.path for e in assessment.effects)
    repeated = _selected(provider, project)
    assert isinstance(repeated, OwnerAssessment)
    assert repeated.complete and not repeated.effects, repeated.diagnostics
    settled = snapshot({"project": project, "home": Path.home()})
    with _write_attempts() as attempted:
        assert provider.apply(repeated, repeated.consent).outcome == "applied"
    assert not attempted, attempted
    assert_unchanged(settled, snapshot({"project": project, "home": Path.home()}))


def test_canonical_multi_harness_profile_conflict_is_read_only(tmp_path: Path, canonical_bundle_tree: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    shutil.copytree(canonical_bundle_tree, project)
    before = snapshot({"project": project, "home": Path.home()})
    provider = PluginBundleProvider()
    assessment = _selected(provider, project)
    assert not assessment.complete
    assert any("Conflicting prepared bundle member: agents/" in d.message for d in assessment.diagnostics)
    assert provider.apply(assessment, assessment.consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"project": project, "home": Path.home()}))


def test_equivalent_independent_canonical_copies_have_exact_effects(tmp_path: Path, canonical_bundle_tree: Path) -> None:
    from specify_cli.core.agent_config import AgentConfig, save_agent_config
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    deltas = []
    for label in ("assessed", "independent"):
        project = tmp_path / label
        shutil.copytree(canonical_bundle_tree, project)
        save_agent_config(project, AgentConfig(available=["claude"], auto_commit=False))
        provider = PluginBundleProvider()
        before = snapshot({"project": project, "home": Path.home()})
        assessment = _selected(provider, project)
        assert assessment.complete and assessment.effects, assessment.diagnostics
        result = provider.apply(assessment, assessment.consent)
        assert result.outcome == "applied", result
        delta = {
            (e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in net_delta(before, snapshot({"project": project, "home": Path.home()}))
        }
        assert delta == {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects}
        deltas.append(delta)
    assert deltas[0] == deltas[1]


@pytest.mark.parametrize("member", [".mcp.json", ".agents/skills/spec-kitty.plan/SKILL.md"])
def test_malformed_required_source_is_incomplete_and_write_free(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provider = _unit_provider(tmp_path, monkeypatch)
    (tmp_path / member).write_bytes(b"{bad json" if member.endswith(".json") else b"---\ninvalid: [\n---\n")
    before = snapshot({"project": tmp_path})
    assessment = _selected(provider, tmp_path)
    assert not assessment.complete and not assessment.effects
    assert assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path}))


def _unit_provider(project: Path, monkeypatch: pytest.MonkeyPatch) -> PluginBundleProvider:
    from tests.specify_cli.tool_surface.bundles._support import full_plans

    plans = full_plans(project)
    provider = PluginBundleProvider()
    monkeypatch.setattr(provider, "_plans_for_projection", lambda root: plans)
    return provider


def test_disabled_assessment_never_reads_inventory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provider = PluginBundleProvider()

    def forbidden(root: Path) -> list[object]:
        raise AssertionError("Disabled bundle inventoried its sources")

    monkeypatch.setattr(provider, "_plans_for_projection", forbidden)
    before = snapshot({"project": tmp_path})
    result = provider.assess(
        AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=ApplyConsent(automatic=True)),
        (),
        selections=(SurfaceSelection(PLUGIN_BUNDLE_TOOL_KEY, plugin_manifest_definition()),),
    )
    assert result.complete and not result.effects
    assert [d.state for d in result.dispositions] == ["not_applicable"]
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_retired_command_is_not_copied_from_pre_repair_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_installer
    from specify_cli.tool_surface.bundles.claude import ClaudeCodeBundleProjector
    from specify_cli.tool_surface.bundles.projection import files_for_entries, supplied_entries
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.service import build_providers, build_registry
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    root = OperationRoot("project", "project", tmp_path)
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(root, consent=consent)
    initial = command_installer.prepare_commands(inputs, ("codex",))
    assert initial.complete
    assert command_installer.apply_commands(initial, consent).outcome == "applied"
    plans = SurfacePlanBuilder(build_registry(("codex",)), build_providers()).build(("codex",), tmp_path, kinds=(ToolSurfaceKind.COMMAND_SKILL,))
    original = ClaudeCodeBundleProjector().entries(plans, tmp_path)
    stale = tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md"
    assert any(stale in entry.sources for entry in original)
    monkeypatch.setattr(command_installer, "CANONICAL_COMMANDS", tuple(name for name in command_installer.CANONICAL_COMMANDS if name != "plan"))
    retirement = command_installer.prepare_commands(inputs, ("codex",), prune=True)
    assert retirement.complete, retirement.diagnostics
    assert any(effect.destination == stale and effect.after.kind == "absent" for effect in retirement.effects)
    before = snapshot({"project": tmp_path})
    entries = supplied_entries(original, (retirement,))
    files = files_for_entries(entries, tmp_path / "dist", root, [])
    assert files
    assert all("skills/spec-kitty.plan/" not in member.path for member in files)
    assert stale.is_file()
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_shared_codex_vibe_inventory_has_one_effect_with_both_owners(tmp_path: Path) -> None:
    from specify_cli.skills.command_installer import apply_commands, prepare_commands
    from specify_cli.tool_surface.bundles.claude import ClaudeCodeBundleProjector
    from specify_cli.tool_surface.bundles.projection import files_for_entries, prepare_staging
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.service import build_providers, build_registry

    root = OperationRoot("project", "project", tmp_path)
    consent = ApplyConsent(automatic=True)
    source = prepare_commands(AssessmentInputs(root, consent=consent), ("codex", "vibe"))
    assert source.complete
    assert apply_commands(source, consent).outcome == "applied"
    plans = SurfacePlanBuilder(build_registry(("codex", "vibe")), build_providers()).build(("codex", "vibe"), tmp_path, kinds=(ToolSurfaceKind.COMMAND_SKILL,))
    entries = ClaudeCodeBundleProjector().entries(plans, tmp_path)
    observations = []
    files = files_for_entries(entries, tmp_path / "dist", root, observations)
    assessment = prepare_staging(AssessmentInputs(root, consent=consent), files, (), tuple(observations))
    assert assessment.complete and assessment.effects
    member = [e for e in assessment.effects if e.path == "dist/skills/spec-kitty.plan/SKILL.md"]
    assert len(member) == 1 and set(member[0].logical_owners) == {"codex", "vibe"}


@pytest.mark.parametrize("known", [False, True])
def test_custom_member_and_unknown_link_are_not_adopted_by_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    known: bool,
) -> None:
    from specify_cli.tool_surface.bundles.model import BundleSources
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    provider = _unit_provider(tmp_path, monkeypatch)
    if known:
        first = _selected(provider, tmp_path)
        assert provider.apply(first, first.consent).outcome == "applied"
    path = "dist/spec-kitty-plugins/claude_code_plugin/skills/spec-kitty.plan/SKILL.md"
    destination = tmp_path / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    sentinel = tmp_path / "outside-sentinel"
    sentinel.write_bytes(b"unknown link target")
    destination.symlink_to(sentinel)
    consent = ApplyConsent(automatic=True, overwrite_paths=(path,))
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), projected=BundleSources(selected_targets=("claude_code_plugin",)), consent=consent)
    assessment = provider.assess(inputs, (), selections=())
    assert assessment.complete
    assert any(d.path == path and d.state == "preserve" for d in assessment.dispositions)
    assert not any(e.path == path for e in assessment.effects)
    provider.apply(assessment, consent)
    assert destination.is_symlink() and sentinel.read_bytes() == b"unknown link target"


def test_managed_drift_requires_exact_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.bundles.model import BundleSources
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    provider = _unit_provider(tmp_path, monkeypatch)
    first = _selected(provider, tmp_path)
    assert provider.apply(first, first.consent).outcome == "applied"
    path = "dist/spec-kitty-plugins/claude_code_plugin/skills/spec-kitty.plan/SKILL.md"
    (tmp_path / path).write_bytes(b"managed drift")
    pending = _selected(provider, tmp_path)
    assert any(d.path == path and d.state == "consent_required" for d in pending.dispositions)
    assert not any(e.path == path for e in pending.effects)
    consent = ApplyConsent(automatic=True, overwrite_paths=(path,))
    assessment = provider.assess(
        AssessmentInputs(OperationRoot("project", "project", tmp_path), projected=BundleSources(selected_targets=("claude_code_plugin",)), consent=consent),
        (),
        selections=(),
    )
    assert assessment.complete
    assert any(e.path == path and e.action == "update" for e in assessment.effects)
    assert provider.apply(assessment, consent).outcome == "applied"
    assert (tmp_path / path).read_bytes() == b"# plan skill\n"


@pytest.mark.parametrize("change", ["source", "manifest", "destination", "parent_link", "parent_mode", "config"])
def test_whole_selected_batch_refuses_each_changed_precondition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    provider = _unit_provider(project, monkeypatch)
    first = _selected(provider, project)
    assert provider.apply(first, first.consent).outcome == "applied"
    target = project / "dist/spec-kitty-plugins/claude_code_plugin"
    victim = target / "skills/spec-kitty.plan/SKILL.md"
    victim.unlink()
    assessment = _selected(provider, project)
    assert assessment.complete and assessment.effects
    if change == "source":
        (project / ".agents/skills/spec-kitty.plan/SKILL.md").write_bytes(b"changed source")
    elif change == "manifest":
        (target / ".claude-plugin/plugin.json").write_bytes(b"{}")
    elif change == "destination":
        victim.write_bytes(b"custom destination")
    elif change == "parent_link":
        victim.parent.rmdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        victim.parent.symlink_to(outside, target_is_directory=True)
    elif change == "parent_mode":
        victim.parent.chmod(0o700)
    else:
        (project / ".kittify/config.yaml").write_bytes(b"agents: {}\n")
    before = snapshot({"sandbox": tmp_path, "home": Path.home()})
    result = provider.apply(assessment, assessment.consent)
    assert result.outcome == "precondition_changed", result
    assert not result.succeeded
    assert_unchanged(before, snapshot({"sandbox": tmp_path, "home": Path.home()}))


def test_prepared_missing_command_is_used_without_second_render(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.skills import command_installer
    from specify_cli.tool_surface.bundles.model import BundleSources
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    from tests.specify_cli.tool_surface.bundles._support import skills_only_plans

    plans = skills_only_plans(tmp_path)
    provider = PluginBundleProvider()
    monkeypatch.setattr(provider, "_plans_for_projection", lambda root: plans)
    source = tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md"
    source.unlink()
    root = OperationRoot("project", "project", tmp_path)
    supplier = command_installer.prepare_commands(AssessmentInputs(root), ("codex",))
    assert supplier.complete, supplier.diagnostics
    before = snapshot({"project": tmp_path, "home": Path.home()})
    inputs = AssessmentInputs(root, projected=BundleSources((supplier,), ("claude_code_plugin",)), consent=ApplyConsent(automatic=True))
    assessment = provider.assess(inputs, (), selections=())
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path, "home": Path.home()}))

    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Apply rendered commands again")

    monkeypatch.setattr(command_installer, "_render_command_skill", forbidden)
    result = provider.apply(assessment, inputs.consent)
    assert result.outcome == "applied", result
    assert not source.exists(), "Bundle acquired upstream write ownership"
    staged = tmp_path / "dist/spec-kitty-plugins/claude_code_plugin/skills/spec-kitty.plan/SKILL.md"
    assert staged.read_bytes().startswith(b"---")


def test_partial_io_reports_only_real_completed_effect_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.bundles import projection
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    provider = _unit_provider(tmp_path, monkeypatch)
    assessment = _selected(provider, tmp_path)
    before = snapshot({"project": tmp_path})
    real_replace = projection.os.replace
    count = 0

    def fail_second(source: Path, destination: Path) -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("WP08 bounded second atomic replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(projection.os, "replace", fail_second)
    result = provider.apply(assessment, assessment.consent)
    assert result.outcome == "partial" and len(result.failed) == 1
    actual = net_delta(before, snapshot({"project": tmp_path}))
    expected = {e.path for e in assessment.effects if e.id in result.succeeded}
    assert expected == {e.path for e in actual}
    assert not list((tmp_path / "dist").rglob("plugin.json"))
    assert not list((tmp_path / "dist").rglob("*.tmp"))
    assert set(result.succeeded + result.failed + result.skipped) == {e.id for e in assessment.effects}


def test_legacy_repair_keeps_physical_ids_separate_from_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.bundles import projection
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    provider = _unit_provider(tmp_path, monkeypatch)
    instance = provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, tmp_path)[0]
    status = provider.probe(instance)
    assessment = _selected(provider, tmp_path, (instance.owner,))
    before = snapshot({"project": tmp_path})
    real_replace = projection.os.replace
    count = 0

    def fail_second(source: Path, destination: Path) -> None:
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("WP08 legacy caller partial failure")
        real_replace(source, destination)

    monkeypatch.setattr(projection.os, "replace", fail_second)
    result = provider.repair(tmp_path, (status,))
    assert len(result.failed) == 1 and result.skipped and result.findings_after
    assert set(result.repaired + result.failed + result.skipped) == {effect.id for effect in assessment.effects}
    assert {effect.path for effect in assessment.effects if effect.id in result.repaired} == {
        effect.path for effect in net_delta(before, snapshot({"project": tmp_path}))
    }
    assert any("WP08 legacy caller partial failure" in finding.message for finding in result.findings_after)


@pytest.mark.parametrize("mutation", ["none", "manifest", "member", "custom", "same_bytes"])
def test_independent_oracle_kills_omission_and_churn_mutants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    provider = _unit_provider(tmp_path, monkeypatch)
    custom = tmp_path / "dist/custom.txt"
    custom.parent.mkdir()
    custom.write_bytes(b"ignored custom sentinel")
    assessment = _selected(provider, tmp_path)
    candidate = assessment
    if mutation in {"manifest", "member"}:
        omitted = next(e for e in assessment.effects if e.path.endswith("plugin.json" if mutation == "manifest" else "SKILL.md"))
        candidate = replace(assessment, effects=tuple(e for e in assessment.effects if e.id != omitted.id))
    before = snapshot({"project": tmp_path})
    assert provider.apply(candidate, candidate.consent).outcome == "applied"
    if mutation == "custom":
        custom.write_bytes(b"destructive mutation")
    actual = net_delta(before, snapshot({"project": tmp_path}))

    def compare() -> None:
        assert {(e.path, e.action, e.after.sha256, e.after.mode) for e in assessment.effects} == {(e.path, e.action, e.after.sha256, e.after.mode) for e in actual}

    if mutation in {"manifest", "member", "custom"}:
        with pytest.raises(AssertionError):
            compare()
    else:
        compare()
    settled = snapshot({"project": tmp_path})
    if mutation == "same_bytes":
        custom.write_bytes(custom.read_bytes())
        with pytest.raises(AssertionError):
            assert_unchanged(settled, snapshot({"project": tmp_path}))


def test_probe_detects_one_missing_member_among_surviving_kinds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.specify_cli.tool_surface.bundles._support import full_plans

    plans = full_plans(tmp_path)
    provider = PluginBundleProvider()
    monkeypatch.setattr(provider, "_plans_for_projection", lambda root: plans)
    instances = provider.expand(plugin_manifest_definition(), PLUGIN_BUNDLE_TOOL_KEY, tmp_path)
    result = provider.repair(tmp_path, [provider.probe(i) for i in instances])
    assert not result.failed
    victim = instances[0].path.parent.parent / "skills/spec-kitty.plan/SKILL.md"
    assert victim.is_file()
    victim.unlink()
    assert (victim.parent.parent / "spec-kitty.charter/SKILL.md").is_file()
    status = provider.probe(instances[0])
    assert status.state == STATE_MISSING, "Surviving kinds concealed an omitted member"
    assert not provider.repair(tmp_path, [status]).failed
    assert victim.read_bytes() == plans[0].instances[0].path.read_bytes()


def test_plugin_bundle_repair_is_staging_only_and_dry_run_is_inert(
    tmp_path: Path,
) -> None:
    """The provider's consumed repair path may write only under ``dist/``."""
    provider = PluginBundleProvider()
    definition = plugin_manifest_definition()
    instances = provider.expand(definition, PLUGIN_BUNDLE_TOOL_KEY, tmp_path)
    assert instances

    statuses = [provider.probe(instance) for instance in instances]
    assert {status.state for status in statuses} == {STATE_MISSING}

    dry_run = provider.repair(tmp_path, statuses, dry_run=True)
    assert dry_run.repaired
    assert not (tmp_path / "dist").exists()

    result = provider.repair(tmp_path, statuses, dry_run=False)
    assert result.failed == ()
    written = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert written
    assert all(path.is_relative_to(tmp_path / "dist") for path in written)

    repaired = provider.expand(definition, PLUGIN_BUNDLE_TOOL_KEY, tmp_path)
    assert {provider.probe(instance).state for instance in repaired} == {STATE_PRESENT}


@pytest.fixture
def selected_codex_seed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    from typer.testing import CliRunner
    from specify_cli import app

    base = tmp_path_factory.mktemp("selected-codex-seed")
    home, project = base / "home", base / "project"
    home.mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(base)
        patch.setenv("HOME", str(home))
        patch.setenv("USERPROFILE", str(home))
        patch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
        result = CliRunner().invoke(app, ["init", str(project), "--ai", "codex", "--non-interactive"])
        assert result.exit_code == 0, (result.output, result.exception)
        assert (project / ".agents/skills/spec-kitty.plan/SKILL.md").is_file()
    return project, home


def _selected_skill_preparation(
    project: Path,
) -> tuple[_PreparedMissionTypeActivations, ApplyConsent, ManagedSkillsProvider, SkillCommandComposition, PluginBundleProvider, OwnerAssessment]:
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.skills.registry import SkillRegistry
    from specify_cli.tool_surface.bundles.model import BundleSources
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.providers.managed_skills import ManagedSkillsProvider
    from specify_cli.tool_surface.service import build_providers, build_registry

    root, consent = OperationRoot("project", "project", project), ApplyConsent(automatic=True)
    descriptor = prepare_mission_type_activations(project)
    providers = build_providers()
    builder = SurfacePlanBuilder(build_registry(("codex", PLUGIN_BUNDLE_TOOL_KEY)), providers)
    installation = assess_skill_installation(
        AssessmentInputs(root, projected=descriptor, consent=consent),
        SkillRegistry.from_package(),
        ("codex",),
        runtime=True,
        commands=True,
        command_agent_keys=[key for key in ("codex",) if key in AGENT_COMMAND_CONFIG],
    )
    commands = builder.assess(
        ("codex",),
        AssessmentInputs(root, projected=descriptor, consent=consent),
        kinds=(ToolSurfaceKind.COMMAND_SKILL,),
    ).assessments[0]
    doctrine = builder.assess(
        ("codex",),
        AssessmentInputs(root, projected=installation, consent=consent),
        kinds=(ToolSurfaceKind.DOCTRINE_SKILL,),
    ).assessments[0]
    assert doctrine == installation.project_skills
    managed = next(p for p in providers if isinstance(p, ManagedSkillsProvider))
    bundle_provider = next(p for p in providers if isinstance(p, PluginBundleProvider))
    assert commands.prepared is not None and installation.project_skills.prepared is not None
    sources = BundleSources((installation.project_skills, commands), ("claude_code_plugin",))
    inputs = AssessmentInputs(root, projected=sources, consent=consent)
    disabled = builder.assess(
        (PLUGIN_BUNDLE_TOOL_KEY,),
        inputs,
        kinds=(ToolSurfaceKind.PLUGIN_MANIFEST,),
        configured_tools=("codex",),
    )
    assert all(not owner.effects for owner in disabled.assessments)  # Generic selection stays disabled.
    plans = builder.build((PLUGIN_BUNDLE_TOOL_KEY,), project, kinds=(ToolSurfaceKind.PLUGIN_MANIFEST,))
    selections = tuple(SurfaceSelection(plan.tool_key, definition) for plan in plans for definition in plan.definitions)
    bundle = bundle_provider.assess(inputs, disabled.report.surfaces, selections=selections)
    assert bundle.complete, bundle.diagnostics
    composition = managed.compose_installation(installation, commands, staged_bundle=bundle)
    assert composition.commands is commands and composition.installation is installation
    return descriptor, consent, managed, composition, bundle_provider, bundle


def _selected_skill_project(
    seed: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    key_present: bool,
    dist_present: bool,
    pointer: bool = False,
) -> tuple[Path, dict[str, Path]]:
    import yaml

    original, home = seed
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    project = tmp_path / "project"
    shutil.copytree(original, project, symlinks=True)
    config_path = project / ".kittify/config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config.pop("charter", None)
    config.pop("mission_type_activations", None)
    if pointer:
        config["charter"] = "authored.yaml"
        (project / "authored.yaml").write_text("custom: preserved\n" + ("mission_type_activations: []\n" if key_present else ""))
    elif key_present:
        config["mission_type_activations"] = []
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    assert config["agents"]["available"] == ["codex"]
    if dist_present:
        (project / "dist").mkdir()
    (project / ".agents/skills/spec-kitty.plan/SKILL.md").unlink()
    return project, {"project": project, "home": home}


def _assert_selected_delta(effects: tuple, before: Snapshot, after: Snapshot) -> None:
    from tests.upgrade.preview_support.snapshot import net_delta

    assert {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in effects} == {
        (e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in net_delta(before, after)
    }


@pytest.mark.parametrize("key_present", [False, True], ids=["missing-key", "explicit-empty"])
@pytest.mark.parametrize("dist_present", [False, True], ids=["absent-dist", "existing-dist"])
def test_selected_bundle_skill_transitions(
    selected_codex_seed: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
    key_present: bool,
    dist_present: bool,
) -> None:
    from dataclasses import asdict
    from specify_cli.tool_surface.providers.command_skills import CommandSkillsProvider
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    project, roots = _selected_skill_project(
        selected_codex_seed,
        tmp_path,
        monkeypatch,
        key_present=key_present,
        dist_present=dist_present,
    )
    before = snapshot(roots)
    with _write_attempts() as writes:
        descriptor, consent, managed, composition, provider, bundle = _selected_skill_preparation(project)
    assert not writes, writes
    assert_unchanged(before, snapshot(roots))
    assert bundle.effects and any(e.path.endswith("plugin.json") for e in bundle.effects)
    assert any(e.path.endswith("skills/spec-kitty.plan/SKILL.md") for e in bundle.effects)
    assert any("agents/" in e.path for e in bundle.effects)
    with provider.recheck(bundle) as errors:
        assert not errors, errors
    with managed.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        assert not CommandSkillsProvider().preflight(composition.commands)
        assert_unchanged(before, snapshot(roots))
        assert descriptor.apply() is (not key_present)
        provisioned = snapshot(roots)
        result = provider.apply(bundle, consent)
        record_property("bundle_result", json.dumps(asdict(result), default=str))
        assert result.outcome == "applied", result
        staged = snapshot(roots)
        _assert_selected_delta(bundle.effects, provisioned, staged)
        assert not (project / ".agents/skills/spec-kitty.plan/SKILL.md").exists()
        results = managed.apply_composition(composition, consent)
        record_property("skill_results", json.dumps([asdict(r) for r in results], default=str))
        assert all(r.outcome in {"applied", "skipped"} for r in results), results
        _assert_selected_delta(composition.effects, staged, snapshot(roots))
        assert {e.id for e in bundle.effects + composition.effects} == set(result.succeeded) | {i for r in results for i in r.succeeded}
    record_property("effects", json.dumps([asdict(e) for e in bundle.effects + composition.effects], default=str))
    record_property("delta", json.dumps([asdict(e) for e in net_delta(provisioned, snapshot(roots))], default=str))
    settled = snapshot(roots)
    d2, c2, m2, s2, p2, b2 = _selected_skill_preparation(project)
    assert not s2.effects and not b2.effects
    with m2.preflight_composition(s2, c2) as errors:
        assert not errors, errors
        assert not d2.apply()
        assert p2.apply(b2, c2).outcome == "applied"
        assert all(r.outcome in {"applied", "skipped"} for r in m2.apply_composition(s2, c2))
    assert_unchanged(settled, snapshot(roots))
