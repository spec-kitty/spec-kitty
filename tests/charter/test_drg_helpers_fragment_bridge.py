"""Unit coverage for the DRG read-path bridge (mission
``drg-read-path-bridge-01M0CHVZ``, WP01).

Two seams, below the CLI integration in
``tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py``:

* **T002** — ``charter.activation.drg_activation.load_org_drg(strict=…)``: ``strict=True`` (default,
  the diagnostic-path contract) raises ``OrgPackMissingError`` for a pack with
  no ``drg/fragment.yaml``; ``strict=False`` (the cascade caller) skips such a
  pack, returning ``[]`` for a root-graph-only pack but still loading a present
  fragment (non-vacuity). ``layer_index`` is preserved from the full-registry
  enumeration.
* **T003** — ``charter.activation._drg_helpers.load_validated_graph(org_fragments=…)``: a
  supplied org fragment carrying ``A requires B`` folds via the existing
  ``merge_three_layers`` so the resolved edge appears in the returned graph's
  ``.edges``; omitting ``org_fragments`` is inert (FR-003) — the org edge does
  not appear and the graph is byte-identical to the no-fragment path.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.drg_activation import load_org_drg
from charter.offering.drg.models import DRGGraph
from charter.offering.drg.org_pack_config import resolve_existing_org_roots
from charter.offering.drg.org_pack_loader import OrgDRGFragment, OrgPackMissingError

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    """Write ``.kittify/config.yaml`` declaring *packs* in order.

    Uses the canonical ``charter_packs.org.packs[].local_path`` shape.
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {path}")
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_fragment_pack(repo_root: Path, name: str) -> Path:
    """A pack shipping ``drg/fragment.yaml`` (one directive node, no edges)."""
    pack_dir = repo_root / name
    drg_dir = pack_dir / "drg"
    drg_dir.mkdir(parents=True)
    (drg_dir / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: {name}
            source_kind: local_path
            source_ref: {pack_dir}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: {name}-node
                kind: directives
                title: "Fixture directive for {name}"
            edges: []
            """
        ),
        encoding="utf-8",
    )
    return pack_dir


def _make_root_graph_only_pack(repo_root: Path, name: str) -> Path:
    """A pack shipping a root-level ``*.graph.yaml`` but **no** ``drg/fragment.yaml``.

    This is the shape the strict ``load_org_drg`` cannot load (it raises
    ``OrgPackMissingError``) but the cascade caller must tolerate (skip).
    """
    pack_dir = repo_root / name
    pack_dir.mkdir(parents=True)
    (pack_dir / "fixture.graph.yaml").write_text(
        dedent(
            """\
            schema_version: "1.0"
            generated_at: "2026-08-19T00:00:00Z"
            generated_by: "test"
            nodes:
              - urn: "directive:ROOT_GRAPH_NODE"
                kind: directive
            edges: []
            """
        ),
        encoding="utf-8",
    )
    return pack_dir


def _org_edge(fragment_name: str = "edge-pack") -> OrgDRGFragment:
    """Fragment declaring ``A --requires--> B`` (bare-id endpoints)."""
    return OrgDRGFragment.model_validate(
        {
            "pack_name": fragment_name,
            "source_kind": "local_path",
            "source_ref": f"/nonexistent/{fragment_name}",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [
                {"id": "bridge-a", "kind": "directives", "title": "A"},
                {"id": "bridge-b", "kind": "directives", "title": "B"},
            ],
            "edges": [
                {"source": "bridge-a", "target": "bridge-b", "relation": "requires"},
            ],
        }
    )


# ---------------------------------------------------------------------------
# T002 — load_org_drg(strict=…)
# ---------------------------------------------------------------------------


class TestLoadOrgDrgStrict:
    def test_strict_true_raises_on_root_graph_only_pack(self, tmp_path: Path) -> None:
        """Default (diagnostic) path: a pack with no ``drg/fragment.yaml``
        raises ``OrgPackMissingError`` — behaviour identical to today so the
        diagnostic callers' error reporting is byte-identical (NFR-001)."""
        pack = _make_root_graph_only_pack(tmp_path, "root-graph-pack")
        _write_config(tmp_path, [("root-graph-pack", pack)])

        with pytest.raises(OrgPackMissingError) as exc_info:
            load_org_drg(tmp_path, strict=True)
        assert "root-graph-pack" in str(exc_info.value)
        assert "fragment.yaml" in str(exc_info.value)

    def test_strict_true_is_the_default(self, tmp_path: Path) -> None:
        """Omitting the flag preserves the strict (raising) contract."""
        pack = _make_root_graph_only_pack(tmp_path, "root-graph-pack")
        _write_config(tmp_path, [("root-graph-pack", pack)])

        with pytest.raises(OrgPackMissingError):
            load_org_drg(tmp_path)

    def test_strict_false_skips_root_graph_only_pack(self, tmp_path: Path) -> None:
        """Cascade path: a pack with no ``drg/fragment.yaml`` is skipped (it
        contributes no fragment layer) instead of raising."""
        pack = _make_root_graph_only_pack(tmp_path, "root-graph-pack")
        _write_config(tmp_path, [("root-graph-pack", pack)])

        assert load_org_drg(tmp_path, strict=False) == []

    def test_strict_false_still_loads_present_fragment(self, tmp_path: Path) -> None:
        """Non-vacuity: ``strict=False`` still loads a pack that DOES ship a
        ``drg/fragment.yaml`` — it only skips the fragment-less ones."""
        pack = _make_fragment_pack(tmp_path, "fragment-pack")
        _write_config(tmp_path, [("fragment-pack", pack)])

        strict = load_org_drg(tmp_path, strict=True)
        resilient = load_org_drg(tmp_path, strict=False)
        assert [f.pack_name for f in strict] == ["fragment-pack"]
        assert [f.pack_name for f in resilient] == ["fragment-pack"]

    def test_strict_false_preserves_true_layer_index_of_siblings(self, tmp_path: Path) -> None:
        """A skipped fragment-less pack does NOT renumber its siblings — the
        surviving pack keeps its full-registry ``layer_index`` (here 2)."""
        root_only = _make_root_graph_only_pack(tmp_path, "pack1")
        fragment = _make_fragment_pack(tmp_path, "pack2")
        _write_config(tmp_path, [("pack1", root_only), ("pack2", fragment)])

        resilient = load_org_drg(tmp_path, strict=False)
        assert [f.pack_name for f in resilient] == ["pack2"]
        # pack2 is the SECOND configured pack: its layer_index stays 2 even
        # though pack1 was skipped.
        assert resilient[0].layer_index == 2


# ---------------------------------------------------------------------------
# T003 — load_validated_graph(org_fragments=…)
# ---------------------------------------------------------------------------


class TestLoadValidatedGraphOrgFragments:
    _EDGE = ("directive:bridge-a", "directive:bridge-b")

    def _has_bridge_edge(self, graph: DRGGraph) -> bool:
        src, tgt = self._EDGE
        return any(e.source == src and e.target == tgt for e in graph.edges)

    def test_org_fragment_edge_appears_in_returned_graph(self, tmp_path: Path) -> None:
        """FR-001/FR-002: a supplied org fragment's ``A requires B`` edge is
        folded via ``merge_three_layers`` and appears in ``.edges``."""
        graph = load_validated_graph(tmp_path, org_fragments=[_org_edge()])
        assert self._has_bridge_edge(graph), "org fragment requires edge was not folded into the graph"

    def test_omitting_org_fragments_is_inert(self, tmp_path: Path) -> None:
        """FR-003: omitting ``org_fragments`` yields the pre-existing graph —
        the org edge is absent and the node/edge sets are byte-identical to the
        explicit-empty-list path (build-time callers unaffected)."""
        without = load_validated_graph(tmp_path)
        empty = load_validated_graph(tmp_path, org_fragments=[])

        assert not self._has_bridge_edge(without)
        assert not self._has_bridge_edge(empty)
        # Omitting and passing [] are the same "no org layer" path.
        assert {n.urn for n in without.nodes} == {n.urn for n in empty.nodes}
        assert {(e.source, e.target, e.relation) for e in without.edges} == {(e.source, e.target, e.relation) for e in empty.edges}

    def test_supplying_fragment_only_adds_the_org_edge(self, tmp_path: Path) -> None:
        """The bridge is purely additive: the fragment run's edge set is the
        no-fragment set PLUS the resolved org edge (no other drift)."""
        without = load_validated_graph(tmp_path)
        with_fragment = load_validated_graph(tmp_path, org_fragments=[_org_edge()])

        base_edges = {(e.source, e.target, e.relation) for e in without.edges}
        bridged_edges = {(e.source, e.target, e.relation) for e in with_fragment.edges}
        new_edges = bridged_edges - base_edges
        src, tgt = self._EDGE
        assert any(s == src and t == tgt for (s, t, _rel) in new_edges), new_edges


# ---------------------------------------------------------------------------
# Spec Edge Case 1 — the same edge authored in BOTH a root *.graph.yaml and
# drg/fragment.yaml must de-duplicate to ONE edge, not hard-fail on the
# duplicate-edge validator (pre-merge squad blocker, mission remediation).
# ---------------------------------------------------------------------------


def _make_both_shapes_pack(repo_root: Path, name: str) -> Path:
    """A pack that declares ``A requires B`` in BOTH a root-level
    ``*.graph.yaml`` AND ``drg/fragment.yaml`` — the exact overlap spec Edge
    Case 1 requires to collapse to a single edge."""
    pack_dir = repo_root / name
    (pack_dir / "directives").mkdir(parents=True)
    (pack_dir / "directives" / "a.directive.yaml").write_text("id: DIRECTIVE_A\ntype: directive\ntitle: a\n", encoding="utf-8")
    (pack_dir / "directives" / "b.directive.yaml").write_text("id: DIRECTIVE_B\ntype: directive\ntitle: b\n", encoding="utf-8")
    (pack_dir / "fixture.graph.yaml").write_text(
        dedent(
            """\
            schema_version: "1.0"
            generated_at: "2026-08-19T00:00:00Z"
            generated_by: "test"
            nodes:
              - urn: "directive:DIRECTIVE_A"
                kind: directive
              - urn: "directive:DIRECTIVE_B"
                kind: directive
            edges:
              - source: "directive:DIRECTIVE_A"
                target: "directive:DIRECTIVE_B"
                relation: requires
            """
        ),
        encoding="utf-8",
    )
    drg_dir = pack_dir / "drg"
    drg_dir.mkdir()
    (drg_dir / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: {name}
            source_kind: local_path
            source_ref: {pack_dir}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: DIRECTIVE_A
                kind: directives
              - id: DIRECTIVE_B
                kind: directives
            edges:
              - source: DIRECTIVE_A
                target: "directive:DIRECTIVE_B"
                relation: requires
            """
        ),
        encoding="utf-8",
    )
    return pack_dir


class TestSameEdgeInBothShapesDedups:
    _EDGE = ("directive:DIRECTIVE_A", "directive:DIRECTIVE_B", "requires")

    def test_same_edge_in_root_graph_and_fragment_collapses_to_one(self, tmp_path: Path) -> None:
        """Spec Edge Case 1: a pack declaring ``A requires B`` in BOTH a root
        ``*.graph.yaml`` and ``drg/fragment.yaml`` loads without raising and the
        graph carries exactly ONE such edge (no double-count) — the composition
        of ``merge_layers`` (root graph) + ``merge_three_layers`` (fragment)
        would otherwise present the triple twice and trip the duplicate-edge
        validator."""
        _make_both_shapes_pack(tmp_path, "both-pack")
        _write_config(tmp_path, [("both-pack", tmp_path / "both-pack")])

        graph = load_validated_graph(
            tmp_path,
            org_roots=resolve_existing_org_roots(tmp_path),
            org_fragments=load_org_drg(tmp_path, strict=False),
        )
        matches = [(e.source, e.target, e.relation.value) for e in graph.edges if (e.source, e.target, e.relation.value) == self._EDGE]
        assert matches == [self._EDGE], f"expected exactly one A→B requires edge, got {len(matches)}: {matches}"
