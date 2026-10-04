"""Pack-skill drift/staleness findings on the real surfaces (FR-012, FR-014).

Mission ``pack-skills-kind-01M43419``, WP05, issue #5193. Findings come from
``find_pack_skill_findings`` and are asserted through ``doctor skills`` (CLI
runner) and the upgrade assessment; each names the pack ``source_ref``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.skills import catalog
from specify_cli.skills.catalog import resolve_project_skill_catalog
from specify_cli.skills.installer import install_all_skills
from specify_cli.skills.manifest import ORIGIN_PACK, load_manifest, save_manifest
from specify_cli.skills.pack_skill_drift import KIND_DRIFT, KIND_ORPHANED, KIND_STALE, find_pack_skill_findings
from specify_cli.tool_surface.operations import ApplyConsent
from specify_cli.upgrade.assessment import prepare_upgrade_repairs
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.integration]

runner = CliRunner()
SKILL_ID = "deploy-helper"
RENDERED = "acme-deploy-helper"
SOURCE_REF = "skills/deploy-helper.skill.yaml"
CONFIG = "agents:\n  available:\n    - claude\n    - codex\nactivated_skills: []\n"


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    root = tmp_path / "pack"
    root.mkdir()
    support.write_skill(root, SKILL_ID)
    support.write_org_charter(root, namespace="acme")
    return root


@pytest.fixture
def project(tmp_path: Path, pack: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    root = tmp_path / "project"
    root.mkdir()
    support.write_config(root, pack, extra=CONFIG)
    save_manifest(install_all_skills(root, ["claude", "codex"], resolve_project_skill_catalog(root)), root)
    result = runner.invoke(charter_app, ["activate", "skill", SKILL_ID, "--repo-root", str(root), "--no-compile"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return root


def _rendered(project: Path) -> Path:
    return project / ".claude" / "skills" / RENDERED / "SKILL.md"


def _doctor(project: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
    monkeypatch.setattr("specify_cli.cli.commands.doctor.locate_project_root", lambda: project)
    result = runner.invoke(doctor_app, ["skills", "--json"])
    start = result.output.index("{")
    return result.exit_code, json.loads(result.output[start:])


def _diagnostic_codes(project: Path) -> dict[str, str]:
    prepared = prepare_upgrade_repairs(project, consent=ApplyConsent(automatic=True))
    return {d.code: d.message for d in prepared.diagnostics if d.code.startswith("pack_skill_")}


def test_clean_install_has_no_findings(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert find_pack_skill_findings(project) == ()
    assert _diagnostic_codes(project) == {}
    _, payload = _doctor(project, monkeypatch)
    assert payload["pack_skills"] == []


def test_local_edit_is_drift_naming_source_ref(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _rendered(project).write_text(_rendered(project).read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")

    findings = find_pack_skill_findings(project)
    assert {f.kind for f in findings} == {KIND_DRIFT}
    assert {f.installed_path for f in findings} == {f".claude/skills/{RENDERED}/SKILL.md"}
    assert all(f.source_ref == SOURCE_REF or f.source_ref.endswith(SOURCE_REF) for f in findings)

    code, payload = _doctor(project, monkeypatch)
    assert code == 1 and payload["ok"] is False
    reported = payload["pack_skills"]
    assert [item["kind"] for item in reported] == [KIND_DRIFT]
    assert reported[0]["source_ref"] in reported[0]["message"]

    messages = _diagnostic_codes(project)
    assert set(messages) == {"pack_skill_drift"}
    assert findings[0].source_ref in messages["pack_skill_drift"]


def test_pack_change_is_staleness_naming_source_ref(project: Path, pack: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (pack / "skills" / f"{SKILL_ID}.skill.md").write_text("Changed upstream: $ARGUMENTS\n", encoding="utf-8")

    findings = find_pack_skill_findings(project)
    assert {f.kind for f in findings} == {KIND_STALE}
    assert len(findings) == 2  # claude + codex copies
    source_ref = findings[0].source_ref
    assert source_ref

    code, payload = _doctor(project, monkeypatch)
    assert code == 1
    assert {item["kind"] for item in payload["pack_skills"]} == {KIND_STALE}
    assert all(item["source_ref"] == source_ref and source_ref in item["message"] for item in payload["pack_skills"])

    messages = _diagnostic_codes(project)
    assert set(messages) == {"pack_skill_stale"}
    assert source_ref in messages["pack_skill_stale"]


def test_findings_are_read_only(project: Path, pack: Path) -> None:
    _rendered(project).write_text("edited\n", encoding="utf-8")
    (pack / "skills" / f"{SKILL_ID}.skill.md").write_text("changed\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    find_pack_skill_findings(project)
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before


def test_old_manifest_without_provenance_gives_no_false_drift(project: Path, pack: Path) -> None:
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    # Simulate a manifest written before pack skills: no origin/source_* on any entry.
    for entry in manifest.entries:
        entry.origin, entry.source_ref, entry.source_hash = "builtin", "", ""
    save_manifest(manifest, project)
    (pack / "skills" / f"{SKILL_ID}.skill.md").write_text("changed\n", encoding="utf-8")
    _rendered(project).write_text("edited\n", encoding="utf-8")

    assert find_pack_skill_findings(project) == ()


def test_pack_entry_without_source_hash_is_not_stale(project: Path, pack: Path) -> None:
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    for entry in manifest.entries:
        if entry.origin == ORIGIN_PACK:
            entry.source_hash = ""
    save_manifest(manifest, project)
    (pack / "skills" / f"{SKILL_ID}.skill.md").write_text("changed\n", encoding="utf-8")
    assert find_pack_skill_findings(project) == ()


def test_no_manifest_and_retired_skill_yield_nothing(tmp_path: Path, project: Path, pack: Path) -> None:
    assert find_pack_skill_findings(tmp_path) == ()
    (pack / "skills" / f"{SKILL_ID}.skill.yaml").unlink()  # unresolvable -> staleness not assessed
    assert [f for f in find_pack_skill_findings(project) if f.kind == KIND_STALE] == []


def test_absent_installed_file_is_not_drift(project: Path) -> None:
    _rendered(project).unlink()
    assert [f for f in find_pack_skill_findings(project) if f.installed_path.startswith(".claude/")] == []


def test_read_only_resolution_reuses_one_parent_and_keeps_earlier_registries_valid(project: Path, pack: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registrations: list[object] = []
    monkeypatch.setattr(catalog.atexit, "register", lambda *args, **kwargs: registrations.append(args))
    monkeypatch.setattr(catalog, "_READ_ONLY_ROOT", None)

    first = resolve_project_skill_catalog(project, stage=False)
    skill = next(s for s in first.discover_skills() if s.name == RENDERED)
    file = skill.skill_dir / "SKILL.md"
    before = file.stat()

    second = resolve_project_skill_catalog(project, stage=False)
    resolve_project_skill_catalog(project, stage=False)

    after = file.stat()
    assert (before.st_dev, before.st_ino, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_mtime_ns)
    assert file.is_file() and any(s.name == RENDERED for s in second.discover_skills())
    assert len(registrations) == 1
    assert catalog._READ_ONLY_ROOT is not None
    assert len(list(catalog._READ_ONLY_ROOT.iterdir())) == 1  # same rendered set -> same subdir

    # A changed pack gets its own subdir; the earlier one is untouched.
    (pack / "skills" / f"{SKILL_ID}.skill.md").write_text("changed\n", encoding="utf-8")
    resolve_project_skill_catalog(project, stage=False)
    assert file.is_file()
    assert len(list(catalog._READ_ONLY_ROOT.iterdir())) == 2
    shutil.rmtree(catalog._READ_ONLY_ROOT, ignore_errors=True)  # the suppressed atexit handler would have done this


def test_prepare_then_apply_upgrade_with_active_pack_skill_is_not_invalidated(project: Path) -> None:
    from specify_cli.upgrade.assessment import apply_upgrade_repairs, preflight_upgrade_repairs

    prepared = prepare_upgrade_repairs(project, consent=ApplyConsent(automatic=True))
    with preflight_upgrade_repairs(prepared) as errors:
        assert not [e for e in errors if getattr(e, "severity", "error") == "error"], errors
        results = apply_upgrade_repairs(prepared)
    assert all(r.outcome != "precondition_changed" for r in results), results


def test_requires_edge_change_is_staleness(project: Path, pack: Path) -> None:
    """The rendered preamble depends on DRG ``requires``; adding an edge makes the install stale."""
    assert find_pack_skill_findings(project) == ()
    support.write_procedure(pack, "proc-p")
    support.write_fragment(
        pack,
        nodes=[(f"skill:{SKILL_ID}", "skill"), ("procedure:proc-p", "procedure")],
        edges=[(f"skill:{SKILL_ID}", "procedure:proc-p", "requires")],
    )

    assert {f.kind for f in find_pack_skill_findings(project)} == {KIND_STALE}


def test_legacy_bare_hex_source_hash_is_stale_once_then_clean(project: Path) -> None:
    """A pre-``sha256:`` manifest is reported stale once; re-projection rewrites the prefixed form."""
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    for entry in manifest.entries:
        if entry.origin == ORIGIN_PACK:
            assert entry.source_hash.startswith("sha256:")
            entry.source_hash = entry.source_hash.removeprefix("sha256:")
    save_manifest(manifest, project)
    assert {f.kind for f in find_pack_skill_findings(project)} == {KIND_STALE}

    save_manifest(install_all_skills(project, ["claude", "codex"], resolve_project_skill_catalog(project)), project)
    assert find_pack_skill_findings(project) == ()


def test_namespace_change_orphans_the_old_copies_on_every_surface(project: Path, pack: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    support.write_org_charter(pack, namespace="beta")  # skill now renders as beta-deploy-helper

    findings = find_pack_skill_findings(project)
    assert {f.kind for f in findings} == {KIND_ORPHANED}
    assert len(findings) == 2  # claude + codex copies, one orphaned finding each
    assert {f.skill_name for f in findings} == {RENDERED}
    source_ref = findings[0].source_ref
    assert source_ref
    assert source_ref in findings[0].message and "spec-kitty upgrade" in findings[0].message

    code, payload = _doctor(project, monkeypatch)
    assert code == 1
    assert {item["kind"] for item in payload["pack_skills"]} == {KIND_ORPHANED}

    messages = _diagnostic_codes(project)
    assert set(messages) == {"pack_skill_orphaned"}
    assert source_ref in messages["pack_skill_orphaned"]
