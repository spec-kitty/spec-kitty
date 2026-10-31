"""#6767 -- the ``charter synthesize --json`` envelope wraps the one strict sidecar reader.

The envelope is a strict-JSON contract: it never raises, and a damaged ownership record costs
it an ``artifact_id``, never its four-field shape. These cases drive
``_load_written_artifacts_from_manifest`` (the pre-existing entry point) directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.synthesizer.manifest import MANIFEST_PATH, ManifestArtifactEntry, SynthesisManifest, dump_yaml, finalize_manifest
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.provenance import ProvenanceEntry
from charter.activation.synthesizer.provenance import dump_yaml as dump_provenance
from specify_cli.cli.commands.charter._synthesis import _load_written_artifacts_from_manifest

pytestmark = [pytest.mark.fast]

_RUN_ID = "01KPE222TESTRUNID0000000001"
_FIELDS = {"path", "kind", "slug", "artifact_id"}


@pytest.fixture
def guard(tmp_path: Path) -> PathGuard:
    return PathGuard(tmp_path, extra_allowed_prefixes=[tmp_path])


def _entry(kind: str, slug: str) -> ManifestArtifactEntry:
    return ManifestArtifactEntry(
        kind=kind,  # type: ignore[arg-type]  # parametrised over the literal kinds
        slug=slug,
        path=f".kittify/charter-packs/{kind}/{slug}.{kind}.yaml",
        provenance_path=f".kittify/charter/provenance/{kind}-{slug}.yaml",
        content_hash="a" * 64,
    )


def _write_manifest(repo_root: Path, guard: PathGuard, entries: list[ManifestArtifactEntry]) -> None:
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-04-17T12:00:00+00:00",
            run_id=_RUN_ID,
            adapter_id="fixture",
            adapter_version="1.0.0",
            synthesizer_version="3.2.0a5",
            manifest_hash="0" * 64,
            artifacts=entries,
        )
    )
    path = repo_root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_yaml(manifest, path, guard)


def _write_sidecar(repo_root: Path, guard: PathGuard, kind: str, slug: str, urn: str, *, adapter_id: str = "fixture") -> None:
    sidecar = ProvenanceEntry(
        artifact_urn=urn,
        artifact_kind=kind,
        artifact_slug=slug,
        artifact_content_hash="a" * 64,
        inputs_hash="b" * 64,
        adapter_id=adapter_id,
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        source_section="mission_type",
        source_urns=[],
        source_input_ids=[],
        generated_at="2026-04-17T12:00:00+00:00",
        produced_at="2026-04-17T12:00:00+00:00",
        corpus_snapshot_id="(none)",
        synthesis_run_id=_RUN_ID,
    )
    path = repo_root / f".kittify/charter/provenance/{kind}-{slug}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_provenance(sidecar, path, guard)


def test_directive_artifact_id_is_the_urn_id_segment(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    _write_sidecar(tmp_path, guard, "directive", "project-intent-directive", "directive:PROJECT_001")

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert set(artifact) == _FIELDS
    assert artifact["artifact_id"] == "PROJECT_001"


def test_non_directive_entry_has_no_artifact_id(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])
    _write_sidecar(tmp_path, guard, "tactic", "review-policy-tactic", "tactic:review-policy-tactic")

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert artifact["artifact_id"] is None
    assert artifact["kind"] == "tactic"


def test_missing_sidecar_degrades_to_no_id_without_raising(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert set(artifact) == _FIELDS
    assert artifact["artifact_id"] is None


def test_corrupt_sidecar_degrades_to_no_id_without_raising(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    sidecar = tmp_path / ".kittify/charter/provenance/directive-project-intent-directive.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("artifact_urn: [unclosed\n", encoding="utf-8")

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert artifact["artifact_id"] is None


def test_sidecar_urn_of_another_kind_degrades_to_no_id(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    _write_sidecar(tmp_path, guard, "directive", "project-intent-directive", "tactic:NOT_A_DIRECTIVE")

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert artifact["artifact_id"] is None


def test_direct_write_registration_keeps_its_artifact_id(tmp_path: Path, guard: PathGuard) -> None:
    """The envelope reports what the manifest committed, not the ownership verdict (#6510 stays intact)."""
    _write_manifest(tmp_path, guard, [_entry("directive", "team-001")])
    _write_sidecar(tmp_path, guard, "directive", "team-001", "directive:TEAM_001", adapter_id="project-direct-write")

    [artifact] = _load_written_artifacts_from_manifest(tmp_path)

    assert artifact["artifact_id"] == "TEAM_001"


def test_absent_manifest_yields_an_empty_envelope(tmp_path: Path) -> None:
    assert _load_written_artifacts_from_manifest(tmp_path) == []


def test_corrupt_manifest_yields_an_empty_envelope(tmp_path: Path) -> None:
    path = tmp_path / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("artifacts: [this is: not a manifest\n", encoding="utf-8")

    assert _load_written_artifacts_from_manifest(tmp_path) == []


def test_the_display_module_does_not_parse_the_sidecar(tmp_path: Path) -> None:
    """The sidecar shape has one parser: the display module must not carry its own."""
    import ast

    source = (Path(__file__).resolve().parents[5] / "src/specify_cli/cli/commands/charter/_synthesis.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # A raw YAML parse is always a second parser; a ``load_yaml`` on a sidecar path is too.
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None)
        raw_parse = name in {"YAML", "safe_load"}
        sidecar_load = name == "load_yaml" and any("provenance" in ast.unparse(arg) for arg in node.args)
        if raw_parse or sidecar_load:
            offenders.append(node.lineno)

    assert offenders == [], f"_synthesis.py parses the sidecar itself at lines {offenders}; use the strict sidecar reader"
