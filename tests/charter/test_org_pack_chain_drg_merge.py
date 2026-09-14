"""#3525 Fold B — the load-bearing chain fix: ``load_validated_graph`` must
fold the FULL configured org-pack chain, not just the first.

Proven live with a 2-pack fixture: org-tier doctrine resolution already works
for a chain of N org packs at every seam EXCEPT the DRG graph merge, which
took only pack #1 (first-match-wins). Pack #2's ``mission_step_contract``
loaded into the repository overlay (chain-correct) but its graph nodes /
``delegates_to`` edges were absent from the DRG (first-only) -- the executor
disagreed with itself. This module pins the primitive-level fix:
:func:`charter.activation._drg_helpers.load_validated_graph` accepts ``org_roots: list[Path]``
and folds every root in declaration order, later-declared-wins (mirroring
``charter.offering.base._apply_overlay_layer`` and ``charter.activation.org_expected_artifacts``).

The executor-level self-consistency proof (repo loads pack #2's contract AND
its ``delegates_to`` target resolves in the DRG) lives alongside the existing
org-pack executor fixtures in
``tests/specify_cli/mission_step_contracts/test_executor.py`` rather than
being re-authored here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from charter.activation._drg_helpers import load_validated_graph
from charter.offering.drg.loader import load_graph_or_dir

pytestmark = pytest.mark.fast


def _built_in_from(root: Path) -> Any:
    """Load a fixture built-in graph from *root* (mirrors
    ``test_merged_graph_on_live_path.py``'s established seam-injection
    pattern: patch ``charter.activation._drg_helpers.load_built_in_graph`` rather than
    depending on the real shipped doctrine tree)."""
    return load_graph_or_dir(root)


def _write_graph(path: Path, *, nodes: list[dict[str, object]], edges: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "schema_version: '1.0'",
        "generated_at: '2026-08-17T00:00:00Z'",
        "generated_by: test",
    ]
    if nodes:
        lines.append("nodes:")
        for node in nodes:
            lines.append(f"- {{urn: '{node['urn']}', kind: {node['kind']}, label: '{node['label']}'}}")
    else:
        lines.append("nodes: []")
    if edges:
        lines.append("edges:")
        for edge in edges:
            lines.append(
                f"- {{source: '{edge['source']}', target: '{edge['target']}', relation: {edge['relation']}}}"
            )
    else:
        lines.append("edges: []")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _empty_built_in(tmp_path: Path) -> Path:
    built_in_root = tmp_path / "doctrine"
    built_in_root.mkdir()
    _write_graph(built_in_root / "graph.yaml", nodes=[], edges=[])
    return built_in_root


class TestChainFoldsBothPacks:
    """The invariant: N=2 org packs each contributing a distinct
    ``mission_step_contract`` node + a ``delegates_to`` edge -- the merged
    graph must carry BOTH packs' contributions.

    Red-first (pre-fix): ``load_validated_graph`` accepted only a single
    ``org_root: Path | None`` -- there was no way to hand it two roots at
    once, so pack #2's node/edge were structurally unreachable regardless of
    which single root a caller chose. This test fails on the pre-fix
    signature with ``TypeError: load_validated_graph() got an unexpected
    keyword argument 'org_roots'`` and, once the parameter is threaded
    through but before the fold-loop is written, fails on the missing-node
    assertions below instead.
    """

    def test_both_org_packs_contribute_nodes_and_edges(self, tmp_path: Path) -> None:
        built_in_root = _empty_built_in(tmp_path)

        org_root_a = tmp_path / "org-pack-a"
        _write_graph(
            org_root_a / "pack-a.graph.yaml",
            nodes=[
                {"urn": "mission_step_contract:chain-fixture/pack-a-step", "kind": "mission_step_contract", "label": "Pack A step"},
                {"urn": "directive:pack-a-directive", "kind": "directive", "label": "Pack A directive"},
            ],
            edges=[
                {"source": "mission_step_contract:chain-fixture/pack-a-step", "target": "directive:pack-a-directive", "relation": "scope"},
            ],
        )

        org_root_b = tmp_path / "org-pack-b"
        _write_graph(
            org_root_b / "pack-b.graph.yaml",
            nodes=[
                {"urn": "mission_step_contract:chain-fixture/pack-b-step", "kind": "mission_step_contract", "label": "Pack B step"},
                {"urn": "directive:pack-b-directive", "kind": "directive", "label": "Pack B directive"},
            ],
            edges=[
                {"source": "mission_step_contract:chain-fixture/pack-b-step", "target": "directive:pack-b-directive", "relation": "scope"},
            ],
        )

        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            side_effect=lambda: _built_in_from(built_in_root),
        ):
            merged = load_validated_graph(tmp_path, org_roots=[org_root_a, org_root_b])

        node_urns = {n.urn for n in merged.nodes}
        edge_pairs = {(e.source, e.target) for e in merged.edges}

        # Pack A's contribution (the pre-fix "first match" -- was already
        # present under the single-org_root code path).
        assert "mission_step_contract:chain-fixture/pack-a-step" in node_urns
        assert "directive:pack-a-directive" in node_urns
        assert ("mission_step_contract:chain-fixture/pack-a-step", "directive:pack-a-directive") in edge_pairs

        # Pack B's contribution -- the load-bearing assertion the break
        # flips: "contract-B present: True".
        assert "mission_step_contract:chain-fixture/pack-b-step" in node_urns
        assert "directive:pack-b-directive" in node_urns
        assert ("mission_step_contract:chain-fixture/pack-b-step", "directive:pack-b-directive") in edge_pairs

    def test_declaration_order_is_preserved_not_reversed_or_sorted(self, tmp_path: Path) -> None:
        """NFR-003-style guard: passing roots in [z, a] order must not get
        silently reordered by the fold loop."""
        built_in_root = _empty_built_in(tmp_path)

        org_root_z = tmp_path / "z-pack"
        _write_graph(
            org_root_z / "z.graph.yaml",
            nodes=[{"urn": "directive:z-only", "kind": "directive", "label": "Z only"}],
            edges=[],
        )
        org_root_a = tmp_path / "a-pack"
        _write_graph(
            org_root_a / "a.graph.yaml",
            nodes=[{"urn": "directive:a-only", "kind": "directive", "label": "A only"}],
            edges=[],
        )

        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            side_effect=lambda: _built_in_from(built_in_root),
        ):
            merged = load_validated_graph(tmp_path, org_roots=[org_root_z, org_root_a])

        node_urns = {n.urn for n in merged.nodes}
        assert "directive:z-only" in node_urns
        assert "directive:a-only" in node_urns


class TestUrnCollisionLaterDeclaredWins:
    """Both packs declare the SAME node URN with a different label -- the
    later-declared pack (#2) must win, mirroring the repository overlay's
    established later-declared-wins precedence
    (``charter.offering.base._apply_overlay_layer``, ``charter.activation.org_expected_artifacts``).
    """

    def test_pack_b_label_wins_on_urn_collision(self, tmp_path: Path) -> None:
        built_in_root = _empty_built_in(tmp_path)
        collided_urn = "directive:shared-collision-directive"

        org_root_a = tmp_path / "org-pack-a"
        _write_graph(
            org_root_a / "pack-a.graph.yaml",
            nodes=[{"urn": collided_urn, "kind": "directive", "label": "Pack A label"}],
            edges=[],
        )
        org_root_b = tmp_path / "org-pack-b"
        _write_graph(
            org_root_b / "pack-b.graph.yaml",
            nodes=[{"urn": collided_urn, "kind": "directive", "label": "Pack B label"}],
            edges=[],
        )

        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            side_effect=lambda: _built_in_from(built_in_root),
        ):
            merged = load_validated_graph(tmp_path, org_roots=[org_root_a, org_root_b])

        survivors = [n for n in merged.nodes if n.urn == collided_urn]
        assert len(survivors) == 1, "URN collision must not duplicate the node"
        assert survivors[0].label == "Pack B label"


class TestBackCompatSingleOrgRoot:
    """The pre-existing single-value ``org_root`` kwarg must keep working
    byte-identically for every caller that has not migrated to the chain
    parameter (charter-build-time callers stay inert by design)."""

    def test_single_org_root_kwarg_still_works(self, tmp_path: Path) -> None:
        built_in_root = _empty_built_in(tmp_path)
        org_root = tmp_path / "org-pack"
        _write_graph(
            org_root / "pack.graph.yaml",
            nodes=[{"urn": "directive:single-root-probe", "kind": "directive", "label": "Single root"}],
            edges=[],
        )

        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            side_effect=lambda: _built_in_from(built_in_root),
        ):
            merged = load_validated_graph(tmp_path, org_root=org_root)

        assert "directive:single-root-probe" in {n.urn for n in merged.nodes}

    def test_no_org_args_stays_built_in_plus_project_only(self, tmp_path: Path) -> None:
        built_in_root = _empty_built_in(tmp_path)

        with patch(
            "charter.activation._drg_helpers.load_built_in_graph",
            side_effect=lambda: _built_in_from(built_in_root),
        ):
            merged = load_validated_graph(tmp_path)

        assert merged.nodes == []
