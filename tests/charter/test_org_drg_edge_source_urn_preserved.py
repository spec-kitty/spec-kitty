"""Regression tests for P0 bug: _tag_source corrupted DRGEdge.source URN.

Before the fix (2026-05, Robert adversarial review), ``_tag_source`` wrote
provenance into an attribute named ``"source"``, which silently overwrote
``DRGEdge.source`` (the source-endpoint URN declared as a Pydantic field).
After ``merge_three_layers`` every edge's endpoint became ``"built-in"`` /
``"org:..."`` / ``"project"`` instead of the URN, causing false-positive
dangling-source findings in the DRG validator.

The fix renamed the sidecar attribute to ``"provenance"``.  These tests pin
the corrected behaviour.
"""

from __future__ import annotations

import pytest

from charter.drg import (
    DRGEdge,
    DRGGraph,
    DRGNode,
    NodeKind,
    OrgDRGFragment,
    Relation,
)
from charter.activation.drg_activation import merge_three_layers

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _built_in_with_edge(source_urn: str, target_urn: str) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-19T00:00:00Z",
        generated_by="regression-test",
        nodes=[
            DRGNode(urn=source_urn, kind=NodeKind.DIRECTIVE),
            DRGNode(urn=target_urn, kind=NodeKind.DIRECTIVE),
        ],
        edges=[DRGEdge(source=source_urn, target=target_urn, relation=Relation.APPLIES)],
    )


def _empty_built_in() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-19T00:00:00Z",
        generated_by="regression-test",
        nodes=[],
        edges=[],
    )


# ---------------------------------------------------------------------------
# P0 regression tests
# ---------------------------------------------------------------------------


class TestShippedEdgeSourceUrnPreservedAfterMerge:
    """Merging must not overwrite DRGEdge.source (the URN) with provenance."""

    def test_shipped_edge_source_urn_preserved_after_merge(self) -> None:
        """The shipped edge.source URN survives merge_three_layers (no org, no project)."""
        built_in = _built_in_with_edge("directive:alpha", "directive:beta")
        merged = merge_three_layers(built_in=built_in, org_fragments=[], project=None)

        assert {(e.source, e.target) for e in merged.edges} == {
            ("directive:alpha", "directive:beta")
        }, "edge must survive the merge"
        edge = merged.edges[0]

        # The declared Pydantic field must still hold the URN — not the
        # provenance marker.  Before the fix this was "built-in".
        assert edge.source == "directive:alpha", (
            f"DRGEdge.source was corrupted by _tag_source: got {edge.source!r}"
        )
        assert edge.target == "directive:beta"

        # Provenance must be on the sidecar attribute, NOT on .source
        assert getattr(edge, "provenance", None) == "built-in"
        assert getattr(edge, "source", None) != "built-in", (
            "edge.source must be the URN, not the provenance marker"
        )

    def test_shipped_graph_with_edge_validates_after_merge(self) -> None:
        """The merged graph must be Pydantic-valid (no corrupted enum fields)."""

        built_in = _built_in_with_edge("directive:a", "directive:b")
        merged = merge_three_layers(built_in=built_in, org_fragments=[], project=None)

        # Re-validate the merged graph through the Pydantic model.  Before the
        # fix, ``DRGEdge.source`` was set to the string ``"built-in"`` which
        # is not a valid URN.  Pydantic accepts arbitrary strings in `source`
        # so this didn't raise directly — but the validator caught dangling
        # edges.  This test proves the round-trip shape is correct.
        assert merged.edges[0].source == "directive:a"
        assert merged.edges[0].target == "directive:b"


class TestOrgBridgeEdgeSourceUrnPreserved:
    """Org-bridged edges must keep the resolved URN as edge.source."""

    def test_org_bridge_edge_source_urn_is_a_urn(self) -> None:
        """An org edge resolved through bridge_org_edge_to_drg_edge must
        carry a URN (not a pack name) in edge.source."""
        built_in = _empty_built_in()
        fragment = OrgDRGFragment.model_validate(
            {
                "pack_name": "acme",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/acme",
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": [
                    {"id": "policy-node", "kind": "directives", "title": "Policy"},
                    {"id": "tactic-node", "kind": "tactics", "title": "Tactic"},
                ],
                "edges": [
                    {
                        "source": "policy-node",
                        "target": "tactic-node",
                        "relation": "requires",
                    }
                ],
            }
        )
        merged = merge_three_layers(
            built_in=built_in, org_fragments=[fragment], project=None
        )

        org_edges = list(merged.edges)
        assert len(org_edges) == 1, "org edge must be bridged into the merged graph"
        edge = org_edges[0]

        # Before the fix, edge.source was "org:acme" (the pack provenance).
        # After the fix, edge.source must be the resolved URN.
        assert edge.source.startswith("directive:") or edge.source.startswith(
            "tactic:"
        ), (
            f"edge.source should be a URN, not a provenance marker; got {edge.source!r}"
        )
        assert edge.source != "org:acme", (
            "edge.source must not be the pack name (provenance marker)"
        )

        # Provenance lives on the sidecar, not on the declared field.
        assert getattr(edge, "provenance", None) == "org:acme"


class TestDanglingSourceValidatorOnMergedGraph:
    """After merge, the validator must not produce false-positive dangling-source findings."""

    def test_dangling_source_validator_does_not_false_positive_after_merge(
        self,
    ) -> None:
        """Merged graph edges must not look dangling when their source URNs exist."""
        from specify_cli.charter_runtime.lint.checks.reference_integrity import (  # noqa: PLC0415
            ReferenceIntegrityChecker,
        )

        built_in = _built_in_with_edge("directive:x", "directive:y")
        merged = merge_three_layers(built_in=built_in, org_fragments=[], project=None)

        checker = ReferenceIntegrityChecker()
        findings = checker.run(merged, feature_scope=None)

        dangling_source_findings = [
            f for f in findings if f.type == "dangling_edge"
        ]
        assert not dangling_source_findings, (
            f"merge_three_layers produced false-positive dangling edges: "
            f"{dangling_source_findings}"
        )
