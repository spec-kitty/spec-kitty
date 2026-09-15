"""Unit tests for ``tool_surface.providers.native_config``."""

from __future__ import annotations

from pathlib import Path

from specify_cli.tool_surface.enums import ToolSurfaceKind
from specify_cli.tool_surface.providers.command_skills import (
    command_skill_definition,
)
from specify_cli.tool_surface.providers.native_config import (
    NativeConfigProvider,
    native_config_definition,
)
from specify_cli.tool_surface.providers.protocol import ReportingSurfaceProvider
from specify_cli.tool_surface.status import (
    STATE_MISSING,
    STATE_NOT_APPLICABLE,
    STATE_PRESENT,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_provider_satisfies_reporting_protocol() -> None:
    provider = NativeConfigProvider()
    assert isinstance(provider, ReportingSurfaceProvider)
    assert provider.provider_key == "native_config"


def test_can_handle_native_config_only() -> None:
    provider = NativeConfigProvider()
    assert provider.can_handle(native_config_definition()) is True
    assert provider.can_handle(command_skill_definition()) is False


def test_definition_kind_is_native_config() -> None:
    assert native_config_definition().kind == ToolSurfaceKind.NATIVE_CONFIG


def test_expand_vibe_yields_config_instance(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instances = provider.expand(native_config_definition(), "vibe", tmp_path)
    assert len(instances) == 1
    assert instances[0].path == tmp_path / ".vibe" / "config.toml"
    assert instances[0].owner == "vibe"


def test_expand_non_vibe_yields_research_gap(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instances = provider.expand(native_config_definition(), "claude", tmp_path)
    assert len(instances) == 1
    status = provider.probe(instances[0])
    assert status.state == STATE_NOT_APPLICABLE
    assert status.findings[0].code == "research-gap-surface"
    assert status.findings[0].severity == "info"


def test_probe_missing_when_config_absent(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    status = provider.probe(instance)
    assert status.state == STATE_MISSING
    assert status.findings[0].code == "native-config-missing"
    assert status.findings[0].repair_command is not None


def test_probe_missing_when_skill_path_absent(tmp_path: Path) -> None:
    vibe = tmp_path / ".vibe"
    vibe.mkdir()
    (vibe / "config.toml").write_text('other = "value"\n', encoding="utf-8")
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    assert provider.probe(instance).state == STATE_MISSING


def test_probe_present_when_skill_path_listed(tmp_path: Path) -> None:
    vibe = tmp_path / ".vibe"
    vibe.mkdir()
    (vibe / "config.toml").write_text('skill_paths = [".agents/skills"]\n', encoding="utf-8")
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    assert provider.probe(instance).state == STATE_PRESENT


def test_probe_present_when_skill_path_is_string(tmp_path: Path) -> None:
    vibe = tmp_path / ".vibe"
    vibe.mkdir()
    (vibe / "config.toml").write_text('skill_paths = ".agents/skills"\n', encoding="utf-8")
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    assert provider.probe(instance).state == STATE_PRESENT


def test_probe_missing_on_invalid_toml(tmp_path: Path) -> None:
    vibe = tmp_path / ".vibe"
    vibe.mkdir()
    (vibe / "config.toml").write_text("not = valid = toml", encoding="utf-8")
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    assert provider.probe(instance).state == STATE_MISSING


def test_repair_writes_skill_path(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    missing = provider.probe(instance)
    assert missing.state == STATE_MISSING
    result = provider.repair(tmp_path, [missing])
    assert result.repaired
    assert not result.failed
    assert provider.probe(instance).state == STATE_PRESENT
    assert (tmp_path / ".vibe" / "config.toml").exists()


def test_repair_dry_run_writes_nothing(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    status = provider.probe(instance)
    result = provider.repair(tmp_path, [status], dry_run=True)
    assert result.dry_run is True
    assert result.repaired
    assert not (tmp_path / ".vibe").exists()


def test_repair_skips_research_gap(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "claude", tmp_path)[0]
    status = provider.probe(instance)
    result = provider.repair(tmp_path, [status])
    assert result.repaired == ()
    assert result.skipped


def test_remove_is_noop(tmp_path: Path) -> None:
    provider = NativeConfigProvider()
    instance = provider.expand(native_config_definition(), "vibe", tmp_path)[0]
    assert provider.remove(instance) is False


def test_wp07_existing_vibe_helper_preserves_unowned_toml(tmp_path: Path) -> None:
    from specify_cli.skills.vibe_config import ensure_project_skill_path

    target = tmp_path / ".vibe/config.toml"
    target.parent.mkdir()
    original = (b'# personal config\r\nskill_paths = ["custom"] # retain comment\r\n\r\n[tools]\r\nskill_paths = ["nested"]\r\ncustom = "value"\r\n\r\n')
    target.write_bytes(original)
    ensure_project_skill_path(tmp_path)
    assert target.read_bytes() == original.replace(b'["custom"]', b'["custom", ".agents/skills"]')


def _native_assessment(root: Path):
    from specify_cli.tool_surface.operations import AssessmentInputs, ApplyConsent, OperationRoot
    from specify_cli.tool_surface.model import SurfaceSelection

    return NativeConfigProvider().assess(
        AssessmentInputs(OperationRoot("project", "project", root), consent=ApplyConsent(automatic=True)),
        (),
        selections=(SurfaceSelection("vibe", native_config_definition()),),
    )


def test_wp07_cycle2_directory_chmod_failure_is_not_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    import stat
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    assessment = _native_assessment(tmp_path)
    assert assessment.complete and len(assessment.effects) == 2
    original = os.fchmod
    failed_descriptors: list[int] = []

    def fail_directory(fd: int, mode: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            failed_descriptors.append(fd)
            raise OSError("cycle2 directory fchmod fault")
        original(fd, mode)

    before = snapshot({"project": tmp_path})
    monkeypatch.setattr(os, "fchmod", fail_directory)
    previous = os.umask(0o077)
    try:
        result = NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    finally:
        os.umask(previous)
    delta = net_delta(before, snapshot({"project": tmp_path}))
    assert [(e.path, e.after.kind, e.after.mode) for e in delta] == [(".vibe", "directory", 0o700)]
    directory = next(e for e in assessment.effects if e.path == ".vibe")
    assert directory.after.mode == 0o755
    assert directory.id not in result.succeeded
    assert directory.id in result.failed and result.diagnostics
    assert failed_descriptors
    with pytest.raises(OSError):
        os.fstat(failed_descriptors[0])


def test_wp07_cycle2_completed_directory_survives_file_fault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    assessment = _native_assessment(tmp_path)

    def fail_replace(*args: object, **kwargs: object) -> None:
        raise OSError("cycle2 file replace fault")

    monkeypatch.setattr(os, "replace", fail_replace)
    before = snapshot({"project": tmp_path})
    previous = os.umask(0o077)
    try:
        result = NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    finally:
        os.umask(previous)
    delta = net_delta(before, snapshot({"project": tmp_path}))
    assert [(e.path, e.after.kind, e.after.mode) for e in delta] == [(".vibe", "directory", 0o755)]
    assert result.outcome == "partial" and result.failed
    assert result.succeeded == tuple(e.id for e in assessment.effects if e.path == ".vibe")


def test_wp07_cycle2_nan_does_not_bypass_nested_preservation_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import vibe_config
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / ".vibe").mkdir()
    (tmp_path / ".vibe/config.toml").write_text('skill_paths = ["custom"]\nnested = {special = nan, finite = 1}\n')
    original = vibe_config._add_skill_path

    def corrupt_foreign(text: str, paths: object) -> str:
        return original(text, paths).replace("finite = 1", "finite = 2")

    monkeypatch.setattr(vibe_config, "_add_skill_path", corrupt_foreign)
    before = snapshot({"project": tmp_path})
    assessment = _native_assessment(tmp_path)
    assert not assessment.complete and not assessment.effects
    assert "unowned TOML key" in assessment.diagnostics[0].message
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("foreign", [b"threshold = nan\n", b"threshold = {nested = [nan, {negative = -nan, positive = +nan}]}\n"])
def test_wp07_cycle2_legal_nan_preserves_foreign_bytes(tmp_path: Path, foreign: bytes) -> None:
    import tomllib
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    (tmp_path / ".vibe").mkdir()
    target = tmp_path / ".vibe/config.toml"
    original = b'# keep\nskill_paths = ["custom"] # owned entry\n' + foreign
    target.write_bytes(original)
    tomllib.loads(original.decode())
    before = snapshot({"project": tmp_path})
    assessment = _native_assessment(tmp_path)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert assessment.complete and assessment.effects, assessment.diagnostics
    result = NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.succeeded and not result.failed
    assert target.read_bytes() == original.replace(b'["custom"]', b'["custom", ".agents/skills"]')
    assert len(net_delta(before, snapshot({"project": tmp_path}))) == 1
    after = snapshot({"project": tmp_path})
    again = _native_assessment(tmp_path)
    assert again.complete and not again.effects
    NativeConfigProvider().apply(again, ApplyConsent(automatic=True))
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("closing", [4, 5])
def test_wp07_cycle2_multiline_closing_quotes(tmp_path: Path, quote: str, closing: int) -> None:
    import json
    import tomllib
    from specify_cli.skills.vibe_config import ensure_project_skill_path
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / ".vibe").mkdir()
    target = tmp_path / ".vibe/config.toml"
    scalar = quote * 3 + "custom" + quote * closing
    prefix, suffix = "# keep\r\nskill_paths = ", " # keep too\r\n[tools]\nforeign = true\n"
    original = prefix + scalar + suffix
    target.write_bytes(original.encode())
    value = tomllib.loads(original)["skill_paths"]
    assert value == "custom" + quote * (closing - 3)
    ensure_project_skill_path(tmp_path)
    expected = prefix + json.dumps([value, ".agents/skills"]) + suffix
    assert target.read_bytes() == expected.encode()
    after = snapshot({"project": tmp_path})
    ensure_project_skill_path(tmp_path)
    assert_unchanged(after, snapshot({"project": tmp_path}))


def test_wp07_native_disabled_repair_is_skipped(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("agents:\n  available: []\n")
    provider = NativeConfigProvider()
    statuses = [provider.probe(i) for i in provider.expand(native_config_definition(), "vibe", tmp_path)]
    result = provider.repair(tmp_path, statuses)
    assert not result.repaired and result.skipped
    assert not (tmp_path / ".vibe").exists()


@pytest.mark.parametrize("path", [".vibe/config.toml", ".kittify/config.yaml"])
def test_wp07_native_directory_is_not_a_config(tmp_path: Path, path: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / path).mkdir(parents=True)
    before = snapshot({"project": tmp_path})
    assessment = _native_assessment(tmp_path)
    assert not assessment.complete and assessment.diagnostics and not assessment.effects
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize(
    "original",
    [
        None,
        b'# custom\n[tools]\nvalue = "keep"\n',
        b'skill_paths = "custom" # keep\n',
        b'skill_paths = [\n "custom", # keep\n]\n[table]\nskill_paths = []\n',
        b"\"skill_paths\" = ['custom'] # keep\n",
    ],
)
def test_wp07_native_exact_physical_effects_and_second_apply(tmp_path: Path, original: bytes | None) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from specify_cli.skills.vibe_config import PreparedVibeConfig
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    if original is not None:
        (tmp_path / ".vibe").mkdir()
        (tmp_path / ".vibe/config.toml").write_bytes(original)
    before = snapshot({"project": tmp_path})
    assessment = _native_assessment(tmp_path)
    assert assessment.complete, assessment.diagnostics
    assert assessment.effects
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert isinstance(assessment.prepared, PreparedVibeConfig)
    assert assessment.prepared.execution_artifacts
    expected_bytes = assessment.prepared.file.content
    result = NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "applied", result
    after = snapshot({"project": tmp_path})
    assert {(e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in assessment.effects} == {
        (e.path, e.action, e.after.kind, e.after.mode, e.after.sha256) for e in net_delta(before, after)
    }
    assert (tmp_path / ".vibe/config.toml").read_bytes() == expected_bytes
    for _ in range(2):
        again = _native_assessment(tmp_path)
        assert again.complete and not again.effects
        NativeConfigProvider().apply(again, ApplyConsent(automatic=True))
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("raw", [b"bad = =", b"skill_paths = 7", b'skill_paths = ["custom", 7]'])
def test_wp07_native_malformed_blocks_without_writes(tmp_path: Path, raw: bytes) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    (tmp_path / ".vibe").mkdir()
    (tmp_path / ".vibe/config.toml").write_bytes(raw)
    before = snapshot({"project": tmp_path})
    assessment = _native_assessment(tmp_path)
    assert not assessment.complete and assessment.diagnostics
    NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("change", ["config", "target", "parent"])
def test_wp07_native_whole_batch_recheck(tmp_path: Path, change: str) -> None:
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    root = tmp_path / "project"
    root.mkdir()
    (root / ".kittify").mkdir()
    (root / ".kittify/config.yaml").write_text("agents:\n  available: [vibe]\n")
    (root / ".vibe").mkdir()
    assessment = _native_assessment(root)
    assert assessment.complete and assessment.effects
    if change == "config":
        (root / ".kittify/config.yaml").write_text("agents:\n  available: []\n")
    elif change == "target":
        (root / ".vibe/config.toml").write_text("# new custom file\n")
    else:
        (root / ".vibe").rename(root / "saved")
        (root / ".vibe").symlink_to(tmp_path, target_is_directory=True)
    before = snapshot({"sandbox": tmp_path})
    result = NativeConfigProvider().apply(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_wp07_native_actual_service_selection(tmp_path: Path) -> None:
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.service import run_tool_surfaces

    outcome = run_tool_surfaces(
        tmp_path,
        ["vibe"],
        kinds=[ToolSurfaceKind.NATIVE_CONFIG],
        assessment_inputs=AssessmentInputs(OperationRoot("project", "project", tmp_path)),
    )
    assert len(outcome.assessments) == 1
    assert outcome.assessments[0].complete
    assert {e.path for e in outcome.assessments[0].effects} == {".vibe", ".vibe/config.toml"}
