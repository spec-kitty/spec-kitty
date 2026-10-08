"""R8 — projection ``--fix`` prunes de-activated/orphaned projected artifacts.

Debbie's finding: ``doctor tool-surfaces --kind agent-profile --fix`` projected
org/agent files but never removed a stale ``.claude/agents/<id>.md`` (or its
manifest entry) once a profile was de-activated. The in-memory projection set
shrank, but disk + manifest kept the orphan.

This drives the real provider (no injected projector, so projection applies the
charter activation gate via ``default_profile_repository``) over a real-format
org pack: project an org agent with ``--fix``, then de-activate it and re-run
``--fix``. The orphaned file AND its manifest entry must be gone, while a
still-projected built-in profile (and its entry) is untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.tool_surface.profiles.manifest import ProfileManifest
from specify_cli.tool_surface.providers.agent_profiles import (
    AgentProfilesProvider,
    agent_profile_definition,
)

pytestmark = pytest.mark.fast

_PACK_NAME = "orgzilla-governance-pack"
_ORG_ANALYST_ID = "orgzilla-org-analyst"
# A real built-in projected (ungated by projection) in both regimes; it is the
# "still-activated/unrelated" control that must NOT be pruned.
_UNRELATED_BUILTIN_ID = "reviewer-renata"
_TOOL_KEY = "claude"


def _agent_yaml(profile_id: str, *, name: str, role: str) -> str:
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Org-pack profile for prune fixtures\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Organisation-provided analyst used to verify prune-on-deactivation.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Organisation-specific evidence-provenance analysis.\n"
        "  avoidance-boundary: unrelated work\n"
    )


def _write_org_pack(repo_root: Path) -> Path:
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_ORG_ANALYST_ID}.agent.yaml").write_text(
        _agent_yaml(_ORG_ANALYST_ID, name="Orgzilla Org Analyst", role="researcher"),
        encoding="utf-8",
    )
    return pack_root


def _write_config(repo_root: Path, pack_root: Path, *, activated: list[str] | None) -> None:
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
    }
    if activated is not None:
        data["activated_agent_profiles"] = activated
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _run_fix(repo_root: Path) -> None:
    """Drive the provider's expand -> probe -> repair (``--fix``) cycle."""
    provider = AgentProfilesProvider()
    definition = agent_profile_definition()
    instances = provider.expand(definition, _TOOL_KEY, repo_root)
    statuses = [provider.probe(instance) for instance in instances]
    provider.repair(repo_root, statuses, dry_run=False)


def _manifest_output_names(repo_root: Path) -> set[str]:
    manifest = ProfileManifest.load(repo_root)
    return {entry.output_path.name for entry in manifest.all_entries()}


def test_fix_prunes_deactivated_profile_file_and_manifest_entry(tmp_path: Path) -> None:
    """De-activating an org agent and re-running ``--fix`` removes its orphan."""
    pack_root = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack_root, activated=None)

    _run_fix(tmp_path)

    org_file = tmp_path / ".claude" / "agents" / f"{_ORG_ANALYST_ID}.md"
    unrelated_file = tmp_path / ".claude" / "agents" / f"{_UNRELATED_BUILTIN_ID}.md"
    assert org_file.exists(), "the admitted org agent must be projected to disk"
    assert unrelated_file.exists()
    names = _manifest_output_names(tmp_path)
    assert f"{_ORG_ANALYST_ID}.md" in names
    assert f"{_UNRELATED_BUILTIN_ID}.md" in names

    # De-activate the org agent (activate only the unrelated built-in).
    _write_config(tmp_path, pack_root, activated=[_UNRELATED_BUILTIN_ID])

    _run_fix(tmp_path)

    # The orphaned file AND its manifest entry are gone.
    assert not org_file.exists(), "the de-activated org agent file must be pruned"
    names_after = _manifest_output_names(tmp_path)
    assert f"{_ORG_ANALYST_ID}.md" not in names_after, "the de-activated org agent manifest entry must be dropped"
    # The still-projected built-in (and its entry) is untouched.
    assert unrelated_file.exists()
    assert f"{_UNRELATED_BUILTIN_ID}.md" in names_after


