"""Unit tests for ``tool_surface.providers.session_presence``."""

from __future__ import annotations

from pathlib import Path

from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.providers.command_skills import (
    command_skill_definition,
)
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.providers.session_presence import (
    SessionPresenceProvider,
    context_file_definition,
    hook_definition,
    rule_definition,
)
from specify_cli.session_presence.content import (
    SECTION_OPEN,
    SessionPresenceContent,
)
from specify_cli.tool_surface.status import (
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
    STATE_STALE,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    "raw",
    ["[]", "false", "0", "''"]
    + [f"{section}: {value}" for section in ("agents", "tools") for value in ("[]", "false", "0", "''")]
    + [f"agents: {value}\ntools: {{available: [vibe]}}" for value in ("[]", "false", "0", "''")]
    + [f"agents: {empty}\ntools: {value}" for empty in ("null", "{}") for value in ("[]", "false", "0", "''")]
    + ["agents: {available: [1]}", "agents: {available: [{}]}"],
)
def test_wp07_cycle2_integrated_config_refuses_without_writes(tmp_path: Path, raw: str) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces, build_providers
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text(raw + "\n")
    before = snapshot({"project": tmp_path})
    consent = ApplyConsent(automatic=True)
    assessed = run_tool_surfaces(
        tmp_path,
        ["vibe"],
        kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE],
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent),
    )
    assert {a.owner_key for a in assessed.assessments} == {"native_config", "session_presence"}
    assert all(not a.complete and not a.effects and a.diagnostics for a in assessed.assessments)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    results = SurfaceRepairService(build_providers()).apply_assessments(assessed.assessments, consent)
    assert all(not result.succeeded for result in results)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize(
    ("raw", "repair"),
    [
        (None, True),  # An explicitly selected surface still works without a config file.
        ("", False),
        ("# comment", False),
        ("null", False),
        ("{}", False),
        ("agents: null", False),
        ("agents: {}", False),
        ("agents: {available: []}\ntools: {available: [vibe]}", False),
        ("agents: {available: [vibe]}", True),
        ("tools: {available: [vibe]}", True),
        ("agents: null\ntools: {available: [vibe]}", True),
        ("agents: {}\ntools: {available: [vibe]}", True),
        ("agents: {available: [claude]}\ntools: {available: [vibe]}", False),
        ("agents: {available: [vibe]}\ntools: []", True),
        ("agents: {custom: true}\ntools: {available: [vibe]}", False),
        ("tools: {available: vibe}", True),
    ],
)
def test_wp07_cycle2_integrated_config_preserves_selection_policy(tmp_path: Path, raw: str | None, repair: bool) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces, build_providers
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    if raw is not None:
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify/config.yaml").write_text(raw + "\n")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent)
    before = snapshot({"project": tmp_path})
    assessed = run_tool_surfaces(tmp_path, ["vibe"], kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE], assessment_inputs=inputs)
    assert len(assessed.assessments) == 2 and all(a.complete for a in assessed.assessments)
    assert all(bool(a.effects) == repair for a in assessed.assessments)
    if not repair:
        assert all(a.dispositions and all(d.state == "not_applicable" for d in a.dispositions) for a in assessed.assessments)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    results = SurfaceRepairService(build_providers()).apply_assessments(assessed.assessments, consent)
    assert all(not result.failed for result in results)
    after = snapshot({"project": tmp_path})
    assert {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for a in assessed.assessments for e in a.effects} == {
        (e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in net_delta(before, after)
    }
    if not repair:
        assert_unchanged(before, after)
    again = run_tool_surfaces(tmp_path, ["vibe"], kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE], assessment_inputs=inputs)
    assert all(a.complete and not a.effects for a in again.assessments)
    SurfaceRepairService(build_providers()).apply_assessments(again.assessments, consent)
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("existing_parent", [False, True])
def test_wp07_cycle2_combined_native_session_dispatch(tmp_path: Path, existing_parent: bool) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces, build_providers
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("agents:\n  available: [vibe]\n")
    if existing_parent:
        (tmp_path / ".vibe").mkdir()
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent)
    before = snapshot({"project": tmp_path})
    assessed = run_tool_surfaces(tmp_path, ["vibe"], kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE], assessment_inputs=inputs)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert {a.owner_key for a in assessed.assessments} == {"native_config", "session_presence"}
    assert all(a.complete and a.effects for a in assessed.assessments)
    results = SurfaceRepairService(build_providers()).apply_assessments(assessed.assessments, consent)
    assert all(r.outcome == "applied" for r in results), results
    after = snapshot({"project": tmp_path})
    assert {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for a in assessed.assessments for e in a.effects} == {
        (e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in net_delta(before, after)
    }
    assert (tmp_path / "AGENTS.md").is_file() and (tmp_path / ".vibe/config.toml").is_file()
    for _ in range(2):
        again = run_tool_surfaces(tmp_path, ["vibe"], kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE], assessment_inputs=inputs)
        assert all(a.complete and not a.effects for a in again.assessments)
        SurfaceRepairService(build_providers()).apply_assessments(again.assessments, consent)
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("change", ["root_inode", "root_mode", "root_symlink", "config_bytes", "config_mtime", "target"])
def test_wp07_cycle2_native_success_does_not_hide_external_race(tmp_path: Path, change: str) -> None:
    import os
    import shutil
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces, build_providers
    from specify_cli.tool_surface.repair import SurfaceRepairService
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    config = root / ".kittify/config.yaml"
    config.write_text("agents:\n  available: [vibe]\n")
    consent = ApplyConsent(automatic=True)
    assessed = run_tool_surfaces(
        root,
        ["vibe"],
        kinds=[ToolSurfaceKind.NATIVE_CONFIG, ToolSurfaceKind.CONTEXT_FILE],
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", root), consent=consent),
    )
    service = SurfaceRepairService(build_providers())
    native = tuple(a for a in assessed.assessments if a.owner_key == "native_config")
    session = tuple(a for a in assessed.assessments if a.owner_key == "session_presence")
    assert len(native) == len(session) == 1 and all(a.complete for a in assessed.assessments)
    assert service.apply_assessments(native, consent)[0].outcome == "applied"
    if change in {"root_inode", "root_symlink"}:
        previous = tmp_path / "previous"
        root.rename(previous)
        if change == "root_inode":
            shutil.copytree(previous, root, copy_function=shutil.copy2)
        else:
            root.symlink_to(previous, target_is_directory=True)
    elif change == "root_mode":
        root.chmod(root.stat().st_mode ^ 0o200)
    elif change == "config_bytes":
        config.write_text("agents:\n  available: [vibe]\ncustom: true\n")
    elif change == "config_mtime":
        info = config.stat()
        os.utime(config, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
    else:
        (root / "AGENTS.md").write_bytes(b"foreign late occupant\n")
    before = snapshot({"sandbox": tmp_path})
    result = service.apply_assessments(session, consent)[0]
    assert result.outcome == "precondition_changed" and not result.succeeded
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("policy", ["optional", "required", "research_gap"])
@pytest.mark.parametrize("owner", ["session", "native"])
def test_wp07_nonrepairable_policy_never_becomes_automatic(tmp_path: Path, policy: str, owner: str) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.enums import RequiredPolicy
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.model import SurfaceSelection
    from specify_cli.tool_surface.providers.native_config import NativeConfigProvider, native_config_definition
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    definition = native_config_definition() if owner == "native" else context_file_definition()
    definition = replace(definition, required_policy=RequiredPolicy(policy))
    provider = NativeConfigProvider() if owner == "native" else SessionPresenceProvider()
    before = snapshot({"project": tmp_path})
    result = provider.assess(AssessmentInputs(OperationRoot("project", "project", tmp_path)), (), selections=(SurfaceSelection("vibe", definition),))
    assert result.complete and not result.effects and result.dispositions
    assert all(d.state == "not_applicable" for d in result.dispositions)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("owner", ["native", "session"])
@pytest.mark.parametrize("stage", ["assess", "changed_precondition", "malformed_config"])
def test_wp07_assessment_has_no_transient_write_attempts(tmp_path: Path, owner: str, stage: str) -> None:
    import os
    import sys
    from tests.upgrade.preview_support.write_observer import EVENTS
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from tests.specify_cli.tool_surface.providers.test_native_config import _native_assessment
    from specify_cli.tool_surface.providers.native_config import NativeConfigProvider
    from specify_cli.tool_surface.operations import ApplyConsent

    (tmp_path / ".claude").mkdir()
    enabled = [False]
    attempts = []

    def deny(event, args):
        write_open = event == "open" and (
            isinstance(args[1], str)
            and any(c in args[1] for c in "wax+")
            or isinstance(args[2], int)
            and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        )
        if enabled[0] and (event in EVENTS or write_open):
            attempts.append(event)
            raise PermissionError("WP07 write observer")

    sys.addaudithook(deny)
    assess = _native_assessment if owner == "native" else _session_assessment
    prepared = None
    if stage == "malformed_config":
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify/config.yaml").write_bytes(b"[]\n")
    if stage == "changed_precondition":
        prepared = assess(tmp_path)
        assert prepared.complete and prepared.effects
        if owner == "native":
            (tmp_path / ".vibe").mkdir()
            (tmp_path / ".vibe/config.toml").write_text("changed = true\n")
        else:
            (tmp_path / ".claude/settings.json").write_text("{}\n")
    before = snapshot({"project": tmp_path})
    enabled[0] = True
    try:
        if prepared is None:
            assessment = assess(tmp_path)
            if stage == "malformed_config":
                assert not assessment.complete and assessment.diagnostics and not assessment.effects
            else:
                assert assessment.complete and assessment.effects
        else:
            provider = NativeConfigProvider() if owner == "native" else SessionPresenceProvider()
            result = provider.apply(prepared, ApplyConsent(automatic=True))
            assert result.outcome == "precondition_changed" and not result.succeeded
        assert not attempts
        with pytest.raises(PermissionError, match="WP07 write observer"):
            (tmp_path / "transient").write_bytes(b"control")
        assert attempts == ["open"]
    finally:
        enabled[0] = False
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_wp07_partial_io_reports_only_real_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    (tmp_path / ".claude").mkdir()
    assessment = _session_assessment(tmp_path)
    before = snapshot({"project": tmp_path})
    original = os.replace
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise OSError("WP07 second replacement fault")
        return original(*args, **kwargs)

    monkeypatch.setattr(os, "replace", fail_second)
    result = SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "partial" and len(result.succeeded) == 1 and len(result.failed) == 1
    delta = net_delta(before, snapshot({"project": tmp_path}))
    assert {e.path for e in delta} == {e.path for e in assessment.effects if e.id in result.succeeded}
    assert (tmp_path / ".claude/CLAUDE.md").is_file()
    assert not (tmp_path / ".claude/settings.json").exists()


def test_wp07_oracle_rejects_omitted_settings_and_parent_effects(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path, ("claude", "cursor"))
    result = SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "applied"
    actual = {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in net_delta(before, snapshot({"project": tmp_path}))}
    planned = {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in assessment.effects}
    assert actual == planned
    for omitted in (".claude/settings.json", ".cursor/rules"):
        assert any(e[0] == omitted for e in planned)
        with pytest.raises(AssertionError):
            assert actual == {e for e in planned if e[0] != omitted}


@pytest.mark.parametrize(
    "raw",
    [
        b"<!-- spec-kitty:orientation -->\n",
        b"<!-- /spec-kitty:orientation -->\n<!-- spec-kitty:orientation -->",
        b"<!-- spec-kitty:orientation --><!-- spec-kitty:orientation --><!-- /spec-kitty:orientation -->",
    ],
)
def test_wp07_bad_markers_are_explicit_refusals(tmp_path: Path, raw: bytes) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / "AGENTS.md").write_bytes(raw)
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path, ("codex",))
    assert not assessment.complete and assessment.diagnostics
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_wp07_session_disabled_and_missing_harness_are_inapplicable(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("agents:\n  available: []\n")
    assessment = _session_assessment(tmp_path, ("codex", "claude", "qwen"))
    assert assessment.complete and not assessment.effects
    assert len(assessment.dispositions) == 3
    assert all(d.state == "not_applicable" for d in assessment.dispositions)


@pytest.mark.parametrize("path", [".claude/CLAUDE.md", ".claude/settings.json", ".kittify/config.yaml"])
def test_wp07_directory_in_place_of_file_is_incomplete(tmp_path: Path, path: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / ".claude").mkdir()
    (tmp_path / path).mkdir(parents=True)
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path)
    assert not assessment.complete and assessment.diagnostics and not assessment.effects
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_wp07_disabled_existing_repair_never_claims_success(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("agents:\n  available: []\n")
    provider = SessionPresenceProvider()
    statuses = [provider.probe(i) for i in provider.expand(context_file_definition(), "codex", tmp_path)]
    result = provider.repair(tmp_path, statuses)
    assert not result.repaired and result.skipped
    assert not (tmp_path / "AGENTS.md").exists()


def test_wp07_apply_does_not_render_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.tool_surface.providers.session_presence import PreparedSessionBatch

    (tmp_path / ".claude").mkdir()
    assessment = _session_assessment(tmp_path)
    assert isinstance(assessment.prepared, PreparedSessionBatch)
    assert len(assessment.prepared.execution_artifacts) == 2
    expected = {member.path: member.content for _tool, member in assessment.prepared.files}

    def unavailable(_self):
        raise AssertionError("T2 must consume T1 bytes, not render again")

    monkeypatch.setattr(SessionPresenceContent, "render", unavailable)
    result = SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.succeeded and not result.failed
    assert {path: (tmp_path / path).read_bytes() for path in expected} == expected


def test_wp07_unavailable_required_content_is_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import PackageNotFoundError
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.model import SurfaceSelection

    def unavailable(_name):
        raise PackageNotFoundError("spec-kitty-cli")

    monkeypatch.setattr("importlib.metadata.version", unavailable)
    provider = SessionPresenceProvider()
    assessment = provider.assess(
        AssessmentInputs(OperationRoot("project", "project", tmp_path)), (), selections=(SurfaceSelection("codex", context_file_definition()),)
    )
    assert not assessment.complete and assessment.diagnostics and not assessment.effects


def test_wp07_existing_repair_refuses_malformed_sibling_before_orientation(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    target = tmp_path / ".claude/CLAUDE.md"
    _write_orientation(target, version="0.1.0")
    (target.parent / "settings.json").write_bytes(b'{"hooks":')
    provider = SessionPresenceProvider()
    statuses = [provider.probe(instance) for instance in provider.expand(context_file_definition(), "claude", tmp_path)]
    assert statuses[0].state == STATE_STALE
    before = snapshot({"project": tmp_path})
    result = provider.repair(tmp_path, statuses)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert result.failed
    assert not result.repaired


def _session_assessment(root: Path, tools: tuple[str, ...] = ("claude",), kinds=None):
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.model import SurfaceSelection

    definitions = kinds if kinds is not None else (context_file_definition(), hook_definition(), rule_definition())
    return SessionPresenceProvider().assess(
        AssessmentInputs(
            OperationRoot("project", "project", root),
            projected=SessionPresenceContent(_installed_version(), "fixed-project", "healthy", None),
            consent=ApplyConsent(automatic=True),
        ),
        (),
        selections=tuple(SurfaceSelection(tool, d) for tool in tools for d in definitions),
    )


@pytest.mark.parametrize("tools", [("claude",), ("cursor",), ("codex", "opencode", "vibe")])
def test_wp07_session_exact_batch_and_repeat(tmp_path: Path, tools: tuple[str, ...]) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    if tools == ("claude",):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude/CLAUDE.md").write_bytes(b"# foreign\r\n\r\n\r\n")
        (tmp_path / ".claude/settings.json").write_text(
            '{"permissions":{"allow":["Read"]},"hooks":{"Stop":[{"matcher":"custom","hooks":[{"type":"command","command":"spec-kitty session-stop --custom"}]}]}}'
        )
    if tools == ("cursor",):
        (tmp_path / ".cursor").mkdir()
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path, tools)
    assert assessment.complete, assessment.diagnostics
    assert assessment.effects
    assert_unchanged(before, snapshot({"project": tmp_path}))
    result = SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "applied", result
    after = snapshot({"project": tmp_path})
    assert {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in assessment.effects} == {
        (e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in net_delta(before, after)
    }
    if tools == ("claude",):
        import json

        assert (tmp_path / ".claude/CLAUDE.md").read_bytes().startswith(b"# foreign\r\n\r\n\r\n")
        settings = json.loads((tmp_path / ".claude/settings.json").read_bytes())
        assert settings["permissions"] == {"allow": ["Read"]}
        assert settings["hooks"]["Stop"][0] == {
            "matcher": "custom",
            "hooks": [{"type": "command", "command": "spec-kitty session-stop --custom"}],
        }
        assert len([e for e in assessment.effects if e.path.endswith("settings.json")]) == 1
    if len(tools) > 1:
        assert len(assessment.effects) == 1
        assert set(assessment.effects[0].logical_owners) == set(tools)
    for _ in range(2):
        again = _session_assessment(tmp_path, tools)
        assert again.complete and not again.effects
        SessionPresenceProvider().apply(again, ApplyConsent(automatic=True))
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("raw", [b'{"hooks":', b"[]", b'{"hooks":[]}', b'{"hooks":{"Stop":null}}', b'{"hooks":{"SessionStart":[{"hooks":"bad"}]}}'])
def test_wp07_session_required_settings_refusal(tmp_path: Path, raw: bytes) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    _write_orientation(tmp_path / ".claude/CLAUDE.md", version="0.1.0")
    (tmp_path / ".claude/settings.json").write_bytes(raw)
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path)
    assert not assessment.complete and assessment.diagnostics
    SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("change", ["last_target", "config", "parent", "mode", "mtime"])
def test_wp07_session_rechecks_all_siblings_before_first_write(tmp_path: Path, change: str) -> None:
    import os
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    root = tmp_path / "project"
    root.mkdir()
    (root / ".kittify").mkdir()
    config = root / ".kittify/config.yaml"
    config.write_text("agents:\n  available: [claude]\n")
    _write_orientation(root / ".claude/CLAUDE.md", version="0.1.0")
    settings = root / ".claude/settings.json"
    settings.write_text("{}\n")
    assessment = _session_assessment(root)
    assert assessment.complete and len(assessment.effects) == 2
    if change == "last_target":
        settings.write_text('{"foreign":1}')
    elif change == "config":
        config.write_text("agents:\n  available: []\n")
    elif change == "parent":
        (root / ".claude").rename(root / "retained")
        (root / ".claude").symlink_to(tmp_path, target_is_directory=True)
    elif change == "mode":
        settings.chmod(0o600)
    else:
        os.utime(settings, ns=(1_000_000_000, 1_000_000_000))
    before = snapshot({"sandbox": tmp_path})
    result = SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "precondition_changed", result
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_wp07_session_hook_selection_includes_orientation_sibling(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assessment = _session_assessment(tmp_path, kinds=(hook_definition(),))
    assert assessment.complete
    assert {e.path for e in assessment.effects} == {".claude/CLAUDE.md", ".claude/settings.json"}


def test_wp07_session_nonmatching_empty_selection_is_explicit(tmp_path: Path) -> None:
    assessment = _session_assessment(tmp_path, ("codex",), kinds=(hook_definition(),))
    assert assessment.complete and not assessment.effects
    assert assessment.dispositions[0].state == "not_applicable"


def test_wp07_session_unknown_whole_file_and_edited_block_survive(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot
    from specify_cli.tool_surface.operations import ApplyConsent

    target = tmp_path / ".cursor/rules/spec-kitty.mdc"
    target.parent.mkdir(parents=True)
    target.write_text("# personal rules\n")
    before = snapshot({"project": tmp_path})
    assessment = _session_assessment(tmp_path, ("cursor",))
    assert assessment.complete and not assessment.effects
    assert assessment.dispositions[0].state == "preserve"
    SessionPresenceProvider().apply(assessment, ApplyConsent(automatic=True))
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_wp07_session_actual_service_and_dispatcher(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces, build_providers
    from specify_cli.tool_surface.repair import SurfaceRepairService

    (tmp_path / ".claude").mkdir()
    consent = ApplyConsent(automatic=True)
    outcome = run_tool_surfaces(
        tmp_path,
        ["claude"],
        kinds=[ToolSurfaceKind.HOOK],
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=consent),
    )
    assert len(outcome.assessments) == 1
    assert outcome.assessments[0].complete and outcome.assessments[0].effects
    results = SurfaceRepairService(build_providers()).apply_assessments(outcome.assessments, consent)
    assert all(result.outcome == "applied" for result in results)
    assert (tmp_path / ".claude/CLAUDE.md").is_file()
    assert (tmp_path / ".claude/settings.json").is_file()


def _installed_version() -> str:
    from importlib.metadata import version

    return version("spec-kitty-cli")


def _write_orientation(target: Path, *, version: str) -> None:
    """Write a full orientation block stamped at ``version`` to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    block = SessionPresenceContent(
        version=version,
        project_slug="unknown",
        health="healthy",
        available_version=None,
    ).render()
    target.write_text(block, encoding="utf-8")


def test_provider_satisfies_reporting_protocol() -> None:
    provider = SessionPresenceProvider()
    assert isinstance(provider, ReportingSurfaceProvider)
    assert provider.provider_key == "session_presence"


def test_can_handle_context_file() -> None:
    provider = SessionPresenceProvider()
    assert provider.can_handle(context_file_definition()) is True


def test_can_handle_hook() -> None:
    provider = SessionPresenceProvider()
    assert provider.can_handle(hook_definition()) is True


def test_can_handle_rule() -> None:
    provider = SessionPresenceProvider()
    assert provider.can_handle(rule_definition()) is True


def test_cannot_handle_command_skill() -> None:
    provider = SessionPresenceProvider()
    assert provider.can_handle(command_skill_definition()) is False


def test_definitions_use_distinct_kinds() -> None:
    assert context_file_definition().kind == ToolSurfaceKind.CONTEXT_FILE
    assert hook_definition().kind == ToolSurfaceKind.HOOK
    assert rule_definition().kind == ToolSurfaceKind.RULE
    # session_presence is a provider name, never a ToolSurfaceKind value.
    assert "session_presence" not in {k.value for k in ToolSurfaceKind}


def test_session_presence_is_provider_key_not_a_kind() -> None:
    for definition in (
        context_file_definition(),
        hook_definition(),
        rule_definition(),
    ):
        assert definition.provider_key == "session_presence"
        assert str(definition.kind) != "session_presence"


def test_expand_claude_context_file(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instances = provider.expand(context_file_definition(), "claude", tmp_path)
    assert len(instances) == 1
    inst = instances[0]
    assert inst.definition.kind == ToolSurfaceKind.CONTEXT_FILE
    assert inst.path == tmp_path / ".claude" / "CLAUDE.md"
    assert inst.owner == "claude"


def test_expand_claude_hooks_two_entries(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instances = provider.expand(hook_definition(), "claude", tmp_path)
    # SessionStart and Stop -> two hook instances.
    assert len(instances) == 2
    assert all(i.definition.kind == ToolSurfaceKind.HOOK for i in instances)
    assert all(i.path.name == "settings.json" for i in instances)


def test_expand_filters_to_requested_kind(tmp_path: Path) -> None:
    """A context_file definition must not leak hook instances."""
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    ctx = provider.expand(context_file_definition(), "claude", tmp_path)
    assert all(i.definition.kind == ToolSurfaceKind.CONTEXT_FILE for i in ctx)


def test_expand_cursor_yields_rule(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    provider = SessionPresenceProvider()
    instances = provider.expand(rule_definition(), "cursor", tmp_path)
    assert len(instances) == 1
    assert instances[0].definition.kind == ToolSurfaceKind.RULE
    assert instances[0].path.name.endswith(".mdc")


def test_expand_codex_context_file_is_agents_md(tmp_path: Path) -> None:
    provider = SessionPresenceProvider()
    instances = provider.expand(context_file_definition(), "codex", tmp_path)
    assert len(instances) == 1
    assert instances[0].path == tmp_path / "AGENTS.md"
    assert instances[0].definition.kind == ToolSurfaceKind.CONTEXT_FILE


def test_expand_per_tool_paths_differ(tmp_path: Path) -> None:
    """Each tool has distinct session presence paths."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".cursor").mkdir()
    provider = SessionPresenceProvider()
    claude = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    codex = provider.expand(context_file_definition(), "codex", tmp_path)[0]
    cursor = provider.expand(rule_definition(), "cursor", tmp_path)[0]
    paths = {claude.path, codex.path, cursor.path}
    assert len(paths) == 3


def test_expand_null_writer_yields_research_gap(tmp_path: Path) -> None:
    provider = SessionPresenceProvider()
    instances = provider.expand(context_file_definition(), "qwen", tmp_path)
    assert len(instances) == 1
    status = provider.probe(instances[0])
    assert status.state == STATE_NOT_APPLICABLE
    assert status.findings[0].code == "research-gap-surface"
    assert status.findings[0].severity == "info"


def test_probe_detects_missing_context_file(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "context-file-missing"
    assert status.findings[0].repair_command is not None


def test_probe_detects_missing_hook(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(hook_definition(), "claude", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "session-presence-incomplete"


def test_repair_cursor_rule_creates_missing_directory_without_dir_fd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no dir_fd support): repair still creates the missing rule directory.

    Exercises the ``effect.after.kind == "directory"`` branch in
    ``SessionPresenceProvider._apply_prepared`` (session_presence.py site
    #8), which previously called ``os.mkdir(..., dir_fd=fd)`` /
    ``os.fchmod(fd, ...)`` unconditionally -- both unsupported on Windows.
    The Cursor rule writer's ``.cursor/rules`` directory does not exist yet,
    so applying it must create that directory through the Windows fallback.
    """
    import os
    import stat

    monkeypatch.setattr(os, "supports_dir_fd", set())
    (tmp_path / ".cursor").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(rule_definition(), "cursor", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING

    result = provider.repair(tmp_path, [missing])

    assert result.repaired
    assert not result.failed
    rules_dir = tmp_path / ".cursor" / "rules"
    assert rules_dir.is_dir()
    assert stat.S_IMODE(rules_dir.stat().st_mode) == 0o755
    refreshed = provider.probe(instance)
    assert refreshed.state == STATE_PRESENT


def test_probe_present_after_repair(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING
    result = provider.repair(tmp_path, [missing])
    assert result.repaired
    assert not result.failed
    refreshed = provider.probe(instance)
    assert refreshed.state == STATE_PRESENT
    assert (tmp_path / ".claude" / "CLAUDE.md").exists()


def test_repair_hook_registers_entries(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instances = provider.expand(hook_definition(), "claude", tmp_path)
    statuses = [provider.probe(i) for i in instances]
    result = provider.repair(tmp_path, statuses)
    assert result.repaired
    assert (tmp_path / ".claude" / "settings.json").exists()
    for instance in instances:
        assert provider.probe(instance).state == STATE_PRESENT


def test_repair_dry_run_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    status = provider.probe(instance)
    result = provider.repair(tmp_path, [status], dry_run=True)
    assert result.dry_run is True
    assert result.repaired
    assert not (tmp_path / ".claude" / "CLAUDE.md").exists()


def test_repair_no_actionable_skips_research_gap(tmp_path: Path) -> None:
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "qwen", tmp_path)[0]
    status = provider.probe(instance)
    result = provider.repair(tmp_path, [status])
    assert result.repaired == ()
    assert status.findings[0].code == "research-gap-surface"
    assert result.skipped


def test_remove_research_gap_returns_false(tmp_path: Path) -> None:
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "qwen", tmp_path)[0]
    assert provider.remove(instance) is False


def test_remove_context_file_deletes_section(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(rule_definition(), "cursor", tmp_path)[0]
    provider.repair(tmp_path, [provider.probe(instance)])
    assert provider.probe(instance).state == STATE_PRESENT
    assert provider.remove(instance) is True
    assert provider.probe(instance).state == STATE_MISSING


# ---------------------------------------------------------------------------
# Stale orientation refresh (#2265)
# ---------------------------------------------------------------------------


def test_probe_reports_stale_when_context_file_version_outdated(tmp_path: Path) -> None:
    """A present-but-outdated orientation block must probe as STATE_STALE.

    #2265: the block is stamped at init time and left untouched by upgrade, so
    an already-up-to-date project keeps a version string that contradicts the
    live SessionStart hook. The provider must detect the version mismatch.
    """
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    _write_orientation(tmp_path / ".claude" / "CLAUDE.md", version="0.0.1-legacy")

    status = provider.probe(instance)

    assert status.state == STATE_STALE
    assert status.findings, "a stale surface must carry a finding"
    assert status.findings[0].repair_command is not None


def test_probe_current_version_is_present_not_stale(tmp_path: Path) -> None:
    """An orientation block already at the installed version must not churn."""
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    _write_orientation(tmp_path / ".claude" / "CLAUDE.md", version=_installed_version())

    assert provider.probe(instance).state == STATE_PRESENT


def test_probe_present_when_version_unparseable(tmp_path: Path) -> None:
    """A present block with no parseable version stamp is left alone, not churned."""
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    # Marker present (so it counts as present) but no ``**Spec Kitty v...**`` stamp.
    (tmp_path / ".claude" / "CLAUDE.md").write_text(
        f"{SECTION_OPEN}\nhand-edited, no version stamp\n<!-- /spec-kitty:orientation -->\n",
        encoding="utf-8",
    )

    assert provider.probe(instance).state == STATE_PRESENT


def test_repair_rewrites_stale_context_file_to_current_version(tmp_path: Path) -> None:
    """repair() must action STATE_STALE and rewrite the block to the installed version."""
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    target = tmp_path / ".claude" / "CLAUDE.md"
    _write_orientation(target, version="0.0.1-legacy")

    status = provider.probe(instance)
    assert status.state == STATE_STALE

    result = provider.repair(tmp_path, [status])

    assert result.repaired
    assert not result.failed
    text = target.read_text(encoding="utf-8")
    assert f"**Spec Kitty v{_installed_version()}**" in text
    assert "0.0.1-legacy" not in text
    assert text.count(SECTION_OPEN) == 1, "the block must be replaced in place, not duplicated"
    assert provider.probe(instance).state == STATE_PRESENT


def test_probe_ignores_version_stamp_outside_managed_block(tmp_path: Path) -> None:
    """A stray '**Spec Kitty v...**' outside the block must not fool staleness.

    Squad F1: the version parse is scoped to the marker-delimited managed block,
    so a pasted example or a second stamp elsewhere in the file cannot be read
    as the managed version (false-stale churn or false-fresh).
    """
    (tmp_path / ".claude").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", tmp_path)[0]
    target = tmp_path / ".claude" / "CLAUDE.md"
    current_block = SessionPresenceContent(
        version=_installed_version(),
        project_slug="unknown",
        health="healthy",
        available_version=None,
    ).render()
    # A stale-looking stamp lives OUTSIDE the managed block (user prose); the
    # managed block itself is current.
    target.write_text(
        "# My project notes\nWe pinned **Spec Kitty v0.0.1-legacy** last year.\n\n" + current_block,
        encoding="utf-8",
    )

    assert provider.probe(instance).state == STATE_PRESENT


def test_probe_reports_stale_for_rule_surface(tmp_path: Path) -> None:
    """RULE-kind orientation surfaces (.cursor/rules, .kiro/steering) also refresh.

    Squad F2: rule/steering files are written by the same Markdown family and
    carry the identical version stamp, so they must not be left latently stale.
    """
    (tmp_path / ".cursor").mkdir()
    provider = SessionPresenceProvider()
    instance = provider.expand(rule_definition(), "cursor", tmp_path)[0]
    assert instance.definition.kind == ToolSurfaceKind.RULE
    _write_orientation(instance.path, version="0.0.1-legacy")

    status = provider.probe(instance)
    assert status.state == STATE_STALE

    result = provider.repair(tmp_path, [status])
    assert result.repaired
    assert not result.failed
    text = instance.path.read_text(encoding="utf-8")
    assert f"**Spec Kitty v{_installed_version()}**" in text
    assert "0.0.1-legacy" not in text
    assert provider.probe(instance).state == STATE_PRESENT
