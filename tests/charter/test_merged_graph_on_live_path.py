"""FR-016 regression: :func:`charter.offering.drg.validator.assert_valid` is invoked
on every live path that loads the DRG.

Ensures the Phase 0 merged-graph validator is not bypassed as the live
charter resolver / compiler evolves through Phase 1 cutovers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from charter.activation._drg_helpers import load_validated_graph
from charter.offering.drg.loader import load_graph_or_dir
from charter.offering.drg.validator import DRGValidationError

pytestmark = pytest.mark.fast


def _built_in_from(root: Path) -> Any:
    """Load a fixture built-in graph from *root* (a fake doctrine directory).

    WP03 (mission #2680) routed ``load_validated_graph`` through the canonical
    :func:`charter.offering.drg.loader.load_built_in_graph` seam, so tests inject the
    built-in layer by patching that seam rather than the retired
    ``resolve_offering_root`` import.
    """
    return load_graph_or_dir(root)


def test_load_validated_graph_invokes_assert_valid(tmp_path: Path) -> None:
    """Loading the validated DRG via the shared helper must call
    :func:`assert_valid`."""
    built_in_root = tmp_path / "doctrine"
    built_in_root.mkdir()
    (built_in_root / "graph.yaml").write_text(
        "schema_version: '1.0'\n"
        "generated_at: '2026-04-14T00:00:00Z'\n"
        "generated_by: test\n"
        "nodes: []\n"
        "edges: []\n",
        encoding="utf-8",
    )

    with patch(
        "charter.activation._drg_helpers.load_built_in_graph",
        side_effect=lambda: _built_in_from(built_in_root),
    ), patch("charter.activation._drg_helpers.assert_valid") as mock_validator:
        load_validated_graph(tmp_path)
    assert mock_validator.called, "assert_valid() was not called"


def test_load_validated_graph_overlays_project_graph(tmp_path: Path) -> None:
    """When a project-overlay ``.kittify/charter-packs/graph.yaml`` exists, the
    helper merges it onto the shipped graph before validating."""
    built_in_root = tmp_path / "doctrine"
    built_in_root.mkdir()
    (built_in_root / "graph.yaml").write_text(
        "schema_version: '1.0'\n"
        "generated_at: '2026-04-14T00:00:00Z'\n"
        "generated_by: test\n"
        "nodes:\n"
        "- {urn: 'directive:shipped-one', kind: directive}\n"
        "edges: []\n",
        encoding="utf-8",
    )

    project_graph_dir = tmp_path / ".kittify" / "charter-packs"
    project_graph_dir.mkdir(parents=True)
    (project_graph_dir / "graph.yaml").write_text(
        "schema_version: '1.0'\n"
        "generated_at: '2026-04-14T00:00:00Z'\n"
        "generated_by: test\n"
        "nodes:\n"
        "- {urn: 'directive:project-one', kind: directive}\n"
        "edges: []\n",
        encoding="utf-8",
    )

    with patch(
        "charter.activation._drg_helpers.load_built_in_graph",
        side_effect=lambda: _built_in_from(built_in_root),
    ):
        graph = load_validated_graph(tmp_path)

    urns = {n.urn for n in graph.nodes}
    assert "directive:shipped-one" in urns
    assert "directive:project-one" in urns


def test_load_validated_graph_rejects_invalid_merge(tmp_path: Path) -> None:
    """A corrupted (e.g. duplicate-edge) merged graph must raise via
    :func:`assert_valid`."""
    built_in_root = tmp_path / "doctrine"
    built_in_root.mkdir()
    # Dangling edge target -> should fail validation.
    (built_in_root / "graph.yaml").write_text(
        "schema_version: '1.0'\n"
        "generated_at: '2026-04-14T00:00:00Z'\n"
        "generated_by: test\n"
        "nodes:\n"
        "- {urn: 'directive:a', kind: directive}\n"
        "edges:\n"
        "- {source: 'directive:a', target: 'directive:missing', relation: requires}\n",
        encoding="utf-8",
    )
    with patch(
        "charter.activation._drg_helpers.load_built_in_graph",
        side_effect=lambda: _built_in_from(built_in_root),
    ):
        with pytest.raises(DRGValidationError, match=r"Dangling target: .*directive:missing"):
            load_validated_graph(tmp_path)


def test_shipped_graph_is_valid() -> None:
    """The shipped built-in DRG passes :func:`assert_valid` today.

    This is the live-path backstop: if the shipped graph regresses into an
    invalid shape (dangling edges, duplicate edges, cycles in ``requires``),
    every downstream charter build will fail loudly instead of silently
    losing artifacts. Routed through the WP03 seam ``load_built_in_graph()`` so
    it stays layout-agnostic across the WP05 monolith->fragment migration (the
    seam raises if no built-in graph source can be loaded).
    """
    from charter.offering.drg.loader import load_built_in_graph
    from charter.offering.drg.validator import assert_valid

    assert_valid(load_built_in_graph())
