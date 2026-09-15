"""Unit tests for ``tool_surface.providers.agent_profiles``."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository
from specify_cli.tool_surface.profiles.manifest import (
    PROJECTION_VERSION,
    ProfileManifest,
    manifest_path_for,
)
from specify_cli.tool_surface.profiles.projection import ProfileProjector
from specify_cli.tool_surface.model import SurfaceInstance
from specify_cli.tool_surface.operations import OwnerAssessment, OwnerApplyResult, PhysicalEffect
from tests.upgrade.preview_support.snapshot import Snapshot
from specify_cli.tool_surface.providers.agent_profiles import (
    AgentProfilesProvider,
    agent_profile_definition,
)
from specify_cli.tool_surface.providers.command_skills import (
    command_skill_definition,
)
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.status import (
    STATE_DRIFTED,
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    SurfaceStatus,
    _surface_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _assess_real(root: Path, tools: tuple[str, ...] = ("claude",)) -> OwnerAssessment:
    """Exercise the delivered guarded inventory and real registered owner."""
    from specify_cli.tool_surface.enums import ToolSurfaceKind
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces

    outcome = run_tool_surfaces(
        root,
        list(tools),
        kinds=[ToolSurfaceKind.AGENT_PROFILE],
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", root)),
    )
    assert len(outcome.assessments) == 1
    return outcome.assessments[0]


def _apply_real(assessment: OwnerAssessment) -> OwnerApplyResult:
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from specify_cli.tool_surface.service import build_providers

    return SurfaceRepairService(build_providers()).apply_assessments((assessment,), ApplyConsent(automatic=True))[0]


def _assert_exact_delta(assessment: OwnerAssessment, before: Snapshot, after: Snapshot) -> None:
    from tests.upgrade.preview_support.snapshot import net_delta

    actual = {(e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in net_delta(before, after)}
    planned = {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in assessment.effects}
    assert planned == actual


def test_real_profile_assessment_apply_exact_and_repeat_no_churn(tmp_path: Path) -> None:
    from dataclasses import replace
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path, ("claude", "codex", "vibe"))
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path}))
    manifest_effect = next(e for e in assessment.effects if e.path == ".kittify/agent_profiles_manifest.json")
    assert set(manifest_effect.logical_owners) == {"claude", "codex"}
    assert any(e.path.startswith(".claude/agents/") for e in assessment.effects)
    assert any(e.path.startswith(".codex/agents/") for e in assessment.effects)
    assert any(d.state == "not_applicable" for d in assessment.dispositions)
    result = _apply_real(assessment)
    assert result.outcome == "applied", result
    assert set(result.succeeded) == {e.id for e in assessment.effects}
    after = snapshot({"project": tmp_path})
    _assert_exact_delta(assessment, before, after)
    with pytest.raises(AssertionError):
        _assert_exact_delta(replace(assessment, effects=tuple(e for e in assessment.effects if e != manifest_effect)), before, after)
    for _ in range(2):
        repeated = _assess_real(tmp_path, ("claude", "codex", "vibe"))
        assert repeated.complete and not repeated.effects
        _apply_real(repeated)
        assert_unchanged(after, snapshot({"project": tmp_path}))


def test_real_profile_apply_windows_fchmod_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no ``os.fchmod``): applying a fresh profile still writes and chmods.

    Exercises ``_write_profile_effect``'s create branch (agent_profiles.py
    site #831), which previously called ``os.fchmod`` unconditionally.
    Before the fix, this raised ``AttributeError: module 'os' has no
    attribute 'fchmod'`` on a platform without the syscall.
    """
    import os
    import stat

    monkeypatch.delattr(os, "fchmod", raising=False)
    assessment = _assess_real(tmp_path, ("claude",))
    assert assessment.complete, assessment.diagnostics

    result = _apply_real(assessment)

    assert result.outcome == "applied", result
    file_effects = [e for e in assessment.effects if e.after.kind == "file" and e.action == "create"]
    assert file_effects
    for effect in file_effects:
        destination = tmp_path / effect.path
        assert destination.is_file()
        assert effect.after.mode is not None
        assert stat.S_IMODE(destination.stat().st_mode) == effect.after.mode