def test_fix_does_not_prune_unrelated_user_file(tmp_path: Path) -> None:
    """A user-authored ``.claude/agents`` file not in the manifest is never pruned."""
    pack_root = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack_root, activated=None)
    _run_fix(tmp_path)

    # Seed an unrelated user file the projector never wrote / tracked.
    user_file = tmp_path / ".claude" / "agents" / "my-handwritten-agent.md"
    user_file.write_text("# hand-authored, not managed by spec-kitty\n", encoding="utf-8")

    # De-activate the org agent and re-run --fix (triggers a prune pass).
    _write_config(tmp_path, pack_root, activated=[_UNRELATED_BUILTIN_ID])
    _run_fix(tmp_path)

    assert user_file.exists(), "untracked user files must never be pruned"


def test_fix_preserves_edited_orphan_and_discloses_drift(tmp_path: Path) -> None:
    """T029: existing repair must preserve edited, formerly admitted content."""
    from tests.upgrade.preview_support.snapshot import snapshot

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    _run_fix(tmp_path)
    orphan = tmp_path / ".claude/agents" / f"{_ORG_ANALYST_ID}.md"
    orphan.write_text("# Operator customization\n", encoding="utf-8")
    orphan.chmod(0o640)
    custom = orphan.parent / "handwritten.md"
    custom.write_text("untouched\n", encoding="utf-8")
    manifest_entry = next(e for e in ProfileManifest.load(tmp_path).all_entries() if e.output_path == orphan)
    _write_config(tmp_path, pack, activated=[_UNRELATED_BUILTIN_ID])
    provider = AgentProfilesProvider()
    instances = provider.expand(agent_profile_definition(), _TOOL_KEY, tmp_path)
    assert orphan not in {i.path for i in instances}
    before = snapshot({"project": tmp_path})
    result = provider.repair(tmp_path, [provider.probe(i) for i in instances])
    after = snapshot({"project": tmp_path})
    key = ("project", orphan.relative_to(tmp_path).as_posix())
    assert after.get(key) == before[key], "edited managed orphan must survive repair unchanged"
    assert manifest_entry in ProfileManifest.load(tmp_path).all_entries()
    assert after[("project", custom.relative_to(tmp_path).as_posix())] == before[("project", custom.relative_to(tmp_path).as_posix())]
    assert any("drift" in message.lower() for message in result.failed)


