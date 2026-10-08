"""Charter-pack cutover migration: project-root move, path references, selection (#3732, T055/T058/T060)."""

from __future__ import annotations

import json
import os
import sys
from kernel.clock import datetime
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.migration.legacy_charter_layout import detect_legacy_charter_layout
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations import m_4_0_0rc6_charter_pack_cutover as cutover
from specify_cli.upgrade.migrations._charter_pack_cutover_report import CutoverReport
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit]

LEGACY = ".kittify/doctrine"
NEW = ".kittify/charter-packs"
CUTOVER_ID = "charter_pack_cutover"
#: The contract report keys (contracts/upgrade-migration.md), in contract order.
REPORT_KEYS = ("moved", "rewritten", "reset", "kept_for_review", "matches_minimal", "skills_removed", "skills_kept", "errors")


def _write(project: Path, rel: str, text: str) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _digest(project: Path) -> dict[str, bytes]:
    """Every file and symlink under *project* and its bytes or link target (a tree snapshot)."""
    entries = sorted(p for p in project.rglob("*") if p.is_file() or p.is_symlink())
    return {p.relative_to(project).as_posix(): os.readlink(p).encode() if p.is_symlink() else p.read_bytes() for p in entries}


def _report(result: MigrationResult) -> dict[str, list[str]]:
    report: dict[str, list[str]] = json.loads(result.changes_made[0])
    return report


def _legacy_tree(project: Path) -> list[str]:
    files = {
        "graph.yaml": "nodes: []\n",
        "directive/001-x.directive.yaml": "id: PROJECT_001\n",
        "directive/.provenance/001-x.yaml": "artifact_id: PROJECT_001\n",
        "overlays/calibration-a.yaml": "overlay: a\n",
        "skills/triage.skill.yaml": "id: triage\n",
    }
    for rel, text in files.items():
        _write(project, f"{LEGACY}/{rel}", text)
    return sorted(files)


def _apply(project: Path, *, dry_run: bool = False) -> MigrationResult:
    return CharterPackCutoverMigration().apply(project, dry_run=dry_run)


# --------------------------------------------------------------------------- #
# Move
# --------------------------------------------------------------------------- #


def test_move_with_nested_dot_directories(tmp_path: Path) -> None:
    files = _legacy_tree(tmp_path)
    (tmp_path / LEGACY / "empty-dir" / "nested").mkdir(parents=True)
    migration = CharterPackCutoverMigration()
    assert detect_legacy_charter_layout(tmp_path)
    result = _apply(tmp_path)
    assert result.success, result.errors
    assert not (tmp_path / LEGACY).exists()
    moved = sorted(p.relative_to(tmp_path / NEW).as_posix() for p in (tmp_path / NEW).rglob("*") if p.is_file())
    assert moved == files
    assert _report(result)["moved"] == [f"{LEGACY}/{rel} -> {NEW}/{rel}" for rel in files]
    assert result.changes_made[1] == f"Moved {LEGACY}/{files[0]} -> {NEW}/{files[0]}"
    assert detect_legacy_charter_layout(tmp_path) == ()
    before = _digest(tmp_path)
    assert _apply(tmp_path).success
    assert _digest(tmp_path) == before
    assert migration.detect(tmp_path) is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink")
def test_move_carries_a_symlink_as_a_symlink(tmp_path: Path) -> None:
    _write(tmp_path, f"{LEGACY}/directive/real.yaml", "id: X\n")
    (tmp_path / LEGACY / "directive" / "alias.yaml").symlink_to("real.yaml")
    assert _apply(tmp_path).success
    alias = tmp_path / NEW / "directive" / "alias.yaml"
    assert alias.is_symlink() and os.readlink(alias) == "real.yaml"


def test_legacy_root_symlink_refuses(tmp_path: Path) -> None:
    _write(tmp_path, "elsewhere/x.yaml", "x\n")
    (tmp_path / ".kittify").mkdir()
    (tmp_path / LEGACY).symlink_to(tmp_path / "elsewhere")
    result = _apply(tmp_path)
    assert not result.success
    assert "is a symlink" in result.errors[0]