@pytest.mark.parametrize("changed", ["destination", "manifest", "source", "source_added", "source_removed", "config", "parent"])
def test_profile_whole_batch_recheck_refuses_changes(tmp_path: Path, changed: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    overlay = tmp_path / ".kittify/agent_profiles"
    overlay.mkdir(parents=True)
    from .test_agent_profiles_prune import _agent_yaml

    source = overlay / "project-reviewer.agent.yaml"
    source.write_text(_agent_yaml("project-reviewer", name="Project Reviewer", role="reviewer"), encoding="utf-8")
    assessment = _assess_real(tmp_path)
    assert assessment.complete and assessment.effects
    if changed == "destination":
        path = next(e.destination for e in assessment.effects if e.after.kind == "file" and ".claude/" in e.path)
        path.parent.mkdir(parents=True)
        path.write_text("racing user content", encoding="utf-8")
    elif changed == "manifest":
        manifest_path_for(tmp_path).write_text("{}", encoding="utf-8")
    elif changed == "source":
        source.write_text(source.read_text() + "# changed\n", encoding="utf-8")
    elif changed == "source_added":
        (overlay / "new-reviewer.agent.yaml").write_text(_agent_yaml("new-reviewer", name="New Reviewer", role="reviewer"))
    elif changed == "source_removed":
        source.unlink()
    elif changed == "config":
        (tmp_path / ".kittify/config.yaml").write_text("activated_agent_profiles: []\n", encoding="utf-8")
    else:
        sentinel = tmp_path / "sentinel"
        sentinel.mkdir()
        (tmp_path / ".claude").symlink_to(sentinel, target_is_directory=True)
    before = snapshot({"project": tmp_path})
    result = _apply_real(assessment)
    assert result.outcome == "precondition_changed", result
    assert not result.succeeded
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_missing_profile_manifest_safe_adoption_and_ambiguity(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    assert _apply_real(_assess_real(tmp_path)).outcome == "applied"
    manifest_path_for(tmp_path).unlink()
    unknown = next((tmp_path / ".claude/agents").glob("*.md"))
    unknown.write_text("# user-owned content\n", encoding="utf-8")
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert {e.path for e in assessment.effects} == {".kittify/agent_profiles_manifest.json"}
    assert any(d.path == unknown.relative_to(tmp_path).as_posix() and d.state == "preserve" for d in assessment.dispositions)
    assert _apply_real(assessment).outcome == "applied"
    assert unknown.read_text() == "# user-owned content\n"
    assert ProfileManifest.load(tmp_path).get_hash(unknown) is None
    assert not _assess_real(tmp_path).effects


@pytest.mark.parametrize(
    "path, content",
    [
        (".kittify/config.yaml", "[broken"),
        (".kittify/agent_profiles_manifest.json", "{"),
        (".kittify/agent_profiles_manifest.json", '{"schema_version":1,"entries":[{}]}'),
        (".kittify/agent_profiles_manifest.json", '{"schema_version":true,"entries":[]}'),
        (".kittify/agent_profiles/broken.agent.yaml", "[bad"),
    ],
)
def test_profile_unreadable_required_input_is_not_empty_success(tmp_path: Path, path: str, content: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_text(content, encoding="utf-8")
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert not assessment.complete and assessment.diagnostics
    assert not assessment.effects
    if path == ".kittify/config.yaml":
        assert all(d.code != "profile-source-invalid" for d in assessment.diagnostics)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize(
    "field", ["profile_urn", "source_layer", "tool_key", "output_path", "format", "file_hash", "source_path", "source_hash", "projection_version"]
)
def test_manifest_field_classes_block_real_assessment(tmp_path: Path, field: str) -> None:
    import json
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    provider = AgentProfilesProvider()
    instances = provider.expand(agent_profile_definition(), "claude", tmp_path)
    installed = provider.repair(tmp_path, [provider.probe(i) for i in instances])
    assert installed.repaired and not installed.failed
    path = manifest_path_for(tmp_path)
    original = path.read_bytes()
    healthy = _assess_real(tmp_path)
    assert healthy.complete and not healthy.effects
    required = field in {"profile_urn", "source_layer", "tool_key", "output_path", "format"}
    invalid: list[object] = [[], {}, True, 1.5]
    invalid.extend([None, "", 7] if required else ["1", "invalid"] if field == "projection_version" else [7])
    for value in invalid:
        payload = json.loads(original)
        payload["entries"][0][field] = value
        path.write_text(json.dumps(payload), encoding="utf-8")
        before = snapshot({"project": tmp_path})
        assessment = _assess_real(tmp_path)
        assert_unchanged(before, snapshot({"project": tmp_path}))
        assert not assessment.complete and not assessment.effects, (field, value, assessment)
        assert any(d.severity == "error" for d in assessment.diagnostics)
        assert not _apply_real(assessment).succeeded
        assert_unchanged(before, snapshot({"project": tmp_path}))
        with pytest.raises(ValueError):
            ProfileManifest.load(tmp_path)
    payload = json.loads(original)
    del payload["entries"][0][field]
    path.write_text(json.dumps(payload), encoding="utf-8")
    if required:
        assessment = _assess_real(tmp_path)
        assert not assessment.complete and not assessment.effects
    else:
        # Absent/nullable provenance and hash fields are legitimate legacy records.
        assert ProfileManifest.load(tmp_path).all_entries()
        assert _assess_real(tmp_path).complete
        payload["entries"][0][field] = None
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert ProfileManifest.load(tmp_path).all_entries()
        assert _assess_real(tmp_path).complete
    path.write_bytes(original)
    before = snapshot({"project": tmp_path})
    for _ in range(2):
        recovered = _assess_real(tmp_path)
        assert recovered.complete and not recovered.effects
        assert not _apply_real(recovered).succeeded
        assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("race", ["parent_link", "parent_file", "target", "node_refusal", "permission", "io", "healthy"])
def test_late_profile_failure_retains_actual_partial_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str) -> None:
    from dataclasses import replace
    import specify_cli.tool_surface.providers.agent_profiles as module
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    (sentinel / "custom").write_text("must survive\n")
    sentinel_before = snapshot({"sentinel": sentinel})
    assessment = _assess_real(tmp_path, ("claude", "codex"))
    assert assessment.complete and assessment.effects
    before = snapshot({"project": tmp_path})
    writer = module._write_profile_effect
    actual_success: list[str] = []
    refused: list[str] = []

    def late_failure(effect: PhysicalEffect, content: bytes | None) -> None:
        if effect.path.startswith(".codex/agents/") and effect.after.kind == "file" and not refused and race != "healthy":
            assert actual_success
            assert any((tmp_path / ".claude/agents").glob("*.md"))
            refused.append(effect.id)
            if race.startswith("parent_"):
                effect.destination.parent.rmdir()
                if race == "parent_link":
                    effect.destination.parent.symlink_to(sentinel, target_is_directory=True)
                else:
                    effect.destination.parent.write_text("racing parent\n")
            elif race == "target":
                effect.destination.write_text("racing occupant\n")
            elif race == "node_refusal":
                raise ValueError("late unsupported-node refusal")
            elif race == "permission":
                raise PermissionError("late permission refusal")
            else:
                raise OSError("late I/O refusal")
        writer(effect, content)
        actual_success.append(effect.id)

    monkeypatch.setattr(module, "_write_profile_effect", late_failure)
    result = _apply_real(assessment)
    assert actual_success
    assert set(result.succeeded) == set(actual_success)
    assert_unchanged(sentinel_before, snapshot({"sentinel": sentinel}))
    if race == "healthy":
        assert result.outcome == "applied" and not result.failed
        _assert_exact_delta(assessment, before, snapshot({"project": tmp_path}))
        after = snapshot({"project": tmp_path})
        for _ in range(2):
            repeated = _assess_real(tmp_path, ("claude", "codex"))
            assert repeated.complete and not repeated.effects
            assert not _apply_real(repeated).succeeded
            assert_unchanged(after, snapshot({"project": tmp_path}))
    else:
        assert result.outcome == "partial" and set(refused) <= set(result.failed)
        assert set(result.succeeded).isdisjoint(result.failed)
        assert set(result.succeeded) | set(result.failed) == {e.id for e in assessment.effects}
        assert any(d.code == "profile_apply_failed" for d in result.diagnostics)
        assert not manifest_path_for(tmp_path).exists()
        if race in {"permission", "io", "node_refusal"}:
            _assert_exact_delta(
                replace(assessment, effects=tuple(e for e in assessment.effects if e.id in result.succeeded)), before, snapshot({"project": tmp_path})
            )


@pytest.mark.parametrize("unsafe", ["absolute", "traversal", "unknown_identity"])
def test_legacy_manifest_strings_remain_non_authorizing(tmp_path: Path, unsafe: str) -> None:
    import json
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    assert _apply_real(_assess_real(tmp_path)).outcome == "applied"
    manifest = manifest_path_for(tmp_path)
    payload = json.loads(manifest.read_bytes())
    entry = payload["entries"][0]
    if unsafe == "unknown_identity":
        entry["profile_urn"] = "legacy:unknown"
    else:
        sentinel = tmp_path / "sentinel"
        sentinel.write_text("legacy path grants no authority\n")
        entry["output_path"] = str(sentinel) if unsafe == "absolute" else ".claude/../sentinel"
    # Legacy optional provenance may be absent; the string path is not corruption.
    for field in ("source_path", "source_hash", "projection_version"):
        entry.pop(field)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    loaded = ProfileManifest.load(tmp_path).all_entries()
    assert loaded
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert assessment.complete, assessment.diagnostics
    assert any(d.state == "preserve" for d in assessment.dispositions)
    assert not any(e.action == "delete" for e in assessment.effects)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert not _apply_real(assessment).failed
    assert all(e in ProfileManifest.load(tmp_path).all_entries() for e in loaded)


def test_profile_shared_aliases_coalesce_actual_outputs(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path, ("copilot", "vscode"))
    assert assessment.complete and assessment.effects, assessment.diagnostics
    native = [e for e in assessment.effects if e.after.kind == "file" and e.path.startswith(".github/agents/")]
    assert native
    assert len(native) == len({e.path for e in native})
    assert all(set(e.logical_owners) == {"copilot", "vscode"} for e in native)
    assert all({"copilot.agent_profile." + e.destination.name, "vscode.agent_profile." + e.destination.name} == set(e.surface_ids) for e in native)
    assert _apply_real(assessment).outcome == "applied"
    after = snapshot({"project": tmp_path})
    _assert_exact_delta(assessment, before, after)
    for tools in (("copilot",), ("vscode",), ("copilot", "vscode")):
        repeated = _assess_real(tmp_path, tools)
        assert repeated.complete and not repeated.effects
        _apply_real(repeated)
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("drift", [False, True])
def test_profile_source_update_distinguishes_installed_hash_from_drift(tmp_path: Path, drift: bool) -> None:
    from .test_agent_profiles_prune import _agent_yaml
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    source = tmp_path / ".kittify/agent_profiles/local-reviewer.agent.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(_agent_yaml("local-reviewer", name="Local Reviewer", role="reviewer"))
    assert _apply_real(_assess_real(tmp_path)).outcome == "applied"
    output = tmp_path / ".claude/agents/local-reviewer.md"
    original = next(e for e in ProfileManifest.load(tmp_path).all_entries() if e.output_path == output)
    source.write_text(_agent_yaml("local-reviewer", name="Changed Reviewer", role="reviewer"))
    if drift:
        output.write_text("# operator-owned edits\n")
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert assessment.complete
    assert_unchanged(before, snapshot({"project": tmp_path}))
    if drift:
        assert not assessment.effects
        assert any(d.state == "consent_required" and d.path == ".claude/agents/local-reviewer.md" for d in assessment.dispositions)
        _apply_real(assessment)
        assert original in ProfileManifest.load(tmp_path).all_entries()
        assert_unchanged(before, snapshot({"project": tmp_path}))
        output.write_text("# sabotage drift overwrite\n")
        with pytest.raises(AssertionError):
            assert_unchanged(before, snapshot({"project": tmp_path}))
    else:
        assert {e.path for e in assessment.effects} == {".claude/agents/local-reviewer.md", ".kittify/agent_profiles_manifest.json"}
        assert _apply_real(assessment).outcome == "applied"
        _assert_exact_delta(assessment, before, snapshot({"project": tmp_path}))
        current = next(e for e in ProfileManifest.load(tmp_path).all_entries() if e.output_path == output)
        assert current.source_hash != original.source_hash
        assert current.source_path == original.source_path == ".kittify/agent_profiles/local-reviewer.agent.yaml"
        assert current.projection_version == original.projection_version
        assert not _assess_real(tmp_path).effects


@pytest.mark.parametrize("activated", [None, ["orgzilla-org-analyst"], ["reviewer-renata"], []], ids=["absent", "include", "exclude", "empty"])
@pytest.mark.parametrize("corrupt", [True, False], ids=["corrupt", "healthy"])
def test_org_source_diagnostics_block_real_assessment_independent_of_admission(tmp_path: Path, activated: list[str] | None, corrupt: bool) -> None:
    from specify_cli.invocation.org_profiles import resolve_activated_org_profiles
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from .test_agent_profiles_prune import _write_config, _write_org_pack, _ORG_ANALYST_ID

    pack = _write_org_pack(tmp_path)
    bad = pack / "agent_profiles/broken.agent.yaml"
    if corrupt:
        bad.write_text("profile-id: broken\n: : : invalid yaml [\n", encoding="utf-8")
    _write_config(tmp_path, pack, activated=activated)
    resolved = resolve_activated_org_profiles(tmp_path)
    failures = resolved.skipped_profiles  # Read health before inspecting list-compatible admission.
    admitted = activated is None or _ORG_ANALYST_ID in activated
    assert [r.profile.profile_id for r in resolved] == ([_ORG_ANALYST_ID] if admitted else [])
    assert len(failures) == int(corrupt)
    if corrupt:
        assert failures[0].layer == "org" and Path(failures[0].path) == bad
        assert failures[0].error_summary
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    if corrupt:
        assert not assessment.complete, "canonical org source failure must block even falsey admission"
        assert not assessment.effects
        assert any(d.code == "profile-source-invalid" and d.severity == "error" and failures[0].error_summary in d.message for d in assessment.diagnostics)
        assert not _apply_real(assessment).succeeded
        assert_unchanged(before, snapshot({"project": tmp_path}))
        bad.unlink()
        before = snapshot({"project": tmp_path})
        assessment = _assess_real(tmp_path)
    assert assessment.complete and assessment.effects, assessment.diagnostics
    assert not any(d.code == "profile-source-invalid" for d in assessment.diagnostics)
    assert any(e.path == ".claude/agents/reviewer-renata.md" for e in assessment.effects)
    org_output = f".claude/agents/{_ORG_ANALYST_ID}.md"
    assert any(e.path == org_output for e in assessment.effects) == admitted
    assert _apply_real(assessment).outcome == "applied"
    after = snapshot({"project": tmp_path})
    _assert_exact_delta(assessment, before, after)
    repeated = _assess_real(tmp_path)
    assert repeated.complete and not repeated.effects, repeated.diagnostics
    _apply_real(repeated)
    assert_unchanged(after, snapshot({"project": tmp_path}))


def test_profile_missing_required_org_root_blocks(tmp_path: Path) -> None:
    from .test_agent_profiles_prune import _write_config
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    _write_config(tmp_path, tmp_path / "missing-pack", activated=None)
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert not assessment.complete and assessment.diagnostics
    assert not assessment.effects
    assert all(d.code != "profile-source-invalid" for d in assessment.diagnostics)
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_linked_required_source_parent_is_not_unobserved_input(tmp_path: Path) -> None:
    from .test_agent_profiles_prune import _agent_yaml
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    store = tmp_path / "source-store"
    store.mkdir()
    (store / "linked-reviewer.agent.yaml").write_text(_agent_yaml("linked-reviewer", name="Linked Reviewer", role="reviewer"))
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/agent_profiles").symlink_to(store, target_is_directory=True)
    before = snapshot({"project": tmp_path})
    assessment = _assess_real(tmp_path)
    assert not assessment.complete and assessment.diagnostics
    assert not assessment.effects
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_profile_manifest_save_failure_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assessment = _assess_real(tmp_path)
    manifest = next(e for e in assessment.effects if e.destination == manifest_path_for(tmp_path))

    def fail_save(self: ProfileManifest, prepared: bytes | None = None, *, exclusive: bool = False) -> None:
        raise OSError("injected manifest write refusal")

    monkeypatch.setattr(ProfileManifest, "save", fail_save)
    result = _apply_real(assessment)
    assert result.outcome == "partial"
    assert result.failed == (manifest.id,)
    assert manifest.id not in result.succeeded
    assert any(d.code == "profile_apply_failed" for d in result.diagnostics)
    assert not manifest_path_for(tmp_path).exists()


@pytest.mark.parametrize("tool", ["q", "amazon-q", "amazon-q-agent"])
def test_automatic_q_exception_with_zero_instances(tmp_path: Path, tool: str) -> None:
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    before = snapshot({"project": tmp_path})
    assessment = AgentProfilesProvider().assess(
        AssessmentInputs(OperationRoot("project", "project", tmp_path)),
        (),
        selections=(SurfaceSelection(tool, agent_profile_definition()),),
    )
    assert assessment.complete and not assessment.effects
    assert any(d.state == "not_applicable" and tool in d.reason for d in assessment.dispositions)
    _apply_real(assessment)
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_profile_preparation_write_observer_and_negative_controls(tmp_path: Path) -> None:
    import os
    import sys
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from tests.upgrade.preview_support.write_observer import EVENTS

    active = False
    attempts: list[str] = []

    def observe(event: str, args: tuple[object, ...]) -> None:
        if not active:
            return
        writing = event == "open" and (
            (isinstance(args[1], str) and any(flag in args[1] for flag in "wax+"))
            or (isinstance(args[2], int) and bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        )
        if event in EVENTS or writing:
            attempts.append(event)

    sys.addaudithook(observe)
    sync_setting = os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"]
    before = snapshot({"project": tmp_path})
    active = True
    try:
        assessment = _assess_real(tmp_path)
    finally:
        active = False
    assert assessment.complete and assessment.effects
    assert attempts == []
    assert_unchanged(before, snapshot({"project": tmp_path}))
    active = True
    try:
        transient = tmp_path / "transient"
        transient.write_text("removed", encoding="utf-8")
        transient.unlink()
    finally:
        active = False
    with pytest.raises(AssertionError):
        assert attempts == []
    assert {"open", "os.remove"} <= set(attempts)
    assert os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] == sync_setting


def test_profile_preparation_immutable_clock_and_owner_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    from dataclasses import FrozenInstanceError, replace
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from specify_cli.tool_surface.providers.agent_profiles import _prepared

    monkeypatch.setattr(time, "time", lambda: 1_000_000_000.0)
    first = _assess_real(tmp_path, ("claude", "codex"))
    payload = _prepared(first)
    assert isinstance(payload.projections, tuple) and isinstance(payload.projections[0].content, bytes)
    field = "content"
    with pytest.raises(FrozenInstanceError):
        setattr(payload.projections[0], field, b"changed")
    monkeypatch.setattr(time, "time", lambda: 2_000_000_000.0)
    second = _assess_real(tmp_path, ("claude", "codex"))
    assert first.effects == second.effects
    assert payload.contents == _prepared(second).contents
    assert _apply_real(first).outcome == "applied"
    for path, content in payload.contents:
        assert path.read_bytes() == content
    after = snapshot({"project": tmp_path})
    manifest = next(e for e in first.effects if e.destination == manifest_path_for(tmp_path))

    def owners(effect: PhysicalEffect) -> None:
        assert set(effect.logical_owners) == {"claude", "codex"}

    owners(manifest)
    with pytest.raises(AssertionError):
        owners(replace(manifest, logical_owners=("claude",)))
    manifest_path_for(tmp_path).write_bytes(manifest_path_for(tmp_path).read_bytes())
    with pytest.raises(AssertionError):
        assert_unchanged(after, snapshot({"project": tmp_path}))


def test_profile_later_write_failure_retains_truthful_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.tool_surface.providers.agent_profiles as module

    assessment = _assess_real(tmp_path)
    effects = sorted((e for e in assessment.effects if e.after.kind == "file" and e.destination != manifest_path_for(tmp_path)), key=lambda e: e.path)
    assert len(effects) > 2
    fail_path = effects[1].destination
    writer = module._write_profile_effect

    def fail_one(effect: PhysicalEffect, content: bytes | None) -> None:
        if effect.destination == fail_path:
            raise OSError("injected later profile write failure")
        writer(effect, content)

    monkeypatch.setattr(module, "_write_profile_effect", fail_one)
    result = _apply_real(assessment)
    assert result.outcome == "partial"
    assert effects[0].id in result.succeeded
    assert effects[1].id in result.failed
    assert effects[2].id in result.succeeded
    assert not fail_path.exists()
    assert not ProfileManifest.load(tmp_path).all_entries()


def test_profile_exclusive_creation_preserves_racing_occupant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.tool_surface.providers.agent_profiles as module

    assessment = _assess_real(tmp_path)
    victim = next(e for e in assessment.effects if e.after.kind == "file" and ".claude/" in e.path)
    writer = module._write_profile_effect

    def race(effect: PhysicalEffect, content: bytes | None) -> None:
        if effect == victim:
            effect.destination.write_bytes(b"racing occupant")
        writer(effect, content)

    monkeypatch.setattr(module, "_write_profile_effect", race)
    result = _apply_real(assessment)
    assert victim.id in result.failed and victim.id not in result.succeeded
    assert victim.destination.read_bytes() == b"racing occupant"


def _provider(tmp_path: Path) -> AgentProfilesProvider:
    repo = AgentProfileRepository()
    return AgentProfilesProvider(
        projector=ProfileProjector(repo),
        manifest=ProfileManifest.load(tmp_path),
    )


_DIAGNOSTICS_SENTINEL_SUFFIX = "<profile-diagnostics>"


def _real_profiles(instances: list[SurfaceInstance]) -> list[SurfaceInstance]:
    """Keep only real projected-profile instances.

    Drops the #1940 ``<profile-diagnostics>`` sentinel that ``expand`` appends to
    carry ``ProfileProjector.diagnose`` findings — it is not a projected profile
    file, so per-renderer path/suffix invariants must not assert over it.
    """
    return [i for i in instances if not (i.surface_id and i.surface_id.endswith(_DIAGNOSTICS_SENTINEL_SUFFIX))]


def test_provider_satisfies_reporting_protocol() -> None:
    assert isinstance(AgentProfilesProvider(), ReportingSurfaceProvider)
    assert AgentProfilesProvider().provider_key == "agent_profiles"


def test_can_handle_only_agent_profile() -> None:
    provider = AgentProfilesProvider()
    assert provider.can_handle(agent_profile_definition()) is True
    assert provider.can_handle(command_skill_definition()) is False


def test_expand_supported_tool_yields_profiles(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), "claude", tmp_path)
    # The trailing diagnostics sentinel is not a projected profile file; scope the
    # markdown-suffix invariant to the projected-profile instances.
    profile_instances = [i for i in instances if not (i.surface_id and i.surface_id.endswith(_DIAGNOSTICS_SENTINEL_SUFFIX))]
    assert len(profile_instances) > 1
    assert all(i.owner == "claude" for i in instances)
    assert all(i.path.suffix == ".md" for i in profile_instances)


# ---------------------------------------------------------------------------
# Capability matrix integration: codex now has a renderer (WP02)
# ---------------------------------------------------------------------------


def test_codex_expands_to_real_profiles(tmp_path: Path) -> None:
    """After WP02, codex has a real renderer and projects actual profiles."""
    provider = _provider(tmp_path)
    instances = _real_profiles(provider.expand(agent_profile_definition(), "codex", tmp_path))
    # Must yield at least one real profile instance (not a sentinel).
    assert len(instances) >= 1
    assert all(i.owner == "codex" for i in instances)
    # All paths should be inside .codex/agents/ with .toml suffix.
    assert all(i.path.suffix == ".toml" for i in instances)


# ---------------------------------------------------------------------------
# Capability matrix integration: not-applicable harnesses (WP03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "harness_key",
    ["windsurf", "cursor", "gemini", "qwen", "opencode", "kilocode", "vibe", "pi", "letta"],
)
def test_not_applicable_harnesses_yield_not_applicable_status(harness_key: str, tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), harness_key, tmp_path)
    assert len(instances) == 1
    status = provider.probe(instances[0])
    assert status.state == STATE_NOT_APPLICABLE
    assert status.findings[0].code == "profile-projection-unsupported"
    assert status.findings[0].severity == "info"
    assert status.findings[0].details.get("status") == "not_applicable"


