"""#6443 / FR-008: the shared helper that converges a legacy ``mission-type-scope-directive``.

Covers both provenance shapes a project can carry, every path of FR-008, the manifest hashes,
the bundle restamp, idempotence, collision refusal (nothing changed), dry run and fail-closed
reads. The ``synthesize`` / ``resynthesize`` pre-step is pinned in
``tests/agent/cli/commands/test_charter_synthesize_cli.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.api import (
    LegacyRenameRefusedError,
    RenameReport,
    rename_legacy_project_intent_directive,
)
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    SynthesisManifest,
    finalize_manifest,
    load_yaml,
    verify,
    verify_manifest_hash,
)
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import compute_bundle_content_hash

pytestmark = [pytest.mark.unit, pytest.mark.regression]

_LEGACY = "001-mission-type-scope-directive.directive.yaml"
_NEW = "001-project-intent-directive.directive.yaml"
_LEGACY_STEM = "001-mission-type-scope-directive"
_NEW_STEM = "001-project-intent-directive"
_PACK_DIR = Path(".kittify") / "charter-packs" / "directive"
_GENERATED_DIR = Path(".kittify") / "charter" / "generated" / "directives"
_PROVENANCE_DIR = Path(".kittify") / "charter" / "provenance"
_GRAPH = Path(".kittify") / "charter-packs" / "graph.yaml"
_CHARTER_YAML = Path(".kittify") / "charter" / "charter.yaml"
_CONFIG = Path(".kittify") / "config.yaml"
_BODY = "id: PROJECT_001\ntitle: Mission Type Scope Directive\nintent: keep the scope\nschema_version: '1.0'\n"
#: SHA-256 of ``_BODY`` (the manifest records the raw artifact digest; ``verify`` re-checks it).
_BODY_SHA256 = "2efdbf7523ae2273e2bcc2f9780de41a7a3e23a56b7e6d4adbc99fb175f2a8d0"
_OLD_PATH = f".kittify/charter-packs/directive/{_LEGACY}"
_NEW_PATH = f".kittify/charter-packs/directive/{_NEW}"


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_yaml(data))


def _load(path: Path) -> Any:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _provenance(shape: str) -> tuple[str, dict[str, Any]]:
    """``(file name, content)`` of the directive's provenance sidecar in the given shape."""
    base: dict[str, Any] = {
        "adapter_id": "project-direct-write",
        "artifact_kind": "directive",
        "artifact_urn": "directive:PROJECT_001",
        "schema_version": "2",
        "source_urns": [],
    }
    if shape == "direct-write":
        return "directive-project-001.yaml", {**base, "artifact_slug": "project-001", "source_input_ids": [_OLD_PATH], "source_section": _OLD_PATH}
    slug_keyed = {"artifact_slug": "mission-type-scope-directive", "source_input_ids": ["mission_type"], "source_section": "mission_type"}
    return "directive-mission-type-scope-directive.yaml", {**base, **slug_keyed}