@pytest.mark.parametrize(
    "installed_tools, selected_tools",
    [
        (("copilot", "vscode"), ("copilot", "vscode")),
        (("vscode", "copilot"), ("vscode", "copilot")),
        (("copilot",), ("copilot",)),
        (("vscode",), ("vscode",)),
        (("copilot",), ("vscode",)),
        (("vscode",), ("copilot",)),
    ],
)
@pytest.mark.parametrize("absent", [False, True])
def test_shared_alias_orphan_owners_and_excluded_record(
    tmp_path: Path,
    installed_tools: tuple[str, ...],
    selected_tools: tuple[str, ...],
    absent: bool,
) -> None:
    from dataclasses import replace
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from .test_agent_profiles import _assess_real, _apply_real, _assert_exact_delta

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    created = _assess_real(tmp_path, installed_tools)
    assert created.complete and created.effects
    org_effect = next(e for e in created.effects if _ORG_ANALYST_ID in e.path)
    assert set(org_effect.logical_owners) == set(installed_tools)
    assert _apply_real(created).outcome == "applied"
    path = org_effect.destination
    recorded = next(e for e in ProfileManifest.load(tmp_path).all_entries() if e.output_path == path)
    if absent:
        path.unlink()
    _write_config(tmp_path, pack, activated=[])
    before = snapshot({"project": tmp_path})
    assessed = _assess_real(tmp_path, selected_tools)
    assert assessed.complete
    assert_unchanged(before, snapshot({"project": tmp_path}))
    retained = recorded.tool_key not in selected_tools
    deletes = tuple(e for e in assessed.effects if e.action == "delete")
    assert len(deletes) == int(not retained and not absent)
    assert _apply_real(assessed).outcome == ("skipped" if retained else "applied")
    after = snapshot({"project": tmp_path})
    _assert_exact_delta(assessed, before, after)
    assert (recorded in ProfileManifest.load(tmp_path).all_entries()) == retained
    if retained:
        assert not assessed.effects
        assert_unchanged(before, after)
    else:
        assert not path.exists()
        manifest_effect = next(e for e in assessed.effects if e.path.endswith("agent_profiles_manifest.json"))
        if deletes:
            deletion = deletes[0]
            expected_ids = {f"{tool}.agent_profile.{path.name}" for tool in selected_tools}
            assert set(deletion.logical_owners) == set(selected_tools)
            assert set(deletion.surface_ids) == expected_ids
            with pytest.raises(AssertionError):
                _assert_exact_delta(replace(assessed, effects=tuple(e for e in assessed.effects if e != deletion)), before, after)
            if len(selected_tools) > 1:
                with pytest.raises(AssertionError):
                    assert set(replace(deletion, logical_owners=deletion.logical_owners[:1]).logical_owners) == set(selected_tools)
        assert set(selected_tools) <= set(manifest_effect.logical_owners)
    for _ in range(2):
        repeated = _assess_real(tmp_path, selected_tools)
        assert repeated.complete and not repeated.effects
        assert not _apply_real(repeated).succeeded
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("recorded_tool", ["copilot", "vscode"])
def test_shared_alias_disabled_recorded_owner_is_retained(tmp_path: Path, recorded_tool: str) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.enums import ActivationMode
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from .test_agent_profiles import _assess_real, _apply_real

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    assert _apply_real(_assess_real(tmp_path, (recorded_tool,))).outcome == "applied"
    original = ProfileManifest.load(tmp_path).all_entries()
    _write_config(tmp_path, pack, activated=[])
    before = snapshot({"project": tmp_path})
    definition = agent_profile_definition()
    selections = tuple(
        SurfaceSelection(tool, replace(definition, activation_mode=ActivationMode.DISABLED) if tool == recorded_tool else definition)
        for tool in ("copilot", "vscode")
    )
    for _ in range(2):
        assessment = AgentProfilesProvider().assess(AssessmentInputs(OperationRoot("project", "project", tmp_path)), (), selections=selections)
        assert assessment.complete and not assessment.effects
        assert not _apply_real(assessment).succeeded
        assert ProfileManifest.load(tmp_path).all_entries() == original
        assert_unchanged(before, snapshot({"project": tmp_path}))