def test_collision_refuses_names_every_path_and_writes_nothing(tmp_path: Path) -> None:
    _legacy_tree(tmp_path)
    _write(tmp_path, f"{NEW}/graph.yaml", "nodes: [diverged]\n")
    _write(tmp_path, f"{NEW}/directive/001-x.directive.yaml", "id: OTHER\n")
    _write(tmp_path, f"{NEW}/overlays/calibration-a.yaml", "overlay: a\n")  # identical: not a collision
    _write(tmp_path, ".gitignore", f"{LEGACY}/**\n")
    before = _digest(tmp_path)
    result = _apply(tmp_path)
    assert not result.success
    errors = "\n".join(_report(result)["errors"])
    assert "directive/001-x.directive.yaml" in errors and "graph.yaml" in errors
    assert len(result.errors) == 2
    assert _report(result)["moved"] == [] and _report(result)["rewritten"] == []
    assert _digest(tmp_path) == before


def test_identical_content_overlap_moves_cleanly(tmp_path: Path) -> None:
    files = _legacy_tree(tmp_path)
    _write(tmp_path, f"{NEW}/graph.yaml", "nodes: []\n")
    result = _apply(tmp_path)
    assert result.success, result.errors
    assert not (tmp_path / LEGACY).exists()
    assert len(_report(result)["moved"]) == len(files)