def test_not_applicable_finding_includes_reason(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), "windsurf", tmp_path)
    status = provider.probe(instances[0])
    reason = status.findings[0].details.get("reason", "")
    assert reason, "not_applicable finding must include a non-empty reason"


def test_not_applicable_harness_is_skipped_by_repair(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    na_instance = provider.expand(agent_profile_definition(), "windsurf", tmp_path)[0]
    na_status = provider.probe(na_instance)
    assert na_status.state == STATE_NOT_APPLICABLE
    result = provider.repair(tmp_path, [na_status])
    assert result.repaired == ()
    assert len(result.skipped) == 1


# ---------------------------------------------------------------------------
# Research-gap harness (unknown / unassessed)
# ---------------------------------------------------------------------------


def test_research_gap_for_unknown_tool(tmp_path: Path) -> None:
    """A tool not in AI_CHOICES or the capability matrix yields research_gap."""
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), "unknown_tool_xyz", tmp_path)
    assert len(instances) == 1
    status = provider.probe(instances[0])
    assert status.state == STATE_NOT_APPLICABLE
    assert status.findings[0].code == "research-gap-surface"
    assert status.findings[0].severity == "info"


def test_agent_profiles_provider_codex_no_longer_research_gap(
    tmp_path: Path,
) -> None:
    """Codex now has a renderer and expands to real profile instances, not a research gap."""
    provider = _provider(tmp_path)
    instances = _real_profiles(provider.expand(agent_profile_definition(), "codex", tmp_path))
    # At least one profile projected (built-in profiles are always loaded).
    assert len(instances) > 0
    # All instances are owned by codex and point to .toml files.
    assert all(i.owner == "codex" for i in instances)
    assert all(i.path.suffix == ".toml" for i in instances)
    # None of the instances is the research-gap sentinel.
    assert all(str(i.path) != "<unsupported>" for i in instances)