def test_failed_orphan_unlink_preserves_ownership(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.tool_surface.providers.agent_profiles as module
    from specify_cli.tool_surface.operations import PhysicalEffect
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from .test_agent_profiles import _assess_real, _apply_real

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    _run_fix(tmp_path)
    _write_config(tmp_path, pack, activated=[_UNRELATED_BUILTIN_ID])
    assessment = _assess_real(tmp_path)
    deletion = next(e for e in assessment.effects if e.action == "delete")
    original = ProfileManifest.load(tmp_path).all_entries()
    writer = module._write_profile_effect

    def refuse_unlink(effect: PhysicalEffect, content: bytes | None) -> None:
        if effect.id == deletion.id:
            raise PermissionError("injected orphan unlink refusal")
        writer(effect, content)

    monkeypatch.setattr(module, "_write_profile_effect", refuse_unlink)
    before = snapshot({"project": tmp_path})
    result = _apply_real(assessment)
    assert result.outcome == "failed" and deletion.id in result.failed
    assert not result.succeeded
    assert ProfileManifest.load(tmp_path).all_entries() == original
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_existing_dry_run_omits_statusless_orphan_effects(tmp_path: Path) -> None:
    """Historical reporting seam omits physical prune/manifest effects (WP10)."""
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    _run_fix(tmp_path)
    _write_config(tmp_path, pack, activated=[_UNRELATED_BUILTIN_ID])
    provider = AgentProfilesProvider()
    instances = provider.expand(agent_profile_definition(), _TOOL_KEY, tmp_path)
    statuses = [provider.probe(i) for i in instances]
    before = snapshot({"project": tmp_path})
    preview = provider.repair(tmp_path, statuses, dry_run=True)
    assert preview.repaired == ()
    assert_unchanged(before, snapshot({"project": tmp_path}))
    provider.repair(tmp_path, statuses)
    delta = net_delta(before, snapshot({"project": tmp_path}))
    paths = {(e.path, e.action) for e in delta}
    assert (f".claude/agents/{_ORG_ANALYST_ID}.md", "delete") in paths
    assert (".kittify/agent_profiles_manifest.json", "update") in paths
    print("original ID-only preview:", preview, "independent physical delta:", delta)


@pytest.mark.parametrize("condition", ["unchanged", "absent", "edited", "dangling", "disabled", "unselected", "legacy_escape", "q"])
def test_statusless_prune_preserves_policy_and_sentinels(tmp_path: Path, condition: str) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.enums import ActivationMode
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from .test_agent_profiles import _apply_real, _assert_exact_delta

    pack = _write_org_pack(tmp_path)
    _write_config(tmp_path, pack, activated=None)
    _run_fix(tmp_path)
    orphan = tmp_path / ".claude/agents" / f"{_ORG_ANALYST_ID}.md"
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("outside ownership", encoding="utf-8")
    custom = orphan.parent / "spec-kitty.custom"
    custom.symlink_to(sentinel)
    manifest = ProfileManifest.load(tmp_path)
    entry = next(e for e in manifest.all_entries() if e.output_path == orphan)
    definition = agent_profile_definition()
    tool = "claude"
    if condition == "absent":
        orphan.unlink()
    elif condition == "edited":
        orphan.write_text("operator changes", encoding="utf-8")
    elif condition == "dangling":
        orphan.unlink()
        orphan.symlink_to(tmp_path / "absent-target")
    elif condition == "disabled":
        definition = replace(definition, activation_mode=ActivationMode.DISABLED)
    elif condition == "unselected":
        tool = "vibe"
    elif condition in {"legacy_escape", "q"}:
        manifest.remove(orphan)
        escaped = replace(entry, output_path=sentinel)
        if condition == "q":
            escaped = replace(escaped, tool_key="q", format="amazon-q-agent")
        manifest.record(escaped)
        manifest.save()
    _write_config(tmp_path, pack, activated=[_UNRELATED_BUILTIN_ID])
    before = snapshot({"project": tmp_path})
    assessment = AgentProfilesProvider().assess(
        AssessmentInputs(OperationRoot("project", "project", tmp_path)),
        (),
        selections=(SurfaceSelection(tool, definition),),
    )
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path}))
    deletes = [e for e in assessment.effects if e.action == "delete"]
    assert bool(deletes) == (condition == "unchanged")
    if condition == "unchanged":
        assert deletes[0].destination == orphan
    result = _apply_real(assessment)
    assert not result.failed, result
    after = snapshot({"project": tmp_path})
    _assert_exact_delta(assessment, before, after)
    assert sentinel.read_text() == "outside ownership"
    assert custom.is_symlink()
    if condition in {"edited", "dangling", "disabled", "unselected"}:
        assert entry in ProfileManifest.load(tmp_path).all_entries()
        assert_unchanged(before, after)
    if deletes:
        with pytest.raises(AssertionError):
            _assert_exact_delta(replace(assessment, effects=tuple(e for e in assessment.effects if e not in deletes)), before, after)