def _legacy_project(root: Path, *, shape: str = "direct-write", pointer: bool = True) -> None:
    """A project carrying the legacy slug everywhere FR-008 lists."""
    (root / _PACK_DIR).mkdir(parents=True)
    (root / _PACK_DIR / _LEGACY).write_text(_BODY, encoding="utf-8")
    (root / _GENERATED_DIR).mkdir(parents=True)
    (root / _GENERATED_DIR / _LEGACY).write_text(_BODY, encoding="utf-8")
    prov_name, prov = _provenance(shape)
    _dump(root / _PROVENANCE_DIR / prov_name, prov)
    slug = prov["artifact_slug"]
    entry = ManifestArtifactEntry(
        kind="directive",
        slug=slug,
        path=_OLD_PATH,
        provenance_path=f".kittify/charter/provenance/{prov_name}",
        content_hash=_BODY_SHA256,
    )
    (root / _CHARTER_YAML).write_text(f"activated_directives:\n- {_LEGACY_STEM}\n- DIRECTIVE_003\n" if pointer else "x: 1\n", encoding="utf-8")
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-10-19T00:00:00+00:00",
            run_id="run",
            adapter_id="generated",
            adapter_version="1",
            synthesizer_version="4.0.0rc8",
            manifest_hash="0" * 64,
            artifacts=[entry],
            bundle_content_hash=compute_bundle_content_hash(root),
        )
    )
    _dump(root / MANIFEST_PATH, manifest.model_dump(mode="python"))
    _dump(
        root / _GRAPH,
        {
            "schema_version": "1.0",
            "nodes": [
                {"urn": "directive:PROJECT_001", "kind": "directive", "label": "Mission Type Scope Directive"},
                {"urn": "mission_type:software-dev", "kind": "mission_type", "label": "Software Dev"},
            ],
            "edges": [{"source": "directive:PROJECT_001", "target": "mission_type:software-dev", "relation": "requires"}],
        },
    )
    if pointer:
        (root / _CONFIG).write_text("charter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    else:
        (root / _CONFIG).write_text(f"activated_directives:\n- {_LEGACY_STEM}\n", encoding="utf-8")


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(params=["direct-write", "slug-keyed"])
def legacy_root(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    _legacy_project(tmp_path, shape=request.param)
    return tmp_path


def test_every_fr008_path_moves_and_the_body_is_untouched(legacy_root: Path) -> None:
    report = rename_legacy_project_intent_directive(legacy_root)

    assert isinstance(report, RenameReport) and report.pending and not report.dry_run
    for directory in (_PACK_DIR, _GENERATED_DIR):
        assert not (legacy_root / directory / _LEGACY).exists()
        assert (legacy_root / directory / _NEW).read_text(encoding="utf-8") == _BODY
    assert sorted(p.name for p in (legacy_root / _PACK_DIR).iterdir()) == [_NEW]


def test_manifest_entry_and_hashes_are_valid(legacy_root: Path) -> None:
    rename_legacy_project_intent_directive(legacy_root)

    manifest = load_yaml(legacy_root / MANIFEST_PATH)
    (entry,) = manifest.artifacts
    assert entry.path == _NEW_PATH
    verify_manifest_hash(manifest)
    verify(manifest, legacy_root)
    assert (legacy_root / entry.provenance_path).is_file()
    if entry.slug != "project-001":
        assert entry.slug == "project-intent-directive"
        assert entry.provenance_path.endswith("directive-project-intent-directive.yaml")


def test_bundle_hash_is_restamped_once_the_stem_tokens_moved(legacy_root: Path) -> None:
    before = load_yaml(legacy_root / MANIFEST_PATH).bundle_content_hash
    rename_legacy_project_intent_directive(legacy_root)

    assert _load(legacy_root / _CHARTER_YAML)["activated_directives"] == [_NEW_STEM, "DIRECTIVE_003"]
    after = load_yaml(legacy_root / MANIFEST_PATH).bundle_content_hash
    assert after == compute_bundle_content_hash(legacy_root) != before


def test_direct_write_provenance_paths_are_rewritten_and_slug_shape_is_moved(legacy_root: Path) -> None:
    rename_legacy_project_intent_directive(legacy_root)

    files = sorted(p.name for p in (legacy_root / _PROVENANCE_DIR).iterdir())
    if files == ["directive-project-001.yaml"]:
        data = _load(legacy_root / _PROVENANCE_DIR / files[0])
        assert data["source_input_ids"] == [_NEW_PATH]
        assert data["source_section"] == _NEW_PATH
        assert data["artifact_slug"] == "project-001"
    else:
        assert files == ["directive-project-intent-directive.yaml"]
        assert _load(legacy_root / _PROVENANCE_DIR / files[0])["artifact_slug"] == "project-intent-directive"


def test_id_urn_and_interview_label_are_unchanged_and_the_overlay_is_converged(legacy_root: Path) -> None:
    rename_legacy_project_intent_directive(legacy_root)

    assert _load(legacy_root / _PACK_DIR / _NEW)["id"] == "PROJECT_001"
    graph = _load(legacy_root / _GRAPH)
    directive = next(n for n in graph["nodes"] if n["urn"] == "directive:PROJECT_001")
    assert directive["label"] == "Project Intent Directive"
    assert graph["edges"] == []
    assert any(n["urn"] == "mission_type:software-dev" for n in graph["nodes"])
    provenance = next((legacy_root / _PROVENANCE_DIR).iterdir())
    assert _load(provenance)["artifact_urn"] == "directive:PROJECT_001"


def test_a_second_run_is_a_no_op(legacy_root: Path) -> None:
    rename_legacy_project_intent_directive(legacy_root)
    settled = _tree(legacy_root)

    report = rename_legacy_project_intent_directive(legacy_root)

    assert not report.pending and report.actions == ()
    assert _tree(legacy_root) == settled


def test_stem_tokens_in_a_legacy_config_without_a_charter_pointer_are_rewritten(tmp_path: Path) -> None:
    _legacy_project(tmp_path, pointer=False)

    rename_legacy_project_intent_directive(tmp_path)

    assert _load(tmp_path / _CONFIG)["activated_directives"] == [_NEW_STEM]


def test_a_target_collision_is_refused_and_nothing_changes(legacy_root: Path) -> None:
    (legacy_root / _PACK_DIR / _NEW).write_text("id: PROJECT_001\n", encoding="utf-8")
    before = _tree(legacy_root)

    with pytest.raises(LegacyRenameRefusedError, match="already exists"):
        rename_legacy_project_intent_directive(legacy_root)

    assert _tree(legacy_root) == before


def test_a_provenance_collision_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    _legacy_project(tmp_path, shape="slug-keyed")
    _dump(tmp_path / _PROVENANCE_DIR / "directive-project-intent-directive.yaml", {"artifact_slug": "project-intent-directive"})
    before = _tree(tmp_path)

    with pytest.raises(LegacyRenameRefusedError, match="already exists"):
        rename_legacy_project_intent_directive(tmp_path)

    assert _tree(tmp_path) == before


def test_an_interrupted_provenance_move_is_resumed_by_the_next_run(tmp_path: Path) -> None:
    """The new sidecar was written but the old one not yet unlinked: the re-run removes the old one."""
    _legacy_project(tmp_path, shape="slug-keyed")
    old = tmp_path / _PROVENANCE_DIR / "directive-mission-type-scope-directive.yaml"
    new = tmp_path / _PROVENANCE_DIR / "directive-project-intent-directive.yaml"
    _dump(new, {**_load(old), "artifact_slug": "project-intent-directive"})

    rename_legacy_project_intent_directive(tmp_path)

    assert not old.exists()
    assert sorted(p.name for p in (tmp_path / _PROVENANCE_DIR).glob("directive-*.yaml")) == [new.name]
    assert _load(new)["artifact_slug"] == "project-intent-directive"


def test_a_manifest_slug_collision_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    _legacy_project(tmp_path, shape="slug-keyed")
    manifest = load_yaml(tmp_path / MANIFEST_PATH)
    twin = manifest.artifacts[0].model_copy(update={"slug": "project-intent-directive", "path": ".kittify/charter-packs/directive/002-other.directive.yaml"})
    _dump(tmp_path / MANIFEST_PATH, finalize_manifest(manifest.model_copy(update={"artifacts": [*manifest.artifacts, twin]})).model_dump(mode="python"))
    before = _tree(tmp_path)

    with pytest.raises(LegacyRenameRefusedError, match="same slug"):
        rename_legacy_project_intent_directive(tmp_path)

    assert _tree(tmp_path) == before


def test_dry_run_reports_and_writes_nothing(legacy_root: Path) -> None:
    before = _tree(legacy_root)

    report = rename_legacy_project_intent_directive(legacy_root, dry_run=True)

    assert report.dry_run and report.pending
    assert any(_LEGACY in action for action in report.actions)
    assert _tree(legacy_root) == before


@pytest.mark.parametrize("victim", [MANIFEST_PATH, _GRAPH])
def test_an_unreadable_input_refuses_with_a_clear_message(tmp_path: Path, victim: Path) -> None:
    _legacy_project(tmp_path)
    (tmp_path / victim).write_text("{unclosed: [", encoding="utf-8")
    before = _tree(tmp_path)

    with pytest.raises(LegacyRenameRefusedError, match="is unreadable"):
        rename_legacy_project_intent_directive(tmp_path)

    assert _tree(tmp_path) == before


def test_an_unreadable_overlay_without_legacy_state_is_left_to_its_own_reader(tmp_path: Path) -> None:
    """A corrupt overlay is refused with its own actionable message by the command that reads it."""
    (tmp_path / _GRAPH).parent.mkdir(parents=True)
    (tmp_path / _GRAPH).write_text("{unclosed: [", encoding="utf-8")

    assert not rename_legacy_project_intent_directive(tmp_path).pending


def test_a_dangling_charter_pointer_is_left_to_its_own_reader(tmp_path: Path) -> None:
    """``charter:`` naming a missing file must not crash the preflight (dry-run, migration ``detect()``)."""
    (tmp_path / _CONFIG).parent.mkdir(parents=True)
    (tmp_path / _CONFIG).write_text("charter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    before = _tree(tmp_path)

    report = rename_legacy_project_intent_directive(tmp_path, dry_run=True)

    assert not report.pending
    assert _tree(tmp_path) == before


def test_a_project_without_legacy_state_is_untouched(tmp_path: Path) -> None:
    (tmp_path / _PACK_DIR).mkdir(parents=True)
    (tmp_path / _PACK_DIR / _NEW).write_text(_BODY, encoding="utf-8")
    before = _tree(tmp_path)

    report = rename_legacy_project_intent_directive(tmp_path)

    assert not report.pending
    assert _tree(tmp_path) == before


def test_an_interrupted_run_is_finished_by_the_next_one(legacy_root: Path) -> None:
    """The artifact moved but the manifest did not: every step still recognises its own legacy state."""
    (legacy_root / _PACK_DIR / _LEGACY).replace(legacy_root / _PACK_DIR / _NEW)

    rename_legacy_project_intent_directive(legacy_root)

    verify(load_yaml(legacy_root / MANIFEST_PATH), legacy_root)
    assert not rename_legacy_project_intent_directive(legacy_root).pending


def test_a_stale_bundle_hash_is_restamped_even_with_nothing_to_rename(legacy_root: Path) -> None:
    """An interrupted run can leave the rename done but the stamp stale: the next run self-heals it."""
    rename_legacy_project_intent_directive(legacy_root)
    with (legacy_root / _CHARTER_YAML).open("a", encoding="utf-8") as handle:
        handle.write("# edited after the rename was interrupted\n")
    stale = load_yaml(legacy_root / MANIFEST_PATH).bundle_content_hash
    assert stale != compute_bundle_content_hash(legacy_root), "control: the stamp is stale"

    dry = rename_legacy_project_intent_directive(legacy_root, dry_run=True)
    assert not dry.pending
    assert load_yaml(legacy_root / MANIFEST_PATH).bundle_content_hash == stale, "a dry run writes nothing"

    report = rename_legacy_project_intent_directive(legacy_root)

    assert not report.pending
    assert load_yaml(legacy_root / MANIFEST_PATH).bundle_content_hash == compute_bundle_content_hash(legacy_root)


def test_an_unreadable_manifest_without_legacy_state_is_left_to_its_own_reader(tmp_path: Path) -> None:
    (tmp_path / MANIFEST_PATH).parent.mkdir(parents=True)
    (tmp_path / MANIFEST_PATH).write_text("{unclosed: [", encoding="utf-8")

    assert not rename_legacy_project_intent_directive(tmp_path).pending