def test_locked_file_refuses_names_the_path_and_a_rerun_finishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POSIX simulation of a Windows lock: removing the locked source raises PermissionError."""
    files = _legacy_tree(tmp_path)
    from specify_cli.asset_preservation import guard as guard_module

    real_remove = guard_module._remove

    def locked_remove(path: Path, *, is_tree: bool) -> None:
        if path.name == "graph.yaml":
            raise PermissionError(13, "The process cannot access the file because it is being used by another process", str(path))
        real_remove(path, is_tree=is_tree)

    monkeypatch.setattr(guard_module, "_remove", locked_remove)
    result = _apply(tmp_path)
    assert not result.success
    assert len(result.errors) == 1 and f"{LEGACY}/graph.yaml could not be moved" in result.errors[0]
    report = _report(result)
    assert report["moved"] == [f"{LEGACY}/{rel} -> {NEW}/{rel}" for rel in files[: files.index("graph.yaml")]]
    monkeypatch.setattr(guard_module, "_remove", real_remove)
    rerun = _apply(tmp_path)
    assert rerun.success, rerun.errors
    assert not (tmp_path / LEGACY).exists()
    assert sorted(p.relative_to(tmp_path / NEW).as_posix() for p in (tmp_path / NEW).rglob("*") if p.is_file()) == files


def test_copy_that_does_not_match_keeps_the_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, f"{LEGACY}/graph.yaml", "nodes: []\n")

    def corrupt_copy(src: Path, dest: Path) -> None:
        dest.write_text("corrupted\n", encoding="utf-8")

    monkeypatch.setattr(cutover, "write_file_verbatim", corrupt_copy)
    result = _apply(tmp_path)
    assert not result.success
    assert "does not match" in result.errors[0]
    assert (tmp_path / LEGACY / "graph.yaml").read_text(encoding="utf-8") == "nodes: []\n"


def test_legacy_root_that_still_holds_files_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, f"{LEGACY}/graph.yaml", "nodes: []\n")
    monkeypatch.setattr(cutover._EmptyTreeProver, "prove", lambda self, path, project_path: None)
    result = _apply(tmp_path)
    assert not result.success
    assert "still holds files" in result.errors[0]


def test_empty_tree_prover_refuses_a_tree_with_a_file(tmp_path: Path) -> None:
    _write(tmp_path, "root/a/b.yaml", "x\n")
    assert cutover._EmptyTreeProver().prove(tmp_path / "root", tmp_path) is None
    (tmp_path / "root" / "a" / "b.yaml").unlink()
    assert cutover._EmptyTreeProver().prove(tmp_path / "root", tmp_path) is not None


def test_dry_run_writes_nothing_and_reports_the_same_items(tmp_path: Path) -> None:
    files = _legacy_tree(tmp_path)
    _write(tmp_path, ".gitignore", f"{LEGACY}/**\n")
    before = _digest(tmp_path)
    dry = _apply(tmp_path, dry_run=True)
    assert _digest(tmp_path) == before
    assert all(line.startswith("Would ") for line in dry.changes_made[1:])
    real = _apply(tmp_path)
    assert _report(dry) == _report(real)
    assert len(_report(real)["moved"]) == len(files)


# --------------------------------------------------------------------------- #
# Path references
# --------------------------------------------------------------------------- #


def _synthesis_manifest(project: Path) -> Path:
    from charter.activation.synthesizer.manifest import ManifestArtifactEntry, SynthesisManifest, finalize_manifest
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    entries = [
        ManifestArtifactEntry(
            kind="directive",
            slug="x",
            path=f"{LEGACY}/directive/001-x.directive.yaml",
            provenance_path=".kittify/charter/provenance/directive-x.yaml",
            content_hash="0" * 64,
        ),
        ManifestArtifactEntry(
            kind="tactic",
            slug="y",
            path=".kittify\\doctrine\\tactic\\y.tactic.yaml",
            provenance_path=".kittify/charter/provenance/tactic-y.yaml",
            content_hash="1" * 64,
        ),
        ManifestArtifactEntry(kind="tactic", slug="z", path=f"{NEW}/tactic/z.tactic.yaml", provenance_path="p", content_hash="2" * 64),
    ]
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-01-01T00:00:00+00:00",
            run_id="R",
            adapter_id="a",
            adapter_version="1",
            synthesizer_version="4.0.0rc6",
            manifest_hash="0" * 64,
            artifacts=entries,
        )
    )
    return _write(project, ".kittify/charter/synthesis-manifest.yaml", canonical_yaml(manifest.model_dump(mode="python")).decode())


def test_synthesis_manifest_paths_rewritten_and_hash_verifies(tmp_path: Path) -> None:
    from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash

    path = _synthesis_manifest(tmp_path)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    result = _apply(tmp_path)
    manifest = load_yaml(path)
    assert [a.path for a in manifest.artifacts] == [f"{NEW}/directive/001-x.directive.yaml", f"{NEW}/tactic/y.tactic.yaml", f"{NEW}/tactic/z.tactic.yaml"]
    verify_manifest_hash(manifest)
    assert len(_report(result)["rewritten"]) == 2
    before = _digest(tmp_path)
    _apply(tmp_path)
    assert _digest(tmp_path) == before
    assert migration.detect(tmp_path) is False


def test_synthesis_manifest_with_the_prefix_only_in_prose_is_untouched(tmp_path: Path) -> None:
    path = _synthesis_manifest(tmp_path)
    text = path.read_text(encoding="utf-8").replace(f"{LEGACY}/directive", f"{NEW}/directive").replace(".kittify\\doctrine\\tactic\\", f"{NEW}/tactic/")
    path.write_text(f"# formerly under {LEGACY}/\n{text}", encoding="utf-8")
    result = _apply(tmp_path)
    assert _report(result)["rewritten"] == []
    assert CharterPackCutoverMigration().detect(tmp_path) is False


def test_provenance_sidecar_values_rewritten(tmp_path: Path) -> None:
    sidecar_text = f"artifact_urn: directive:X\nsource_urns:\n- {LEGACY}/directive/x.yaml\nnote: under {LEGACY}/ once\n"
    sidecar = _write(tmp_path, ".kittify/charter/provenance/directive-x.yaml", sidecar_text)
    nested = _write(tmp_path, f"{NEW}/tactic/.provenance/t.yaml", f"origin:\n  path: {LEGACY}/tactic/t.yaml\n")
    result = _apply(tmp_path)
    data = YAML(typ="safe").load(sidecar.read_text(encoding="utf-8"))
    assert data["source_urns"] == [f"{NEW}/directive/x.yaml"]
    assert data["note"] == f"under {LEGACY}/ once", "only values that start with the old root move"
    assert YAML(typ="safe").load(nested.read_text(encoding="utf-8")) == {"origin": {"path": f"{NEW}/tactic/t.yaml"}}
    assert _report(result)["rewritten"] == [
        f".kittify/charter/provenance/directive-x.yaml: source_urns[0] {LEGACY}/directive/x.yaml -> {NEW}/directive/x.yaml",
        f"{NEW}/tactic/.provenance/t.yaml: origin.path {LEGACY}/tactic/t.yaml -> {NEW}/tactic/t.yaml",
    ]


def test_skills_manifest_source_ref_rewritten(tmp_path: Path) -> None:
    manifest = {
        "version": 1,
        "entries": [
            {"skill_name": "acme-triage", "origin": "pack", "source_ref": f"{LEGACY}/skills/triage.skill.yaml"},
            {"skill_name": "other", "origin": "pack", "source_ref": "org-packs/acme/skills/x.skill.yaml"},
        ],
    }
    path = _write(tmp_path, ".kittify/skills-manifest.json", json.dumps(manifest, indent=2) + "\n")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    result = _apply(tmp_path)
    after = json.loads(path.read_text(encoding="utf-8"))
    assert [e["source_ref"] for e in after["entries"]] == [f"{NEW}/skills/triage.skill.yaml", "org-packs/acme/skills/x.skill.yaml"]
    assert list(after["entries"][0]) == ["skill_name", "origin", "source_ref"], "key order preserved"
    assert path.read_text(encoding="utf-8").startswith('{\n  "version": 1,')
    line = f".kittify/skills-manifest.json: entries[].source_ref {LEGACY}/skills/triage.skill.yaml -> {NEW}/skills/triage.skill.yaml"
    assert _report(result)["rewritten"] == [line]
    assert migration.detect(tmp_path) is False


def test_malformed_skills_manifest_names_the_file(tmp_path: Path) -> None:
    from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError

    _write(tmp_path, ".kittify/skills-manifest.json", f'{{"entries": ["{LEGACY}/x"')
    assert CharterPackCutoverMigration().detect(tmp_path) is True
    with pytest.raises(MigrationStateUnreadableError, match="skills-manifest.json could not be read"):
        _apply(tmp_path)


def test_gitignore_rules_rewritten_with_negations_and_comments_kept(tmp_path: Path) -> None:
    original = f"# {LEGACY} rules\nnode_modules/\n{LEGACY}/**\n!{LEGACY}/graph.yaml\n!{LEGACY}/directive/\n{LEGACY}-other/\n"
    path = _write(tmp_path, ".gitignore", original)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    result = _apply(tmp_path)
    assert path.read_text(encoding="utf-8") == (f"# {LEGACY} rules\nnode_modules/\n{NEW}/**\n!{NEW}/graph.yaml\n!{NEW}/directive/\n{LEGACY}-other/\n")
    assert _report(result)["rewritten"][0] == f".gitignore: rule {LEGACY}/** -> {NEW}/**"
    assert migration.detect(tmp_path) is False


def test_gitignore_rule_already_canonical_drops_the_legacy_line(tmp_path: Path) -> None:
    path = tmp_path / ".gitignore"
    path.write_bytes(f"{NEW}/**\r\n{LEGACY}/**\r\n!{NEW}/graph.yaml\r\n".encode())
    result = _apply(tmp_path)
    assert path.read_bytes() == f"{NEW}/**\r\n!{NEW}/graph.yaml\r\n".encode()
    assert _report(result)["rewritten"] == [f".gitignore: dropped rule {LEGACY}/** ({NEW}/** is already present)"]


def test_gitignore_with_the_root_only_in_comments_is_untouched(tmp_path: Path) -> None:
    text = f"# moved from {LEGACY}\nbuild/\n"
    path = _write(tmp_path, ".gitignore", text)
    assert CharterPackCutoverMigration().detect(tmp_path) is False
    _apply(tmp_path)
    assert path.read_text(encoding="utf-8") == text


def test_rewrite_legacy_path_only_moves_the_retired_root() -> None:
    assert cutover._rewrite_legacy_path(f"{LEGACY}/a/b.yaml") == f"{NEW}/a/b.yaml"
    assert cutover._rewrite_legacy_path(".kittify\\doctrine\\a\\b.yaml") == f"{NEW}/a/b.yaml"
    assert cutover._rewrite_legacy_path("packs/doctrine-foo") is None
    assert cutover._rewrite_legacy_path(f"{LEGACY}-other/a") is None
    assert cutover._rewrite_legacy_path(3) is None


# --------------------------------------------------------------------------- #
# Report mapping
# --------------------------------------------------------------------------- #


def test_report_maps_onto_migration_result() -> None:
    report = CutoverReport(
        moved=["a -> b"],
        rewritten=["f: k"],
        kept_for_review=["f: kept"],
        matches_minimal=["m"],
        skills_kept=["s"],
        restore_hints=["set it back"],
        preserved_paths=["p"],
    )
    result = report.to_migration_result(dry_run=False)
    assert result.success and not result.errors
    assert json.loads(result.changes_made[0]) == {**dict.fromkeys(REPORT_KEYS, []), **report.as_dict()}
    assert tuple(report.as_dict()) == REPORT_KEYS
    assert result.changes_made[1:] == ["Moved a -> b", "Rewrote f: k"]
    assert result.warnings == ["Kept for review: f: kept", "Matches preset minimal, kept: m", "Kept edited skill copy: s", "set it back"]
    assert result.manual_review_required and result.preserved_paths == ["p"]
    dry = report.to_migration_result(dry_run=True)
    assert dry.changes_made[1:] == ["Would move a -> b", "Would rewrite f: k"]
    failed = CutoverReport(errors=["x"]).to_migration_result(dry_run=False)
    assert not failed.success and failed.errors == ["x"] and not failed.manual_review_required
    assert CutoverReport(kept_for_review=["k"]).is_actionable() is False
    assert CutoverReport(errors=["e"]).is_actionable() is True


# --------------------------------------------------------------------------- #
# Selection and recording (registry + runner)
# --------------------------------------------------------------------------- #


def _stamp(project: Path, version: str, *, recorded: str | None = None) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    metadata = ProjectMetadata(version=version, initialized_at=datetime(2026, 1, 1), python_version="3.11", platform="t", platform_version="t")
    if recorded is not None:
        metadata.record_migration(CUTOVER_ID, recorded)
    metadata.save(kittify)


@pytest.fixture
def registry() -> None:
    auto_discover_migrations()


@pytest.mark.usefixtures("registry")
def test_cutover_is_selected_first_on_a_legacy_project(tmp_path: Path) -> None:
    _legacy_tree(tmp_path)
    _stamp(tmp_path, "3.1.0")
    applicable = MigrationRegistry.get_applicable("3.1.0", "4.0.0rc6", tmp_path)
    assert applicable[0].migration_id == CUTOVER_ID
    assert sum(m.migration_id == CUTOVER_ID for m in applicable) == 1


@pytest.mark.usefixtures("registry")
def test_cutover_is_selected_for_a_project_stamped_above_its_target(tmp_path: Path) -> None:
    _legacy_tree(tmp_path)
    _stamp(tmp_path, "4.0.1")
    assert [m.migration_id for m in MigrationRegistry.get_applicable("4.0.1", "4.0.1", tmp_path)][:1] == [CUTOVER_ID]


@pytest.mark.usefixtures("registry")
def test_cutover_not_selected_on_a_canonical_project(tmp_path: Path) -> None:
    _write(tmp_path, f"{NEW}/graph.yaml", "nodes: []\n")
    _stamp(tmp_path, "4.0.0rc6")
    assert CUTOVER_ID not in [m.migration_id for m in MigrationRegistry.get_applicable("4.0.0rc6", "4.0.0rc6", tmp_path)]


@pytest.mark.usefixtures("registry")
def test_recorded_cutover_with_a_replanted_legacy_root_runs_again(tmp_path: Path) -> None:
    """A pulled checkout brings ``.kittify/doctrine/x.md`` back after the cutover was recorded."""
    _stamp(tmp_path, "4.0.0rc6", recorded="success")
    _write(tmp_path, f"{LEGACY}/x.md", "# planted\n")
    result = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert result.success, result.errors
    assert CUTOVER_ID in result.migrations_applied
    assert (tmp_path / NEW / "x.md").read_text(encoding="utf-8") == "# planted\n"
    assert detect_legacy_charter_layout(tmp_path) == ()


@pytest.mark.usefixtures("registry")
def test_runner_does_not_record_a_refused_cutover(tmp_path: Path) -> None:
    _legacy_tree(tmp_path)
    _write(tmp_path, f"{NEW}/graph.yaml", "nodes: [diverged]\n")
    _stamp(tmp_path, "4.0.0rc6")
    metadata_before = (tmp_path / ".kittify" / "metadata.yaml").read_bytes()
    result = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert not result.success
    assert any("graph.yaml" in error for error in result.errors)
    assert (tmp_path / ".kittify" / "metadata.yaml").read_bytes() == metadata_before
    assert json.loads(result.migration_results[CUTOVER_ID].changes_made[0])["errors"]


def test_migration_identity() -> None:
    migration = CharterPackCutoverMigration()
    assert migration.migration_id == CUTOVER_ID
    assert migration.runs_first is True and migration.runs_on_worktrees is False
    assert migration.target_version == "4.0.0rc6"
    assert migration.can_apply(Path(".")) == (True, "")


# --------------------------------------------------------------------------- #
# An unreadable .gitignore (review cycle 1, finding 3)
# --------------------------------------------------------------------------- #

_UNREADABLE_GITIGNORE_KINDS = ("symlink", "non_utf8", "directory")


def _plant_unreadable_gitignore(project: Path, kind: str) -> None:
    gitignore = project / ".gitignore"
    if kind == "symlink":
        _write(project, "real-gitignore", f"{LEGACY}/**\n")
        gitignore.symlink_to("real-gitignore")
    elif kind == "non_utf8":
        gitignore.write_bytes(b"\xff\xfe" + f"{LEGACY}/**\n\xe9\n".encode("latin-1"))
    else:
        (gitignore / "nested").mkdir(parents=True)


def _canonical_project(project: Path) -> None:
    _write(project, ".kittify/config.yaml", "charter_packs:\n  org:\n    packs: []\n")
    _write(project, f"{NEW}/graph.yaml", "nodes: []\n")
    _stamp(project, "4.0.0rc6")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink")
@pytest.mark.parametrize("kind", _UNREADABLE_GITIGNORE_KINDS)
@pytest.mark.usefixtures("registry")
def test_unreadable_gitignore_does_not_select_a_canonical_project(tmp_path: Path, kind: str) -> None:
    _canonical_project(tmp_path)
    _plant_unreadable_gitignore(tmp_path, kind)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is False
    assert migration.structural_detect(tmp_path) is False
    assert CUTOVER_ID not in [m.migration_id for m in MigrationRegistry.get_applicable("4.0.0rc6", "4.0.0rc6", tmp_path)]
    result = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert result.success, result.errors
    assert CUTOVER_ID not in result.migrations_applied


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink")
@pytest.mark.parametrize("kind", _UNREADABLE_GITIGNORE_KINDS)
@pytest.mark.usefixtures("registry")
def test_unreadable_gitignore_on_a_legacy_project_is_kept_for_review(tmp_path: Path, kind: str) -> None:
    files = _legacy_tree(tmp_path)
    _stamp(tmp_path, "4.0.0rc6")
    _plant_unreadable_gitignore(tmp_path, kind)
    before = _digest(tmp_path)
    result = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert result.success, result.errors
    assert CUTOVER_ID in result.migrations_applied
    assert sorted(p.relative_to(tmp_path / NEW).as_posix() for p in (tmp_path / NEW).rglob("*") if p.is_file()) == files
    report = _report(result.migration_results[CUTOVER_ID])
    assert report["rewritten"] == []
    assert len(report["kept_for_review"]) == 1
    assert report["kept_for_review"][0].startswith(".gitignore could not be read safely (")
    assert f"check it for {LEGACY} rules by hand" in report["kept_for_review"][0]
    # The unreadable .gitignore (and a symlink's target) is left exactly as it was.
    after = _digest(tmp_path)
    assert {k: v for k, v in after.items() if k in {".gitignore", "real-gitignore"}} == {k: v for k, v in before.items() if k in {".gitignore", "real-gitignore"}}
    assert (tmp_path / ".gitignore").is_dir() is (kind == "directory")


def test_gitignore_write_failure_is_a_named_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, ".gitignore", f"{LEGACY}/**\n")

    def _refuse(path: Path, content: str) -> None:
        raise PermissionError(f"Permission denied: {path}")

    monkeypatch.setattr(cutover, "write_gitignore_text", _refuse)
    result = _apply(tmp_path)
    assert not result.success
    denied = f"Permission denied: {tmp_path / '.gitignore'}"
    assert result.errors == [f".gitignore could not be written ({denied}); make it writable, then run `spec-kitty upgrade` again"]
    assert _report(result)["rewritten"] == []
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == f"{LEGACY}/**\n"


# --------------------------------------------------------------------------- #
# Totality under EACCES (review cycle 1, finding 4)
# --------------------------------------------------------------------------- #


def _deny_kittify(project: Path, monkeypatch: pytest.MonkeyPatch, probe: str) -> None:
    """Make one filesystem probe raise ``PermissionError`` for every path under ``.kittify``."""
    from specify_cli.migration import legacy_charter_layout as layout

    kittify = project / ".kittify"

    def under_kittify(path: Any) -> bool:
        return isinstance(path, (str, os.PathLike)) and Path(path).is_relative_to(kittify)

    def wrap(real: Any) -> Any:
        def denied(target: Any, *args: Any, **kwargs: Any) -> Any:
            if under_kittify(target):
                raise PermissionError(13, "Permission denied", str(target))
            return real(target, *args, **kwargs)

        return denied

    if probe == "os.lstat":
        monkeypatch.setattr(layout.os, "lstat", wrap(os.lstat))
    else:
        monkeypatch.setattr(Path, probe, wrap(getattr(Path, probe)))


_PROBES = ("os.lstat", "stat", "lstat", "is_dir", "is_symlink", "exists", "is_file", "read_bytes", "read_text")


@pytest.mark.parametrize("probe", _PROBES)
def test_detect_is_total_when_a_probe_raises_eacces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str) -> None:
    _legacy_tree(tmp_path)
    _write(tmp_path, ".kittify/config.yaml", "doctrine:\n  org:\n    packs: []\n")
    _deny_kittify(tmp_path, monkeypatch, probe)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    assert migration.structural_detect(tmp_path) is True


def test_apply_names_an_uninspectable_legacy_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _legacy_tree(tmp_path)
    _deny_kittify(tmp_path, monkeypatch, "os.lstat")
    with pytest.raises(cutover.MigrationStateUnreadableError, match=r"\.kittify/doctrine could not be inspected"):
        _apply(tmp_path)


# --------------------------------------------------------------------------- #
# A retired key kept for review does not re-select a recorded cutover (finding 5)
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("registry")
def test_kept_legacy_org_does_not_reselect_a_recorded_cutover(tmp_path: Path) -> None:
    config = _write(tmp_path, ".kittify/config.yaml", "charter_packs: oops\ndoctrine:\n  org:\n    packs: []\n")
    _stamp(tmp_path, "4.0.0rc6")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True  # first application: selected
    first = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert first.success, first.errors
    assert CUTOVER_ID in first.migrations_applied
    assert "charter_packs is not a mapping" in _report(first.migration_results[CUTOVER_ID])["kept_for_review"][0]
    # Recorded, and the kept key is not actionable: not re-selected on the next upgrade.
    assert detect_legacy_charter_layout(tmp_path) == ("legacy_org_packs_key",)
    assert migration.structural_detect(tmp_path) is False
    assert migration.reselect_when_recorded(tmp_path) is False
    kept = config.read_bytes()
    second = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert second.success, second.errors
    assert CUTOVER_ID not in second.migrations_applied
    assert config.read_bytes() == kept
    # Once the operator fixes charter_packs, the key is actionable and the cutover is selected again.
    config.write_text("charter_packs: {}\ndoctrine:\n  org:\n    packs: []\n", encoding="utf-8")
    assert migration.structural_detect(tmp_path) is True
    again = MigrationRunner(tmp_path).upgrade("4.0.0rc6", include_worktrees=False)
    assert again.success, again.errors
    assert CUTOVER_ID in again.migrations_applied
    assert detect_legacy_charter_layout(tmp_path) == ()


@pytest.mark.usefixtures("registry")
def test_recorded_cutover_with_a_replanted_config_key_runs_again(tmp_path: Path) -> None:
    _stamp(tmp_path, "4.0.0rc6", recorded="success")
    _write(tmp_path, ".kittify/config.yaml", "tracker:\n  doctrine:\n    mode: external_authoritative\n")
    assert CharterPackCutoverMigration().structural_detect(tmp_path) is True
    assert [m.migration_id for m in MigrationRegistry.get_applicable("4.0.0rc6", "4.0.0rc6", tmp_path)][:1] == [CUTOVER_ID]
