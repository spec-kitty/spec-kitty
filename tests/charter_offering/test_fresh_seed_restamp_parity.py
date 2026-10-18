"""Pin: the fresh-project scaffold stamps the single-authority bundle hash (#6366, WP02).

``_synthesize_project_layer`` already re-stamps ``bundle_content_hash`` via
``compute_bundle_content_hash``; this guards that behaviour against regression
and pins FR-006 parity for this repository's committed manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
from charter.bundle import compute_bundle_content_hash
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from specify_cli.cli.commands.charter.authoring import _STUB_TEMPLATES

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_synthesize_project_layer_stamps_authority_hash(tmp_path: Path) -> None:
    from specify_cli.cli.commands.charter import _fresh_project_layer as layer

    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text('schema_version: "2.0.0"\n', encoding="utf-8")
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
    kind = ArtifactKind.DIRECTIVE
    directive_dir = tmp_path / ".kittify" / "charter-packs" / PROJECT_KIND_DIRS[kind]
    directive_dir.mkdir(parents=True)
    (directive_dir / kind.glob_pattern.replace("*", "CHANGE_FREEZE")).write_text(
        _STUB_TEMPLATES[kind].format(artifact_id="CHANGE_FREEZE").replace("TODO", "Operational"),
        encoding="utf-8",
    )

    result = layer._synthesize_project_layer(tmp_path, dry_run=False)

    assert result is not None and result["success"] is True
    manifest = load_yaml(tmp_path / MANIFEST_PATH)
    assert manifest.built_in_only is False
    assert manifest.bundle_content_hash == compute_bundle_content_hash(tmp_path)


def test_committed_manifest_matches_recomputed_bundle_hash() -> None:
    """FR-006: the committed manifest of this repository is in parity (PASS)."""
    manifest = load_yaml(_REPO_ROOT / MANIFEST_PATH)
    if manifest.built_in_only:
        pytest.skip("built-in-only seed carries no content hash")
    assert manifest.bundle_content_hash == compute_bundle_content_hash(_REPO_ROOT)


def test_committed_synthesized_drg_freshness_is_fresh() -> None:
    """FR-006: a clean checkout of this repository reports ``synthesized_drg`` fresh."""
    from specify_cli.charter_runtime.freshness.computer import compute_freshness

    assert compute_freshness(_REPO_ROOT).synthesized_drg.state == "fresh"
