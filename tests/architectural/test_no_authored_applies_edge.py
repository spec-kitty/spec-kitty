"""Reject inert ``applies`` edges in the shipped doctrine graph.

No runtime traversal consumes this relation.  The guard covers checked-in graph
fragments, the loaded graph, and the generated graph.  It carries no historical
edge-count registry, prose parser, migration allowlist, or named-WP acceptance pin.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.offering.drg.loader import load_graph_or_dir
from charter.offering.drg.migration.hand_authored_overlay import (
    generate_reference_graph_with_overlay,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = pytest.mark.architectural

_BUILT_IN_PACK_ROOT = Path(__file__).resolve().parents[2] / "packs" / "built-in"
_FORBIDDEN = Relation.APPLIES


@dataclass(frozen=True)
class AuthoredAppliesEdge:
    fragment: str
    source: str
    target: str

    def __str__(self) -> str:
        return f"{self.fragment}: {self.source} --applies--> {self.target}"


def _load_fragment(path: Path) -> dict[str, Any]:
    data: Any = YAML(typ="safe").load(path)
    return data if isinstance(data, dict) else {}


def iter_fragments(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.graph.yaml")
        if "__pycache__" not in path.parts
    )


def authored_applies_edges(root: Path) -> tuple[AuthoredAppliesEdge, ...]:
    found: list[AuthoredAppliesEdge] = []
    for path in iter_fragments(root):
        edges = _load_fragment(path).get("edges") or []
        if not isinstance(edges, list):
            continue
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("relation") != _FORBIDDEN.value:
                continue
            found.append(
                AuthoredAppliesEdge(
                    fragment=path.relative_to(root).as_posix(),
                    source=str(edge.get("source", "?")),
                    target=str(edge.get("target", "?")),
                )
            )
    return tuple(found)


def applies_edges_in(graph: DRGGraph) -> tuple[str, ...]:
    return tuple(
        f"{edge.source} --{_FORBIDDEN.value}--> {edge.target}"
        for edge in graph.edges
        if edge.relation is _FORBIDDEN
    )


def _fragment_text(relation: str) -> str:
    return (
        "schema_version: '1.0'\n"
        "generated_at: STATIC\n"
        "generated_by: test\n"
        "nodes: []\n"
        "edges:\n"
        "- source: agent_profile:planted\n"
        "  target: procedure:planted\n"
        f"  relation: {relation}\n"
    )


def _graph_with(relation: Relation) -> DRGGraph:
    source = "agent_profile:planted"
    target = "procedure:planted"
    return DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[
            DRGNode(urn=source, kind=NodeKind.AGENT_PROFILE),
            DRGNode(urn=target, kind=NodeKind.PROCEDURE),
        ],
        edges=[DRGEdge(source=source, target=target, relation=relation)],
    )


def test_shipped_fragments_have_no_authored_applies_edge() -> None:
    fragments = iter_fragments(_BUILT_IN_PACK_ROOT)
    assert fragments, "doctrine fragment scan collected zero files"
    assert authored_applies_edges(_BUILT_IN_PACK_ROOT) == ()


def test_loaded_shipped_graph_has_no_applies_edge() -> None:
    graph = load_graph_or_dir(_BUILT_IN_PACK_ROOT)
    assert graph.nodes, "loaded doctrine graph has an empty corpus"
    assert applies_edges_in(graph) == ()


def test_generated_shipped_graph_has_no_applies_edge() -> None:
    graph = generate_reference_graph_with_overlay(_BUILT_IN_PACK_ROOT)
    assert graph.nodes, "generated doctrine graph has an empty corpus"
    assert applies_edges_in(graph) == ()


def test_fragment_guard_has_two_sided_fault_bite(tmp_path: Path) -> None:
    fragment = tmp_path / "probe.graph.yaml"
    fragment.write_text(_fragment_text("requires"), encoding="utf-8")
    assert authored_applies_edges(tmp_path) == ()

    fragment.write_text(_fragment_text("applies"), encoding="utf-8")
    assert [str(edge) for edge in authored_applies_edges(tmp_path)] == [
        "probe.graph.yaml: agent_profile:planted --applies--> procedure:planted"
    ]


def test_loaded_graph_guard_has_two_sided_fault_bite() -> None:
    assert applies_edges_in(_graph_with(Relation.REQUIRES)) == ()
    assert applies_edges_in(_graph_with(Relation.APPLIES)) == (
        "agent_profile:planted --applies--> procedure:planted",
    )
