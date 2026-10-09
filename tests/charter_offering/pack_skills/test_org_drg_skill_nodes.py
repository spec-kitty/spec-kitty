"""Org DRG fragments may declare ``skill:<id>`` nodes with requires/suggests edges (FR-003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.drg_activation import merge_three_layers
from charter.drg import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.org_pack_loader import load_org_pack

from .conftest import prompt_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FRAGMENT = """\
pack_name: acme
source_kind: local_path
source_ref: "/nonexistent/pack"
layer_index: 1
nodes:
  - id: land-pr
    kind: skills
    title: "Land a PR"
    body_path: skills/land-pr.skill.yaml
edges:
  - source: skill:land-pr
    target: procedure:landing-contributor-prs
    relation: requires
  - source: skill:land-pr
    target: directive:SOME-DIRECTIVE
    relation: suggests
"""


def _built_in() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-10-04T00:00:00Z",
        generated_by="test",
        nodes=[
            DRGNode(urn="procedure:landing-contributor-prs", kind=NodeKind.PROCEDURE),
            DRGNode(urn="directive:SOME-DIRECTIVE", kind=NodeKind.DIRECTIVE),
        ],
        edges=[DRGEdge(source="directive:SOME-DIRECTIVE", target="procedure:landing-contributor-prs", relation=Relation.APPLIES)],
    )


def test_org_fragment_skill_node_and_edges_survive_the_merge(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    (pack_root / "drg").mkdir(parents=True)
    (pack_root / "drg" / "fragment.yaml").write_text(_FRAGMENT, encoding="utf-8")
    write_skill(pack_root / "skills", prompt_skill("land-pr"))

    fragment = load_org_pack("acme", pack_root, layer_index=1)
    merged = merge_three_layers(_built_in(), [fragment], None)

    kinds = {node.urn: node.kind for node in merged.nodes}
    assert kinds["skill:land-pr"] is NodeKind.SKILL
    edges = {(edge.source, edge.target, edge.relation) for edge in merged.edges}
    assert ("skill:land-pr", "procedure:landing-contributor-prs", Relation.REQUIRES) in edges
    assert ("skill:land-pr", "directive:SOME-DIRECTIVE", Relation.SUGGESTS) in edges


def test_skill_enhances_field_auto_emits_an_enhances_edge(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    (pack_root / "drg").mkdir(parents=True)
    (pack_root / "drg" / "fragment.yaml").write_text(
        "pack_name: acme\nsource_kind: local_path\nsource_ref: /x\nlayer_index: 1\nnodes: []\nedges: []\n",
        encoding="utf-8",
    )
    write_skill(pack_root / "skills", prompt_skill("land-pr-tuned", enhances="land-pr"))

    fragment = load_org_pack("acme", pack_root, layer_index=1)

    assert any(e.source == "skill:land-pr-tuned" and e.target == "skill:land-pr" and e.relation == Relation.ENHANCES.value for e in fragment.edges)