# ---------------------------------------------------------------------------
# Augment renderer (WP03) — project-local, manifest-tracked
# ---------------------------------------------------------------------------


def test_augment_expands_to_real_profiles(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = _real_profiles(provider.expand(agent_profile_definition(), "auggie", tmp_path))
    assert len(instances) >= 1
    assert all(i.owner == "auggie" for i in instances)
    assert all(i.path.suffix == ".md" for i in instances)
    assert all(".augment/agents" in str(i.path) for i in instances)


def test_augment_repair_writes_file_and_records_manifest(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "auggie", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING

    result = provider.repair(tmp_path, [missing])
    assert result.failed == ()
    assert len(result.repaired) == 1
    assert instance.path.exists()
    reloaded = ProfileManifest.load(tmp_path)
    assert reloaded.get_hash(instance.path) is not None, "Augment profiles must be recorded in the project manifest"


# ---------------------------------------------------------------------------
# Amazon Q renderer (WP03) — user-global, NOT manifest-tracked
# ---------------------------------------------------------------------------


def test_amazon_q_expands_to_real_profiles(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = _real_profiles(provider.expand(agent_profile_definition(), "q", tmp_path))
    assert len(instances) >= 1
    assert all(i.owner == "q" for i in instances)
    assert all(i.path.suffix == ".json" for i in instances)


def test_amazon_q_output_path_is_user_global(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instances = _real_profiles(provider.expand(agent_profile_definition(), "q", tmp_path))
    home = Path.home()
    for instance in instances:
        assert str(instance.path).startswith(str(home)), f"Amazon Q path {instance.path} must be under home directory"


def test_amazon_q_repair_writes_file_but_not_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Amazon Q profiles are user-global and must NOT appear in the project manifest."""
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "q", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING

    result = provider.repair(tmp_path, [missing])
    assert result.failed == ()
    assert len(result.repaired) == 1
    assert instance.path.exists()
    # Check the user-global file was written.
    content = instance.path.read_text(encoding="utf-8")
    assert "name" in content  # JSON payload
    # Verify the project manifest does NOT record an Amazon Q entry.
    reloaded = ProfileManifest.load(tmp_path)
    assert reloaded.get_hash(instance.path) is None, "Amazon Q (user-global) profiles must NOT be recorded in the project manifest"


# ---------------------------------------------------------------------------
# Core existing probe tests
# ---------------------------------------------------------------------------


def test_probe_missing_is_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "claude", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "native-agent-profile-missing"
    assert status.findings[0].severity == "error"
    assert status.findings[0].repair_command is not None


def test_probe_present(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "claude", tmp_path)[0]
    instance.path.parent.mkdir(parents=True, exist_ok=True)
    instance.path.write_text("content", encoding="utf-8")
    # No manifest hash recorded -> present once the file exists.
    status = provider.probe(instance)
    assert status.state == STATE_PRESENT
    assert status.findings == ()


def test_probe_drift_is_warning(tmp_path: Path) -> None:
    from dataclasses import replace

    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "claude", tmp_path)[0]
    instance.path.parent.mkdir(parents=True, exist_ok=True)
    instance.path.write_text("real content", encoding="utf-8")
    drifted = replace(instance, exists=True, file_hash="deadbeef" * 8)
    status = provider.probe(drifted)
    assert status.state == STATE_DRIFTED
    assert status.findings[0].code == "native-agent-profile-drift"
    assert status.findings[0].severity == "warning"


def test_agent_profiles_provider_repair_writes_file(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "claude", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING

    result = provider.repair(tmp_path, [missing])
    assert result.failed == ()
    assert len(result.repaired) == 1
    assert instance.path.exists()
    assert "name:" in instance.path.read_text(encoding="utf-8")
    # Manifest now records a hash for the written file.
    assert manifest_path_for(tmp_path).exists()
    reloaded = ProfileManifest.load(tmp_path)
    assert reloaded.get_hash(instance.path) is not None


def test_agent_profiles_provider_repair_records_source_provenance(
    tmp_path: Path,
) -> None:
    provider = _provider(tmp_path)
    instance = _real_profiles(provider.expand(agent_profile_definition(), "claude", tmp_path))[0]
    missing = provider.probe(instance)

    result = provider.repair(tmp_path, [missing])

    assert result.failed == ()
    reloaded = ProfileManifest.load(tmp_path)
    entry = next(e for e in reloaded.all_entries() if e.output_path == instance.path)
    assert entry.source_path
    assert entry.source_hash
    assert entry.projection_version == PROJECTION_VERSION


def test_repair_dry_run_writes_nothing(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    instance = provider.expand(agent_profile_definition(), "claude", tmp_path)[0]
    missing = provider.probe(instance)
    result = provider.repair(tmp_path, [missing], dry_run=True)
    assert result.dry_run is True
    assert result.repaired == (_surface_id(missing.instance),)
    assert not instance.path.exists()


def test_repair_not_applicable_is_skipped(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    na_instance = provider.expand(agent_profile_definition(), "windsurf", tmp_path)[0]
    na_status = provider.probe(na_instance)
    result = provider.repair(tmp_path, [na_status])
    assert result.repaired == ()
    assert len(result.skipped) == 1


def test_repair_unsupported_status_provider_marks_skip(tmp_path: Path) -> None:
    """A status whose instance has no projection is skipped, not repaired."""
    provider = _provider(tmp_path)
    na_instance = provider.expand(agent_profile_definition(), "windsurf", tmp_path)[0]
    # Force a non-applicable status object through repair to exercise the skip
    # branch deterministically.
    status = SurfaceStatus(instance=na_instance, state=STATE_NOT_APPLICABLE)
    result = provider.repair(tmp_path, [status])
    assert result.repaired == ()
    assert _surface_id(na_instance) in result.skipped


def test_expand_appends_diagnostics_instance_for_supported_tool(
    tmp_path: Path,
) -> None:
    """A supported tool's expansion includes the diagnostics sentinel."""
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), "claude", tmp_path)
    diagnostics = [i for i in instances if i.surface_id and i.surface_id.endswith(_DIAGNOSTICS_SENTINEL_SUFFIX)]
    assert len(diagnostics) == 1
    assert diagnostics[0].owner == "claude"


def test_probe_diagnostics_instance_emits_profile_finding_codes(
    tmp_path: Path,
) -> None:
    """Probing the diagnostics sentinel surfaces ProfileProjector.diagnose codes.

    The built-in profile repository ships at least one sentinel profile, so
    ``profile-sentinel-skipped`` (info) is emitted unconditionally for a
    supported tool -- proving the provider invokes ``diagnose`` rather than
    leaving it dead code.
    """
    provider = _provider(tmp_path)
    instances = provider.expand(agent_profile_definition(), "claude", tmp_path)
    diagnostics = next(i for i in instances if i.surface_id and i.surface_id.endswith(_DIAGNOSTICS_SENTINEL_SUFFIX))
    status = provider.probe(diagnostics)
    assert status.state == STATE_NOT_APPLICABLE
    codes = {f.code for f in status.findings}
    assert "profile-sentinel-skipped" in codes
    sentinel_findings = [f for f in status.findings if f.code == "profile-sentinel-skipped"]
    assert sentinel_findings
    assert all(f.severity == "info" for f in sentinel_findings)


def test_provider_invokes_projector_diagnose() -> None:
    """Guard: the provider source actually calls ``projector.diagnose``.

    A grep-level assertion that catches a regression where the wiring is removed
    and ``diagnose`` reverts to dead code (the cycle-1 rejection condition).
    """
    import specify_cli.tool_surface.providers.agent_profiles as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "projector.diagnose(" in source


def test_diagnose_code_reaches_doctor_tool_surfaces_json(tmp_path: Path) -> None:
    """End-to-end: ``run_tool_surfaces`` (the doctor CLI delegate) surfaces a
    profile diagnostic code in its JSON ``findings`` for ``--kind agent-profile``.

    This exercises the full live service assembly the ``doctor tool-surfaces``
    command uses (build_providers -> build_registry -> SurfacePlanBuilder ->
    SurfaceStatusService.collect), not ``diagnose`` in isolation, satisfying the
    WP02 DoD that the new codes reach ``doctor tool-surfaces --json`` output.
    """
    from specify_cli.tool_surface.service import (
        run_tool_surfaces,
        surface_kind_from_token,
    )

    outcome = run_tool_surfaces(
        tmp_path,
        ["claude"],
        kinds=[surface_kind_from_token("agent-profile")],
    )
    # The assembled report is the object the CLI serializes to ``--json``.
    report_codes = {finding.code for finding in outcome.report.findings}
    assert "profile-sentinel-skipped" in report_codes
    # And it survives JSON serialization into the ``findings`` payload the
    # operator sees from ``doctor tool-surfaces --kind agent-profile --json``.
    payload = outcome.to_json()
    findings = payload["findings"]
    assert isinstance(findings, list)
    json_codes = {finding["code"] for finding in findings}
    assert "profile-sentinel-skipped" in json_codes
