"""Unit tests for ``tool_surface.providers.managed_skills``.

These tests verify that the managed doctrine-skill provider conforms to the
reporting provider protocol, expands per-tool instances from the
``.kittify/skills-manifest.json`` manifest, probes on-disk state, and delegates
repair to the underlying ``skills.verifier`` (which owns both
``verify_installed_skills`` and ``repair_skills``) without reimplementing its
logic. Doctrine skills must surface as
``surface_kind: "doctrine_skill"`` -- distinct from command skills.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from charter.activation.compiler import _PreparedMissionTypeActivations, prepare_mission_type_activations
from specify_cli.skills.installer import SkillInstallationAssessment, assess_skill_installation

from specify_cli.skills.manifest import (
    compute_content_hash,
    load_manifest,
)
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry
from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.providers.command_skills import (
    CommandSkillsProvider,
    command_skill_definition,
)
from specify_cli.tool_surface.providers.managed_skills import (
    ManagedSkillsProvider,
    doctrine_skill_entries,
    managed_skill_definition,
)
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_PRESENT,
)
from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment, OwnerApplyResult
from tests.upgrade.preview_support.snapshot import Snapshot

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_skill_file(project: Path, rel: str, body: str = "doctrine body") -> str:
    """Materialize a managed skill file and return its content hash."""
    target = project / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return compute_content_hash(target)


def _write_manifest(project: Path, entries: list[dict[str, str]]) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "created_at": "2026-06-14T00:00:00+00:00",
        "updated_at": "2026-06-14T00:00:00+00:00",
        "spec_kitty_version": "",
        "entries": entries,
    }
    (kittify / "skills-manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _entry(
    agent_key: str,
    installed_path: str,
    content_hash: str,
    *,
    skill_name: str = "spec-kitty-setup-doctor",
) -> dict[str, str]:
    return {
        "skill_name": skill_name,
        "source_file": "SKILL.md",
        "installed_path": installed_path,
        "installation_class": "shared-root-capable",
        "agent_key": agent_key,
        "content_hash": content_hash,
        "installed_at": "2026-06-14T00:00:00+00:00",
        "delivery_mode": "copy",
    }


def test_provider_satisfies_reporting_protocol() -> None:
    provider = ManagedSkillsProvider()
    assert isinstance(provider, ReportingSurfaceProvider)
    assert provider.provider_key == "managed_skills"


def test_project_assessment_exposes_effects_but_blocks_uncoordinated_global_contribution(tmp_path: Path) -> None:
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.protocol import AssessingSurfaceProvider
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    _canonical_skill(tmp_path / "source")
    provider = ManagedSkillsProvider(registry_factory=lambda: SkillRegistry(tmp_path / "source"))
    assert isinstance(provider, AssessingSurfaceProvider)
    consent = ApplyConsent(automatic=True)
    before = snapshot({"sandbox": tmp_path})
    assessment = provider.assess(AssessmentInputs(OperationRoot("project", "project", project), consent=consent), (),
                                 selections=(SurfaceSelection("codex", managed_skill_definition()),))
    assert assessment.effects and not assessment.complete
    assert any(item.code == "managed_skills_global_context_required" for item in assessment.diagnostics)
    with provider.recheck(assessment) as diagnostics:
        assert diagnostics
        assert provider.apply(assessment, consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("pointer", [False, True], ids=["legacy", "pointer"])
@pytest.mark.parametrize("missing", [True, False], ids=["missing-key", "explicit-empty"])
def test_managed_provisioning_descriptor_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pointer: bool, missing: bool,
) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    provisioning, installation, registry = _provisioning_installation(tmp_path, monkeypatch, pointer, missing)
    before = snapshot({"sandbox": tmp_path})
    provider = ManagedSkillsProvider()
    assert installation.global_assets.complete, installation.global_assets.diagnostics
    assert installation.project_skills.complete, installation.project_skills.diagnostics
    assert installation.global_assets.effects and installation.project_skills.effects
    consent = installation.project_skills.consent
    # Neither the bare provider nor direct installer can skip original paired preflight.
    from specify_cli.skills.installer import apply_skill_installation
    for results in (provider.apply_installation(installation, consent), apply_skill_installation(installation, consent)):
        assert all(result.outcome == "precondition_changed" and not result.succeeded for result in results)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    with provider.preflight_installation(installation, consent) as errors:
        assert not errors
        assert_unchanged(before, snapshot({"sandbox": tmp_path}))
        assert provisioning.apply() is missing
        after_provision = snapshot({"sandbox": tmp_path})
        results = provider.apply_installation(installation, consent)
    assert all(result.outcome == "applied" for result in results), results
    effects = installation.global_assets.effects + installation.project_skills.effects
    assert {effect.id for effect in effects} == {item for result in results for item in result.succeeded}
    delta = net_delta(after_provision, snapshot({"sandbox": tmp_path}))
    assert {(effect.destination, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
            for effect in effects} == {
        (tmp_path / item.path, item.action, item.after.kind, item.after.sha256, item.after.target, item.after.mode)
        for item in delta
    }
    # Actual post-provisioning canonical rendering/selection is identical; no new
    # mission-type selector is invented, and manifest timestamps do not churn.
    steady = snapshot({"sandbox": tmp_path})
    fresh = assess_skill_installation(
        AssessmentInputs(installation.project_skills.root, consent=consent), registry, installation.agent_keys,
    )
    assert fresh.project_skills.complete and fresh.global_assets.complete
    assert not fresh.project_skills.effects and not fresh.global_assets.effects
    assert all(result.outcome == "skipped" and not result.skipped and not result.succeeded
               for result in provider.apply_installation(fresh, consent))
    assert_unchanged(steady, snapshot({"sandbox": tmp_path}))
    assert all(result.outcome == "precondition_changed" for result in provider.apply_installation(installation, consent))


def _provisioning_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pointer: bool = False, missing: bool = True,
    *, packaged: bool = False, agents: tuple[str, ...] = ("codex", "copilot"),
) -> tuple[_PreparedMissionTypeActivations, SkillInstallationAssessment, SkillRegistry]:
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    _bind_consumer_home(home, monkeypatch)
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex, copilot]\n")
    target = config
    if pointer:
        config.write_text(config.read_text() + "charter: authored.yaml\n")
        target = project / "authored.yaml"
        target.write_text("# authored\nactivated_paradigms: []\n")
    if not missing:
        target.write_text(target.read_text() + "mission_type_activations: []\n")
    _canonical_skill(tmp_path / "source")
    registry = SkillRegistry.from_package() if packaged else SkillRegistry(tmp_path / "source")
    before = snapshot({"sandbox": tmp_path})
    provisioning = prepare_mission_type_activations(project)
    consent = ApplyConsent(automatic=True)
    installation = assess_skill_installation(
        AssessmentInputs(OperationRoot("project", "project", project), projected=provisioning, consent=consent),
        registry, agents,
    )
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    return provisioning, installation, registry


@pytest.mark.parametrize("changed", ["config", "already-provisioned", "source", "global", "consent", "incomplete"])
def test_managed_provisioning_original_pair_refuses_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str,
) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provisioning, installation, _ = _provisioning_installation(tmp_path, monkeypatch)
    consent = installation.project_skills.consent
    if changed == "config":
        assert provisioning.write.before_bytes is not None
        provisioning.write.target.write_bytes(provisioning.write.before_bytes + b"# changed\n")
    elif changed == "already-provisioned":
        assert provisioning.apply()
    elif changed == "source":
        (tmp_path / "source/a/SKILL.md").write_text("changed")
    elif changed == "global":
        (tmp_path / "home/.agents").mkdir()
    elif changed == "consent":
        consent = ApplyConsent(automatic=False)
    else:
        installation = replace(installation, project_skills=replace(installation.project_skills, complete=False))
    before = snapshot({"sandbox": tmp_path})
    provider = ManagedSkillsProvider()
    with provider.preflight_installation(installation, consent) as errors:
        assert errors
        results = provider.apply_installation(installation, consent)
        assert all(result.outcome == "precondition_changed" and not result.succeeded for result in results)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("changed", [
    "not-applied", "bytes", "replace", "mode", "hardlink", "source", "config-pointer", "global", "destination-link",
])
def test_managed_provisioning_poststate_refuses_both_before_skill_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str,
) -> None:
    import os
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provisioning, installation, registry = _provisioning_installation(tmp_path, monkeypatch, pointer=True)
    destination = tmp_path / "project/.agents/skills/a/SKILL.md"
    if changed == "destination-link":
        from specify_cli.tool_surface.operations import AssessmentInputs
        destination.parent.mkdir(parents=True)
        destination.write_text("user content")
        installation = assess_skill_installation(
            AssessmentInputs(installation.project_skills.root, projected=provisioning, consent=installation.project_skills.consent),
            registry, installation.agent_keys,
        )
    provider = ManagedSkillsProvider()
    consent = installation.project_skills.consent
    with provider.preflight_installation(installation, consent) as errors:
        assert not errors
        if changed != "not-applied":
            assert provisioning.apply()
        target = provisioning.write.target
        if changed == "bytes":
            target.write_bytes(target.read_bytes() + b"# unexpected\n")
        elif changed == "replace":
            replacement = target.with_suffix(".replacement")
            replacement.write_bytes(target.read_bytes())
            replacement.replace(target)
        elif changed == "mode":
            target.chmod(0o600)
        elif changed == "hardlink":
            os.link(target, tmp_path / "extra-link")
        elif changed == "source":
            (tmp_path / "source/a/SKILL.md").write_text("changed")
        elif changed == "config-pointer":
            config = tmp_path / "project/.kittify/config.yaml"
            config.write_text(config.read_text() + "# unexpected pointer config change\n")
        elif changed == "global":
            (tmp_path / "home/.agents").mkdir()
        elif changed == "destination-link":
            destination.unlink()
            destination.symlink_to(target)
        before = snapshot({"sandbox": tmp_path})
        results = provider.apply_installation(installation, consent)
        assert all(result.outcome == "precondition_changed" and not result.succeeded for result in results), results
        assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_managed_provisioning_package_three_families_retains_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.skills import installer
    from specify_cli.tool_surface.operations import AssessmentInputs
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    provisioning, original, registry = _provisioning_installation(tmp_path, monkeypatch, packaged=True, agents=("codex",))
    consent = original.project_skills.consent
    installation = assess_skill_installation(
        AssessmentInputs(original.project_skills.root, projected=provisioning, consent=consent), registry, ("codex",),
        runtime=True, commands=True, command_agent_keys=["claude"],
    )
    assert installation.global_assets.complete and installation.project_skills.complete
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Apply must not reprepare or rerender")
    monkeypatch.setattr(installer, "prepare_mission_type_activations", forbidden)
    monkeypatch.setattr(installer, "ensure_skill_frontmatter", forbidden)
    monkeypatch.setattr(SkillRegistry, "snapshot_catalog", forbidden)
    provider = ManagedSkillsProvider()
    with provider.preflight_installation(installation, consent) as errors:
        assert not errors
        assert provisioning.apply()
        before = snapshot({"sandbox": tmp_path})
        results = provider.apply_installation(installation, consent)
    assert all(result.outcome == "applied" for result in results), results
    effects = installation.global_assets.effects + installation.project_skills.effects
    assert len(effects) > 300
    assert {effect.id for effect in effects} == {item for result in results for item in result.succeeded}
    assert {(effect.destination, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
            for effect in effects} == {
        (tmp_path / item.path, item.action, item.after.kind, item.after.sha256, item.after.target, item.after.mode)
        for item in net_delta(before, snapshot({"sandbox": tmp_path}))
    }


def test_managed_provisioning_empty_selection_and_context_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provisioning, installation, _ = _provisioning_installation(tmp_path, monkeypatch, agents=())
    assert installation.agent_keys == ()
    assert installation.global_assets.complete and not installation.global_assets.effects
    assert not any(effect.path.endswith("SKILL.md") for effect in installation.project_skills.effects)
    provider = ManagedSkillsProvider()
    consent = installation.project_skills.consent
    before = snapshot({"sandbox": tmp_path})
    with pytest.raises(RuntimeError, match="consumer stopped"), provider.preflight_installation(installation, consent) as errors:
        assert not errors
        raise RuntimeError("consumer stopped")
    assert all(result.outcome == "precondition_changed" for result in provider.apply_installation(installation, consent))
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    with provider.preflight_installation(installation, consent) as errors:
        assert not errors
        assert provisioning.apply()
        results = provider.apply_installation(installation, consent)
        assert {result.owner_key: result.outcome for result in results} == {
            "global_assets": "skipped", "managed_skills": "skipped",
        }
        assert not installation.project_skills.effects
        assert {item for result in results for item in result.succeeded} == {
            effect.id for effect in installation.project_skills.effects
        }


def test_managed_provisioning_requires_automatic_consent_before_provisioning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provisioning, original, registry = _provisioning_installation(tmp_path, monkeypatch)
    consent = ApplyConsent(automatic=False)
    installation = assess_skill_installation(
        AssessmentInputs(original.project_skills.root, projected=provisioning, consent=consent), registry, ("codex",),
    )
    before = snapshot({"sandbox": tmp_path})
    with ManagedSkillsProvider().preflight_installation(installation, consent) as errors:
        assert errors
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_managed_provisioning_shared_update_preserves_unknown_and_unselected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    _, original, registry = _provisioning_installation(tmp_path, monkeypatch)
    consent = original.project_skills.consent
    root = original.project_skills.root
    provider = ManagedSkillsProvider()
    initial = assess_skill_installation(AssessmentInputs(root, consent=consent), registry, ("codex",))
    assert all(result.outcome == "applied" for result in provider.apply_installation(initial, consent))
    installed = tmp_path / "project/.agents/skills/a/SKILL.md"
    previous = installed.read_bytes()
    (tmp_path / "source/a/SKILL.md").write_text("canonical changed")
    _canonical_skill(tmp_path / "source", "unknown")
    unknowns = tuple(tmp_path / location / ".agents/skills/unknown/SKILL.md" for location in ("home", "project"))
    for path in unknowns:
        path.parent.mkdir(parents=True)
        path.write_text("user authored, not canonical")
    provisioning = prepare_mission_type_activations(root.path)
    installation = assess_skill_installation(
        AssessmentInputs(root, projected=provisioning, consent=consent), registry, ("copilot",),
    )
    updates = [effect for effect in installation.project_skills.effects if effect.path == ".agents/skills/a/SKILL.md"]
    backups = [effect for effect in installation.project_skills.effects
               if ".migration-backup/" in effect.path and effect.after.kind == "file"]
    assert len(updates) == len(backups) == 1
    for effect in (*updates, *backups):
        assert effect.logical_owners == ("codex", "copilot")
        assert len(effect.surface_ids) == 2
        assert tuple((proof.kind, proof.reference) for proof in effect.ownership) == (
            ("manifest", ".kittify/skills-manifest.json:codex:.agents/skills/a/SKILL.md"),
        )
    with provider.preflight_installation(installation, consent) as errors:
        assert not errors
        assert provisioning.apply()
        before = snapshot({"sandbox": tmp_path})
        results = provider.apply_installation(installation, consent)
    assert all(result.outcome == "applied" for result in results), results
    effects = installation.global_assets.effects + installation.project_skills.effects
    # #4714: apply_installation now acquires the global-skills owner lock via
    # kernel.locks.machine_file_lock, whose release truncates (never unlinks)
    # its dedicated ``.agent-skills.lock`` sidecar (G3). A cold acquisition
    # therefore leaves a net create/update on that path in the raw lstat
    # oracle's before/after diff even though it is a coordination artifact,
    # not a managed asset -- it never appears in (and must never be asserted
    # against) the provider's own tracked effects. Excluded here, not in the
    # shared net_delta helper: snapshot.py is a deliberately production-blind
    # independent oracle (see its module docstring).
    delta = {item for item in net_delta(before, snapshot({"sandbox": tmp_path})) if not item.path.endswith(".lock")}
    assert {effect.destination for effect in effects} == {tmp_path / item.path for item in delta}
    assert backups[0].destination.read_bytes() == previous
    assert all(path.read_text() == "user authored, not canonical" for path in unknowns)
    manifest = load_manifest(root.path)
    assert manifest is not None
    assert {entry.agent_key for entry in manifest.entries if entry.skill_name == "a"} == {"codex", "copilot"}


@pytest.mark.parametrize("authority", ["canonical-source", "skill-manifest"])
def test_managed_provisioning_rejects_skill_authority_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: str,
) -> None:
    from specify_cli.skills.installer import assess_project_skills
    from specify_cli.tool_surface.operations import AssessmentInputs
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    _, original, _ = _provisioning_installation(tmp_path, monkeypatch)
    project = original.project_skills.root.path
    source = project / "source"
    _canonical_skill(source)
    if authority == "canonical-source":
        target = source / "a/SKILL.md"
        target.write_text("activated_paradigms: []\n")
    else:
        _write_manifest(project, [])
        target = project / ".kittify/skills-manifest.json"
    config = project / ".kittify/config.yaml"
    config.write_text(config.read_text() + f"charter: {target.relative_to(project).as_posix()}\n")
    before = snapshot({"sandbox": tmp_path})
    provisioning = prepare_mission_type_activations(project)
    assessment = assess_project_skills(
        AssessmentInputs(original.project_skills.root, projected=provisioning), SkillRegistry(source), ("codex",),
    )
    assert not assessment.complete and any("overlaps" in item.message for item in assessment.diagnostics)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def _bind_consumer_home(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key, suffix in {
        "HOME": "", "USERPROFILE": "", "SPEC_KITTY_HOME": ".kittify",
        "XDG_CONFIG_HOME": ".config", "XDG_DATA_HOME": ".local/share",
        "XDG_STATE_HOME": ".local/state", "XDG_CACHE_HOME": ".cache",
        "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
        "OPENCODE_CONFIG_DIR": ".config/opencode",
    }.items():
        monkeypatch.setenv(key, str(home / suffix))


@pytest.mark.parametrize("all_families", [False, True])
def test_coordinated_provider_dispatch_keeps_both_owner_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, all_families: bool,
) -> None:
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from collections.abc import Sequence
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    project.mkdir()
    _bind_consumer_home(home, monkeypatch)
    _canonical_skill(tmp_path / "source")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    root = OperationRoot("project", "project", project)
    before = snapshot({"sandbox": tmp_path})
    installation = assess_skill_installation(
        AssessmentInputs(root, consent=consent), registry, ("codex",),
        runtime=all_families, commands=all_families, command_agent_keys=["claude"],
    )
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)
    assessment = provider.assess(AssessmentInputs(root, projected=installation, consent=consent), (),
                                 selections=(SurfaceSelection("codex", managed_skill_definition()),))
    assert assessment is installation.project_skills and assessment.complete
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    dispatched: list[tuple[OwnerAssessment, ...]] = []
    real_dispatch = SurfaceRepairService.apply_assessments

    def observe_dispatch(
        service: SurfaceRepairService, assessments: Sequence[OwnerAssessment], explicit_consent: ApplyConsent,
    ) -> tuple[OwnerApplyResult, ...]:
        dispatched.append(tuple(assessments))
        results: tuple[OwnerApplyResult, ...] = real_dispatch(service, assessments, explicit_consent)
        return results

    monkeypatch.setattr(SurfaceRepairService, "apply_assessments", observe_dispatch)
    results = provider.apply_installation(installation, consent)
    assert dispatched == [(installation.global_assets, assessment)]
    assert all(result.outcome == "applied" for result in results), [
        (result.owner_key, result.outcome, result.diagnostics) for result in results
    ]
    effects = installation.global_assets.effects + assessment.effects
    assert {effect.id for effect in effects} == {effect_id for result in results for effect_id in result.succeeded}
    expected = {(effect.destination.relative_to(tmp_path).as_posix(), effect.action, effect.after.kind,
                 effect.after.sha256, effect.after.target, effect.after.mode) for effect in effects}
    assert {(effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
            for effect in net_delta(before, snapshot({"sandbox": tmp_path}))} == expected


@pytest.mark.parametrize("route", ["direct", "provider", "paired-provider"])
def test_paired_consumer_config_change_refuses_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str,
) -> None:
    from specify_cli.skills.installer import assess_skill_installation, apply_skill_installation
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.managed_skills import GlobalSkillAssetsProvider
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _bind_consumer_home(home, monkeypatch)
    _canonical_skill(tmp_path / "source")
    (project / ".kittify").mkdir()
    config = project / ".kittify/config.yaml"
    config.write_text("agents:\n  available: [codex]\n")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    installation = assess_skill_installation(inputs, registry, ("codex",))
    assert installation.global_assets.complete and installation.project_skills.complete
    assert installation.global_assets.effects and installation.project_skills.effects
    config.write_text(config.read_text() + "review_change: true\n")
    before = snapshot({"sandbox": tmp_path})
    results: tuple[OwnerApplyResult, ...]
    if route == "direct":
        results = apply_skill_installation(installation, consent)
    else:
        provider = ManagedSkillsProvider(registry_factory=lambda: registry)
        assessment = provider.assess(
            AssessmentInputs(inputs.root, projected=installation, consent=consent), (),
            selections=(SurfaceSelection("codex", managed_skill_definition()),),
        )
        assert assessment is installation.project_skills
        results = (
            provider.apply_installation(installation, consent) if route == "paired-provider"
            else SurfaceRepairService([GlobalSkillAssetsProvider(), provider]).apply_assessments(
                (installation.global_assets, assessment), consent,
            )
        )
    changes = net_delta(before, snapshot({"sandbox": tmp_path}))
    assert not changes, [(effect.path, effect.action) for effect in changes]
    assert all(result.outcome == "precondition_changed" and not result.succeeded for result in results)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_paired_provider_global_change_refuses_project_and_context_does_not_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.managed_skills import GlobalSkillAssetsProvider
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _bind_consumer_home(home, monkeypatch)
    _canonical_skill(tmp_path / "source")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    installation = assess_skill_installation(inputs, registry, ("codex",))
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)
    global_path = home / ".agents/skills/a/SKILL.md"
    global_path.parent.mkdir(parents=True)
    global_path.write_text("new unknown content")
    before = snapshot({"sandbox": tmp_path})
    results = provider.apply_installation(installation, consent)
    assert len(results) == 2 and all(result.outcome == "precondition_changed" for result in results)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    fresh = assess_skill_installation(inputs, registry, ("codex",))
    results = provider.apply_installation(fresh, consent)
    assert all(result.outcome == "applied" for result in results)
    after = snapshot({"sandbox": tmp_path})
    adapter = GlobalSkillAssetsProvider()
    with adapter.recheck(fresh.global_assets) as errors:
        assert errors[0].code == "paired_skill_preflight_required"
    assert adapter.apply(fresh.global_assets, consent).outcome == "precondition_changed"
    assert_unchanged(after, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("refusal", ["consent", "incomplete", "dispatch-error"])
def test_paired_provider_refusal_and_exception_release_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusal: str,
) -> None:
    from dataclasses import replace
    from collections.abc import Sequence
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.managed_skills import GlobalSkillAssetsProvider
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    _bind_consumer_home(home, monkeypatch)
    _canonical_skill(tmp_path / "source")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    installation = assess_skill_installation(
        AssessmentInputs(OperationRoot("project", "project", project), consent=consent), registry, ("codex",),
    )
    provider = ManagedSkillsProvider(registry_factory=lambda: registry)
    before = snapshot({"sandbox": tmp_path})
    if refusal == "dispatch-error":
        def fail_dispatch(
            service: SurfaceRepairService, assessments: Sequence[OwnerAssessment], explicit_consent: ApplyConsent,
        ) -> tuple[OwnerApplyResult, ...]:
            _ = service, assessments, explicit_consent
            raise RuntimeError("injected dispatch exception")

        monkeypatch.setattr(SurfaceRepairService, "apply_assessments", fail_dispatch)
        with pytest.raises(RuntimeError, match="injected dispatch exception"):
            provider.apply_installation(installation, consent)
    else:
        changed = (replace(installation, project_skills=replace(installation.project_skills, complete=False))
                   if refusal == "incomplete" else installation)
        explicit = ApplyConsent(automatic=True, overwrite_paths=(".agents/skills/a/SKILL.md",)) if refusal == "consent" else consent
        results = provider.apply_installation(changed, explicit)
        assert all(result.outcome == "precondition_changed" for result in results)
    adapter = GlobalSkillAssetsProvider()
    with adapter.recheck(installation.global_assets) as errors:
        assert errors[0].code == "paired_skill_preflight_required"
    assert adapter.apply(installation.global_assets, consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("dry_run", [True, False])
def test_real_provider_never_reports_preserved_unknown_content_repaired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dry_run: bool,
) -> None:
    from specify_cli.tool_surface.status import SurfaceStatus
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _canonical_skill(tmp_path / "source")
    provider = ManagedSkillsProvider(registry_factory=lambda: SkillRegistry(tmp_path / "source"))
    instance = provider.expand(managed_skill_definition(), "codex", project)[0]
    instance.path.parent.mkdir(parents=True)
    instance.path.write_text("user-owned content")
    before = snapshot({"sandbox": tmp_path})
    result = provider.repair(project, [SurfaceStatus(instance=instance, state=STATE_DRIFTED)], dry_run=dry_run)
    assert not result.repaired
    assert instance.surface_id in result.skipped
    assert instance.path.read_text() == "user-owned content"
    if dry_run:
        assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_real_provider_partial_failure_reports_paths_not_count_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.skills import installer

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _canonical_skill(tmp_path / "source", "a")
    _canonical_skill(tmp_path / "source", "b")
    provider = ManagedSkillsProvider(registry_factory=lambda: SkillRegistry(tmp_path / "source"))
    instances = provider.expand(managed_skill_definition(), "codex", project)
    statuses = [provider.probe(instance) for instance in reversed(instances)]
    writer = installer._apply_project_skill_write

    def fail_second(write: installer.PreparedProjectSkillWrite) -> None:
        if write.effect.path == ".agents/skills/b/SKILL.md":
            raise OSError("injected second project file failure")
        writer(write)

    monkeypatch.setattr(installer, "_apply_project_skill_write", fail_second)
    result = provider.repair(project, statuses)
    assert result.repaired == (instances[0].surface_id,)
    assert instances[1].surface_id in result.failed
    assert instances[0].path.is_file() and not instances[1].path.exists()
    assert not (project / ".kittify/skills-manifest.json").exists()


def test_managed_skills_provider_can_handle_doctrine_skill() -> None:
    provider = ManagedSkillsProvider()
    definition = managed_skill_definition()
    assert definition.kind == ToolSurfaceKind.DOCTRINE_SKILL
    assert provider.can_handle(definition) is True


def test_managed_skills_provider_cannot_handle_command_skill() -> None:
    provider = ManagedSkillsProvider()
    other = command_skill_definition()
    assert other.kind == ToolSurfaceKind.COMMAND_SKILL
    assert provider.can_handle(other) is False


def _canonical_skill(root: Path, name: str = "a") -> CanonicalSkill:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("canonical", encoding="utf-8")
    return CanonicalSkill(name=name, skill_dir=skill_dir, skill_md=skill_md)


def _manifest_only_provider() -> ManagedSkillsProvider:
    return ManagedSkillsProvider(registry_factory=lambda: _StubRegistry([]))


def test_managed_skills_expand_no_manifest_uses_registry_policy(
    tmp_path: Path,
) -> None:
    skill = _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(
        registry_factory=lambda: _StubRegistry([skill]),
    )

    instances = provider.expand(managed_skill_definition(), "codex", tmp_path)

    assert len(instances) == 1
    assert instances[0].path == tmp_path / ".agents/skills/a/SKILL.md"
    assert provider.probe(instances[0]).state == STATE_MISSING


def test_managed_skills_expand_returns_per_tool_skills(tmp_path: Path) -> None:
    """Skills count must match what the manifest expects for the tool."""
    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    h2 = _write_skill_file(tmp_path, ".agents/skills/b/SKILL.md")
    other = _write_skill_file(tmp_path, ".claude/skills/c/SKILL.md")
    _write_manifest(
        tmp_path,
        [
            _entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a"),
            _entry("codex", ".agents/skills/b/SKILL.md", h2, skill_name="b"),
            _entry("claude", ".claude/skills/c/SKILL.md", other, skill_name="c"),
        ],
    )
    provider = _manifest_only_provider()
    instances = provider.expand(managed_skill_definition(), "codex", tmp_path)
    assert len(instances) == 2
    assert all(i.owner == "codex" for i in instances)
    assert all(i.definition.kind == ToolSurfaceKind.DOCTRINE_SKILL for i in instances)


def test_doctrine_skill_entries_helper(tmp_path: Path) -> None:
    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    entries = doctrine_skill_entries(tmp_path, "codex")
    assert [e.agent_key for e in entries] == ["codex"]
    assert doctrine_skill_entries(tmp_path, "claude") == []
    assert doctrine_skill_entries(tmp_path / "missing", "codex") == []


def test_managed_skills_probe_present(tmp_path: Path) -> None:
    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    provider = _manifest_only_provider()
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_PRESENT
    assert status.findings == ()


def test_managed_skills_probe_detects_missing(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", "sha256:deadbeef", skill_name="a")],
    )
    provider = _manifest_only_provider()
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "generated-surface-missing"
    assert status.findings[0].repair_command is not None


def test_managed_skills_probe_detects_drift(tmp_path: Path) -> None:
    from dataclasses import replace

    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    provider = _manifest_only_provider()
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    drifted = replace(instance, file_hash="sha256:" + "00" * 32)
    status = provider.probe(drifted)
    assert status.state == STATE_DRIFTED
    assert status.findings[0].code == "managed-file-drift"


def test_managed_skills_repair_no_actionable_returns_clean(tmp_path: Path) -> None:
    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    provider = _manifest_only_provider()
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    present = provider.probe(instance)
    assert present.state == STATE_PRESENT
    result = provider.repair(tmp_path, [present])
    assert result.repaired == ()
    assert result.failed == ()


def test_managed_skills_repair_dry_run_does_not_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(registry_factory=lambda: SkillRegistry(tmp_path / "canonical"))
    instance = provider.expand(managed_skill_definition(), "codex", project)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING
    before = snapshot({"sandbox": tmp_path})
    result = provider.repair(project, [missing], dry_run=True)
    assert result.dry_run is True
    assert result.repaired  # reported, but nothing installed
    assert not instance.path.exists()
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_managed_skills_repair_without_manifest_installs_expected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(
        registry_factory=lambda: SkillRegistry(tmp_path / "canonical"),
    )
    instance = provider.expand(managed_skill_definition(), "codex", project)[0]
    missing = provider.probe(instance)
    result = provider.repair(project, [missing])
    assert result.failed == ()
    assert result.repaired
    assert instance.path.is_file()
    assert (home / ".agents/skills/a/SKILL.md").is_file()
    manifest = load_manifest(project)
    assert manifest is not None
    assert [entry.installed_path for entry in manifest.entries] == [
        ".agents/skills/a/SKILL.md"
    ]


class _StubVerifyResult:
    def __init__(self, ok: bool) -> None:
        self.ok = ok


class _StubVerifier:
    def __init__(self, ok: bool) -> None:
        self._ok = ok
        self.calls: list[Path] = []

    def verify_installed_skills(self, project_path: Path) -> _StubVerifyResult:
        self.calls.append(project_path)
        return _StubVerifyResult(self._ok)


class _StubInstaller:
    def __init__(self, repaired: int, failed: int) -> None:
        self._repaired = repaired
        self._failed = failed
        self.calls: list[Path] = []

    def repair_skills(
        self, project_path: Path, verify_result: object, registry: object
    ) -> tuple[int, int]:
        self.calls.append(project_path)
        return self._repaired, self._failed


class _StubRegistry(SkillRegistry):
    def __init__(self, skills: list[CanonicalSkill]) -> None:
        self._skills = skills

    def discover_skills(self) -> list[CanonicalSkill]:
        return self._skills


def test_managed_skills_repair_calls_installer(tmp_path: Path) -> None:
    """Repair must delegate to verifier+installer, not reimplement them."""
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", "sha256:deadbeef", skill_name="a")],
    )
    verifier = _StubVerifier(ok=False)
    installer = _StubInstaller(repaired=1, failed=0)
    skill = _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(
        verifier=verifier,
        installer=installer,
        registry_factory=lambda: _StubRegistry([skill]),
    )
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    missing = provider.probe(instance)
    result = provider.repair(tmp_path, [missing])
    assert verifier.calls == [tmp_path]
    assert installer.calls == [tmp_path]
    assert result.repaired
    assert result.failed == ()


def test_managed_skills_repair_reports_installer_failures(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", "sha256:deadbeef", skill_name="a")],
    )
    skill = _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(
        verifier=_StubVerifier(ok=False),
        installer=_StubInstaller(repaired=0, failed=1),
        registry_factory=lambda: _StubRegistry([skill]),
    )
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    missing = provider.probe(instance)
    result = provider.repair(tmp_path, [missing])
    assert result.failed
    assert "failed to repair" in result.failed[0]


def test_managed_skills_repair_skips_when_verifier_clean(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", "sha256:deadbeef", skill_name="a")],
    )
    installer = _StubInstaller(repaired=0, failed=0)
    skill = _canonical_skill(tmp_path / "canonical")
    provider = ManagedSkillsProvider(
        verifier=_StubVerifier(ok=True),
        installer=installer,
        registry_factory=lambda: _StubRegistry([skill]),
    )
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    missing = provider.probe(instance)
    result = provider.repair(tmp_path, [missing])
    # Verifier reports clean -> installer is never invoked.
    assert installer.calls == []
    assert result.repaired == ()
    assert result.failed == ()


def test_managed_skills_repair_fails_without_registry(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", "sha256:deadbeef", skill_name="a")],
    )
    provider = ManagedSkillsProvider(
        verifier=_StubVerifier(ok=False),
        installer=_StubInstaller(repaired=0, failed=0),
        registry_factory=lambda: _StubRegistry([]),
    )
    instance = provider.expand(managed_skill_definition(), "codex", tmp_path)[0]
    missing = provider.probe(instance)
    result = provider.repair(tmp_path, [missing])
    assert result.failed
    assert "no canonical skill registry" in result.failed[0]


def test_repair_default_collaborator_binds_repair_skills() -> None:
    """Regression: the default (no-DI) repair collaborator must own repair_skills.

    Cycle-1 reject: the default ``self._installer`` was bound to
    ``skills.installer``, which has no ``repair_skills`` -- so the live ``--fix``
    path raised ``AttributeError`` while every DI test masked it with a stub. This
    guard fails fast if the wrong module is ever rebound.
    """
    provider = ManagedSkillsProvider()
    assert callable(getattr(provider._installer, "repair_skills", None))


def test_repair_default_path_repairs_without_injection(tmp_path: Path) -> None:
    """Regression: run ``repair`` with NO injected collaborators (real default).

    Exercises the production wiring the CLI ``--fix`` uses: the default
    ``skills.verifier`` collaborator and the real canonical ``SkillRegistry``.
    A real canonical skill is recorded in the manifest, deleted on disk so it is
    "missing", then repaired -- proving the default path does not raise and
    actually restores the file. Cycle-1 reject was masked because every repair
    test injected a ``_StubInstaller``; this one injects nothing.
    """
    skill_name = "ad-hoc-profile-load"
    installed_rel = ".agents/skills/ad-hoc-profile-load/SKILL.md"
    project = tmp_path.resolve()  # dodge macOS /var -> /private/var symlink mismatch
    placeholder_hash = _write_skill_file(project, installed_rel, body="placeholder")
    _write_manifest(
        project,
        [
            _entry(
                "codex",
                installed_rel,
                placeholder_hash,
                skill_name=skill_name,
            )
        ],
    )
    # Make the managed skill "missing" so repair must restore it.
    (project / installed_rel).unlink()

    provider = ManagedSkillsProvider()  # no verifier/installer/registry injected
    instance = provider.expand(managed_skill_definition(), "codex", project)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING

    result = provider.repair(project, [missing])  # real default --fix path

    assert result.failed == ()
    assert result.repaired  # at least the actionable id reported repaired
    restored = project / installed_rel
    assert restored.exists()
    assert restored.read_text(encoding="utf-8").strip()  # canonical content


def _make_real_providers() -> list[ReportingSurfaceProvider]:
    """Build the real provider list used by the two integration tests below.

    WP03: SurfaceProviderRegistry._registrations is empty until WP04 wires
    providers.  These tests pre-populate via monkeypatch on build_providers /
    build_registry so they exercise real provider logic without relying on the
    registry being populated.  WP04 will delete this helper and let the registry
    supply providers automatically.
    """
    return [CommandSkillsProvider(), ManagedSkillsProvider()]


def _make_real_registry(tool_keys: list[str]) -> object:
    """Build a real ToolSurfaceRegistry with command and doctrine definitions.

    Used by the two integration tests below to bypass the empty registry at
    WP03 stage.  WP04 will remove this helper.
    """
    from specify_cli.tool_surface.registry import ToolSurfaceRegistry

    registry = ToolSurfaceRegistry()
    definitions = (command_skill_definition(), managed_skill_definition())
    for tool_key in tool_keys:
        for defn in definitions:
            registry.register_definition(tool_key, defn)
    return registry


def test_doctrine_vs_command_skill_in_doctor_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """doctor tool-surfaces output separates doctrine and command kinds."""
    import specify_cli.tool_surface.service as svc

    # WP03: pre-populate build_providers and build_registry with real impls
    # because SurfaceProviderRegistry._registrations is empty until WP04.
    monkeypatch.setattr(svc, "build_providers", _make_real_providers)
    monkeypatch.setattr(svc, "build_registry", _make_real_registry)

    from specify_cli.tool_surface.service import run_tool_surfaces

    # One doctrine skill registered in the managed manifest.
    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    # An empty command-skills manifest so the command-skill provider runs too.
    (tmp_path / ".kittify" / "command-skills-manifest.json").write_text(
        json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8"
    )
    outcome = run_tool_surfaces(tmp_path, ["codex"])
    kinds = {s.instance.definition.kind for s in outcome.report.surfaces}
    assert ToolSurfaceKind.DOCTRINE_SKILL in kinds
    assert ToolSurfaceKind.COMMAND_SKILL in kinds
    payload = outcome.to_json()
    surface_kinds = {entry["kind"] for entry in payload["surfaces"]}
    assert "doctrine_skill" in surface_kinds
    assert "command_skill" in surface_kinds


def test_run_tool_surfaces_kind_filter_doctrine_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import specify_cli.tool_surface.service as svc
    from specify_cli.tool_surface.service import run_tool_surfaces

    # WP03: pre-populate build_providers and build_registry with real impls
    # because SurfaceProviderRegistry._registrations is empty until WP04.
    monkeypatch.setattr(svc, "build_providers", _make_real_providers)
    monkeypatch.setattr(svc, "build_registry", _make_real_registry)
    # _KIND_TOKENS is a module-level constant built at import time from the
    # (currently empty) registry.  Patch it so surface_kind_from_token works.
    monkeypatch.setattr(
        svc,
        "_KIND_TOKENS",
        {"doctrine-skill": ToolSurfaceKind.DOCTRINE_SKILL},
    )

    h1 = _write_skill_file(tmp_path, ".agents/skills/a/SKILL.md")
    _write_manifest(
        tmp_path,
        [_entry("codex", ".agents/skills/a/SKILL.md", h1, skill_name="a")],
    )
    (tmp_path / ".kittify" / "command-skills-manifest.json").write_text(
        json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8"
    )
    kind = svc.surface_kind_from_token("doctrine-skill")
    assert kind == ToolSurfaceKind.DOCTRINE_SKILL
    outcome = run_tool_surfaces(tmp_path, ["codex"], kinds=[kind])
    kinds = {s.instance.definition.kind for s in outcome.report.surfaces}
    assert kinds == {ToolSurfaceKind.DOCTRINE_SKILL}


def _shared_parent_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    parents: bool = False,
    pointer: bool = False,
    empty: bool = False,
) -> tuple[dict[str, Path], Snapshot, _PreparedMissionTypeActivations, ApplyConsent, SkillInstallationAssessment, OwnerAssessment, ManagedSkillsProvider]:
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.skills.registry import SkillRegistry
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.plan import SurfacePlanBuilder
    from specify_cli.tool_surface.service import build_providers, build_registry
    from tests.upgrade.preview_support.snapshot import snapshot

    home = tmp_path / "home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex]\n")
    target = config
    if pointer:
        target = project / "authored.yaml"
        target.write_text("custom: preserved\n")
        config.write_text(config.read_text() + "charter: authored.yaml\n")
    if empty:
        target.write_text(target.read_text() + "mission_type_activations: []\n")
    if parents:
        (project / ".agents/skills").mkdir(parents=True)
    roots = {"project": project, "home": home}
    before = snapshot(roots)
    provisioning = prepare_mission_type_activations(project)
    consent = ApplyConsent(automatic=True)
    root = OperationRoot("project", "project", project)
    registry = SkillRegistry.from_package()
    slash_agents = [key for key in ("codex",) if key in AGENT_COMMAND_CONFIG]
    assert slash_agents == []
    installation = assess_skill_installation(
        AssessmentInputs(root, projected=provisioning, consent=consent),
        registry,
        ("codex",),
        runtime=True,
        commands=True,
        command_agent_keys=slash_agents,
    )
    providers = build_providers()
    builder = SurfacePlanBuilder(build_registry(("codex",)), providers)
    commands = builder.assess(
        ("codex",),
        AssessmentInputs(root, projected=provisioning, consent=consent),
        kinds=(ToolSurfaceKind.COMMAND_SKILL,),
    ).assessments[0]
    managed = builder.assess(
        ("codex",),
        AssessmentInputs(root, projected=installation, consent=consent),
        kinds=(ToolSurfaceKind.DOCTRINE_SKILL,),
    ).assessments[0]
    assert managed == installation.project_skills
    assert all(a.complete for a in (installation.global_assets, managed, commands))
    provider = next(p for p in providers if isinstance(p, ManagedSkillsProvider))
    return roots, before, provisioning, consent, installation, commands, provider


def _shared_write_observer() -> AbstractContextManager[list[str]]:
    from contextlib import contextmanager
    import os
    import sys
    from tests.upgrade.preview_support.write_observer import EVENTS

    @contextmanager
    def observing() -> Iterator[list[str]]:
        events: list[str] = []
        active = True

        def observe(event: str, args: tuple[object, ...]) -> None:
            write_open = event == "open" and isinstance(args[2], int) and bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if active and (event in EVENTS or write_open):
                events.append(event)

        sys.addaudithook(observe)
        try:
            yield events
        finally:
            active = False

    return observing()


@pytest.mark.parametrize("parents,pointer,empty", [(False, False, False), (True, False, False), (False, True, False), (False, True, True)])
def test_shared_parent_composition_cold_real_owners(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
    parents: bool,
    pointer: bool,
    empty: bool,
) -> None:
    from dataclasses import asdict
    from specify_cli.tool_surface.operations import coalesce_effects
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    roots, before, provisioning, consent, installation, commands, provider = _shared_parent_case(
        tmp_path,
        monkeypatch,
        parents=parents,
        pointer=pointer,
        empty=empty,
    )
    owners = (installation.global_assets, installation.project_skills, commands)
    effects = tuple(e for a in owners for e in a.effects)
    # Ordinary coalescing must still reject unrelated executable owners.
    if parents:
        coalesce_effects(effects)
    else:
        with pytest.raises(ValueError, match="Owner effect conflict"):
            coalesce_effects(effects)
    with _shared_write_observer() as writes:
        composition = provider.compose_installation(installation, commands)
    assert not writes
    assert_unchanged(before, snapshot(roots))
    shared = {e.destination for e in installation.project_skills.effects} & {e.destination for e in commands.effects}
    assert shared == (set() if parents else {roots["project"] / ".agents", roots["project"] / ".agents/skills"})
    for path in shared:
        claims = [e for e in effects if e.destination == path]
        combined = [e for e in composition.effects if e.destination == path]
        assert len(claims) == 2 and len(combined) == 1
        assert combined[0].owner == commands.owner_key
        assert set(combined[0].ownership) == {p for e in claims for p in e.ownership}
        assert set(combined[0].surface_ids) == {s for e in claims for s in e.surface_ids}
    mkdir = Path.mkdir
    physical_creations: list[Path] = []

    def observed_mkdir(path: Path, mode: int = 0o777, parents: bool = False, exist_ok: bool = False) -> None:
        if path in shared:
            physical_creations.append(path)
        mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", observed_mkdir)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        assert_unchanged(before, snapshot(roots))
        assert provisioning.apply() is not empty
        after_provision = snapshot(roots)
        results = provider.apply_composition(composition, consent)
    assert all(r.outcome in {"applied", "skipped"} for r in results), results
    assert sorted(physical_creations) == sorted(shared)
    assert {i for r in results for i in r.succeeded} == {e.id for e in composition.effects}
    actual = {(d.root, d.path, d.action, d.after.kind, d.after.sha256, d.after.target, d.after.mode) for d in net_delta(after_provision, snapshot(roots))}
    expected = {
        (name, e.destination.relative_to(root).as_posix(), e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode)
        for e in composition.effects
        for name, root in roots.items()
        if e.destination.is_relative_to(root)
    }
    assert actual == expected
    record_property(
        "shared_parent_receipt",
        json.dumps(
            {
                "effects": [asdict(e) for e in composition.effects],
                "results": [asdict(r) for r in results],
                "delta": [asdict(d) for d in net_delta(after_provision, snapshot(roots))],
                "provision_delta": [asdict(d) for d in net_delta(before, after_provision)],
                "mkdirs": sorted(map(str, physical_creations)),
            },
            default=str,
        ),
    )
    settled = snapshot(roots)
    assert all(r.outcome == "precondition_changed" for r in provider.apply_composition(composition, consent))
    assert_unchanged(settled, snapshot(roots))
    # New ordinary preparation after success must be a true no-op.
    from specify_cli.skills.command_installer import prepare_commands
    from specify_cli.skills.installer import assess_skill_installation
    from specify_cli.skills.registry import SkillRegistry
    from specify_cli.tool_surface.operations import AssessmentInputs

    ordinary = AssessmentInputs(commands.root, consent=consent)
    next_pair = assess_skill_installation(ordinary, SkillRegistry.from_package(), ("codex",), runtime=True, commands=True, command_agent_keys=[])
    next_commands = prepare_commands(ordinary, ("codex",), prune=True)
    repeat = provider.compose_installation(next_pair, next_commands)
    assert not repeat.effects
    with provider.preflight_composition(repeat, consent) as errors:
        assert not errors, errors
        assert all(r.outcome == "skipped" for r in provider.apply_composition(repeat, consent))
    assert_unchanged(settled, snapshot(roots))


@pytest.mark.parametrize("change", ["prestate", "premature", "parent-replaced", "mode", "content", "pointer", "consent"])
def test_shared_parent_composition_refuses_before_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    from dataclasses import replace
    import os
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    roots, before, provisioning, consent, installation, commands, provider = _shared_parent_case(
        tmp_path,
        monkeypatch,
        parents=True,
        pointer=True,
    )
    composition = provider.compose_installation(installation, commands)
    if change == "prestate":
        (roots["project"] / "unrelated").write_text("foreign")
    elif change == "premature":
        provisioning.apply()
    elif change == "parent-replaced":
        parent = roots["project"] / ".agents/skills"
        old = parent.stat()
        parent.rename(parent.with_name("retained"))
        parent.mkdir(mode=old.st_mode & 0o777)
        os.utime(parent, ns=(old.st_atime_ns, old.st_mtime_ns))
    poisoned = snapshot(roots)
    with provider.preflight_composition(composition, consent) as errors:
        if change in {"prestate", "premature", "parent-replaced"}:
            assert errors
        else:
            assert not errors, errors
            provisioning.apply()
            if change == "mode":
                (roots["project"] / ".agents/skills").chmod(0o700)
            elif change == "content":
                (roots["project"] / ".agents/skills/foreign").write_text("unknown")
            elif change == "pointer":
                config = roots["project"] / ".kittify/config.yaml"
                config.write_text(config.read_text() + "# unrelated pointer drift\n")
            poisoned = snapshot(roots)
        with _shared_write_observer() as writes:
            results = provider.apply_composition(composition, replace(consent, automatic=False) if change == "consent" else consent)
        assert all(r.outcome == "precondition_changed" for r in results), results
        assert not writes
        assert_unchanged(poisoned, snapshot(roots))
    with _shared_write_observer() as writes:
        transient = roots["project"] / "observer-control"
        transient.write_bytes(b"transient")
        transient.unlink()
    assert "open" in writes and "os.remove" in writes


@pytest.mark.parametrize("change", ["parent-replaced", "mode", "content", "unrelated"])
def test_shared_parent_composition_refuses_after_command_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    from specify_cli.skills import command_installer
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    roots, before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    composition = provider.compose_installation(installation, commands)
    original = command_installer.apply_commands
    poisoned: Snapshot | None = None

    def tampering_apply(assessment: OwnerAssessment, explicit_consent: ApplyConsent) -> OwnerApplyResult:
        nonlocal poisoned
        result = original(assessment, explicit_consent)
        assert result.outcome == "applied"
        parent = roots["project"] / ".agents/skills"
        if change == "parent-replaced":
            parent.rename(parent.with_name("retained"))
            parent.mkdir(mode=0o755)
        elif change == "mode":
            parent.chmod(0o700)
        elif change == "content":
            next(parent.glob("*/SKILL.md")).write_text("foreign")
        else:
            (roots["project"] / "foreign").write_text("unknown")
        poisoned = snapshot(roots)
        return result

    monkeypatch.setattr(command_installer, "apply_commands", tampering_apply)
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors
        provisioning.apply()
        results = provider.apply_composition(composition, consent)
    assert results[0].outcome == "applied"
    assert all(r.outcome == "precondition_changed" for r in results[1:]), results
    assert poisoned is not None
    assert_unchanged(poisoned, snapshot(roots))


def test_shared_parent_composition_mutated_receipt_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import installer

    # Restoring independent-owner absence checks makes the real success contract fail.
    monkeypatch.setattr(installer, "_command_parent_receipts", lambda assessment: {})
    with pytest.raises(AssertionError):
        test_shared_parent_composition_cold_real_owners(tmp_path, monkeypatch, lambda key, value: None, False, False, False)


def test_shared_parent_composition_rejects_unsupported_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import FileState
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    roots, before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    project = installation.project_skills
    shared = roots["project"] / ".agents"
    altered = replace(project, effects=tuple(replace(e, after=FileState("directory", mode=0o700)) if e.destination == shared else e for e in project.effects))
    with pytest.raises(ValueError, match="Unsupported shared skill effect"):
        provider.compose_installation(replace(installation, project_skills=altered), commands)
    with pytest.raises(ValueError, match="Complete commands"):
        provider.compose_installation(installation, replace(commands, complete=False))
    assert_unchanged(before, snapshot(roots))


@pytest.mark.parametrize("route", ["factory", "replace"])
def test_shared_parent_composition_rejects_error_bearing_complete_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import Diagnostic
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    roots, before, provisioning, consent, installation, commands, provider = _shared_parent_case(tmp_path, monkeypatch)
    composition = provider.compose_installation(installation, commands)
    invalid = replace(commands, diagnostics=(Diagnostic("required_input_failed", commands.owner_key, "error", "Known input failure"),))
    with _shared_write_observer() as writes, pytest.raises(ValueError, match="Complete commands"):
        if route == "factory":
            provider.compose_installation(installation, invalid)
        else:
            replace(composition, commands=invalid)
    assert not writes
    assert_unchanged(before, snapshot(roots))


@pytest.mark.parametrize("missing_parent", [False, True])
@pytest.mark.parametrize("damage", [None, "unapplied", "replace", "hardlink", "parent", "source"])
def test_absent_authority_paired_owners_require_canonical_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_parent: bool, damage: str | None,
) -> None:
    import os
    from specify_cli.skills.command_installer import prepare_commands
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    project.mkdir()
    _bind_consumer_home(home, monkeypatch)
    if not missing_parent:
        (project / ".kittify").mkdir()
    before = snapshot({"sandbox": tmp_path})
    consent = ApplyConsent(automatic=True)
    provisioning = prepare_mission_type_activations(project)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), projected=provisioning, consent=consent)
    installation = assess_skill_installation(inputs, SkillRegistry.from_package(), ("codex",))
    commands = prepare_commands(inputs, ("codex",))
    assert all(owner.complete for owner in (installation.global_assets, installation.project_skills, commands))
    provider = ManagedSkillsProvider()
    composition = provider.compose_installation(installation, commands)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    with provider.preflight_composition(composition, consent) as errors:
        assert not errors, errors
        if damage != "unapplied":
            assert provisioning.apply()
        target = project / ".kittify/config.yaml"
        if damage == "replace":
            alternate = project / "replacement"
            alternate.write_bytes(target.read_bytes())
            alternate.replace(target)
        elif damage == "hardlink":
            os.link(target, project / "alias")
        elif damage == "parent":
            target.parent.rename(project / "old")
            target.parent.mkdir()
            (project / "old/config.yaml").rename(target)
        elif damage == "source":
            target.write_bytes(target.read_bytes() + b"agents: {available: []}\n")
        results = provider.apply_composition(composition, consent)
    if damage is not None:
        assert any(result.outcome == "precondition_changed" for result in results), results
        # The paired global/project owners must both refuse before skill writes.
        assert not (project / ".agents/skills").exists()
        assert not (project / ".kittify/skills-manifest.json").exists()
    else:
        assert all(result.outcome in {"applied", "skipped"} for result in results), [
            (result.owner_key, result.diagnostics) for result in results
        ]
        assert (project / ".kittify/skills-manifest.json").exists()
        steady = snapshot({"sandbox": tmp_path})
        fresh = assess_skill_installation(
            AssessmentInputs(inputs.root, consent=consent), SkillRegistry.from_package(), ("codex",),
        )
        assert fresh.project_skills.complete and not fresh.project_skills.effects
        assert fresh.global_assets.complete and not fresh.global_assets.effects
        assert_unchanged(steady, snapshot({"sandbox": tmp_path}))
