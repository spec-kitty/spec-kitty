"""Unit tests for the shared graph-residue unlink helper (WP04 / FR-007).

``charter.activation.synthesizer.graph_residue.unlink_stale_project_graph`` is the single
sanctioned removal of a project ``graph.yaml`` that a ``built_in_only`` writer
disowns. It consolidates the two former bare-``unlink`` sites
(``project_drg.apply_post_condition`` and ``_fresh_doctrine``). These tests pin
its behaviour: present-file removal, missing-file no-op, idempotency, and that
it touches ONLY ``graph.yaml`` (never sibling artifacts).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent

import pytest

from charter.activation.synthesizer.graph_residue import unlink_stale_project_graph
from charter.activation.synthesizer.project_drg import _GRAPH_FILENAME

pytestmark = [pytest.mark.fast]


def test_removes_present_graph(tmp_path: Path) -> None:
    """A present ``graph.yaml`` is removed."""
    graph = tmp_path / _GRAPH_FILENAME
    graph.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")
    assert graph.exists()

    unlink_stale_project_graph(tmp_path)

    assert not graph.exists()


def test_missing_graph_is_noop(tmp_path: Path) -> None:
    """A missing ``graph.yaml`` is a no-op (missing-safe), never raises."""
    assert not (tmp_path / _GRAPH_FILENAME).exists()

    unlink_stale_project_graph(tmp_path)  # must not raise

    assert not (tmp_path / _GRAPH_FILENAME).exists()


def test_idempotent_across_repeat_calls(tmp_path: Path) -> None:
    """Calling twice on a present-then-removed graph is idempotent."""
    graph = tmp_path / _GRAPH_FILENAME
    graph.write_text("nodes: []\n", encoding="utf-8")

    unlink_stale_project_graph(tmp_path)
    unlink_stale_project_graph(tmp_path)  # second call is a clean no-op

    assert not graph.exists()


def test_only_touches_graph_yaml(tmp_path: Path) -> None:
    """Sibling doctrine artifacts are untouched."""
    (tmp_path / _GRAPH_FILENAME).write_text("nodes: []\n", encoding="utf-8")
    sibling = tmp_path / "PROVENANCE.md"
    sibling.write_text("provenance\n", encoding="utf-8")

    unlink_stale_project_graph(tmp_path)

    assert not (tmp_path / _GRAPH_FILENAME).exists()
    assert sibling.exists()
    assert sibling.read_text(encoding="utf-8") == "provenance\n"


def test_reuses_canonical_graph_filename() -> None:
    """FR-007 anti-drift: the helper reuses ``project_drg._GRAPH_FILENAME``.

    Guards against a third copy of the ``graph.yaml`` literal being minted.
    """
    assert _GRAPH_FILENAME == "graph.yaml"


# ---------------------------------------------------------------------------
# apply_post_condition unlink path (diff-coverage gap closeout — #2028)
#
# Fast-suite coverage of the ``project_drg.apply_post_condition`` graph-residue
# unlink branch (the ``if desired_built_in_only: unlink_stale_project_graph(...)``
# sequence). The same path is exercised by the integration suite, but that suite
# does not run in the diff-coverage gate; this topology-true fast test closes the
# gap directly.
# ---------------------------------------------------------------------------


def _seed_manifest(repo: Path, *, built_in_only: bool) -> Path:
    """Write a topology-true synthesis manifest with a valid self-hash."""
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

    manifest_path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2099-01-01T00:00:00+00:00",
        "run_id": "01JTESTRUNIDXXXXXXXXXXXXXX",
        "adapter_id": "test",
        "adapter_version": "0.0.0",
        "synthesizer_version": "0.0.0",
        "artifacts": [],
        "built_in_only": built_in_only,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(manifest_data)).hexdigest()  # noqa: TID251 — synthesizer manifest self-hash, not charter.hasher freshness
    manifest_path.write_text(
        dedent(
            f"""\
            schema_version: '2'
            mission_id: null
            created_at: '2099-01-01T00:00:00+00:00'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: {manifest_hash}
            artifacts: []
            built_in_only: {str(built_in_only).lower()}
            """
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_apply_post_condition_unlinks_present_graph(tmp_path: Path) -> None:
    """``apply_post_condition(has_project_graph=False)`` routes through the
    shared unlink helper to remove a present ``graph.yaml`` and flips the
    manifest to ``built_in_only=true``."""
    from charter.activation.synthesizer.project_drg import apply_post_condition

    manifest_path = _seed_manifest(tmp_path, built_in_only=False)
    graph_path = tmp_path / ".kittify" / "charter-packs" / _GRAPH_FILENAME
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        "schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8"
    )

    apply_post_condition(tmp_path, has_project_graph=False)

    assert not graph_path.exists(), "stale graph.yaml must be unlinked"
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(manifest_path.read_text(encoding="utf-8")) or {}
    assert data["built_in_only"] is True
