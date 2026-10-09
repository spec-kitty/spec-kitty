"""Endpoint authority preserves binding and structural edge identity (#5833)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from charter.drg import (
    EndpointResolutionError,
    OrgPackSchemaError,
    dangling_endpoints,
    load_org_pack,
    resolve_edge_endpoint,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]


@pytest.mark.parametrize(
    "content",
    [
        "nodes: [{id: local, kind: directives, discovered: true}]",
        "edges: [{source: local, target: local, relation: requires, generated_reason: spoof}]",
    ],
)
def test_authors_cannot_spoof_loader_provenance(tmp_path: Path, content: str) -> None:
    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text(content, encoding="utf-8")
    with pytest.raises(OrgPackSchemaError):
        load_org_pack("test", tmp_path, 1)


def test_empty_fragment_has_empty_authored_accessors(tmp_path: Path) -> None:
    fragment = tmp_path / "drg" / "fragment.yaml"
    fragment.parent.mkdir()
    fragment.write_text("{}", encoding="utf-8")
    loaded = load_org_pack("test", tmp_path, 1)
    assert loaded.authored_nodes == [] and loaded.authored_edges == []


@dataclass(frozen=True)
class Edge:
    source: str
    target: str


@dataclass
class View:
    edges: list[Edge]
    known: set[str]

    def node_urns(self) -> set[str]:
        return self.known


def test_dangling_endpoints_generic_order() -> None:
    both = Edge("missing-source", "missing-target")
    target = Edge("directive:local", "missing-target")
    view = View([both, Edge("directive:local", "directive:local"), target], {"directive:local"})
    result: list[Edge] = dangling_endpoints(view)
    assert len(result) == 2
    assert result[0] is both and result[1] is target
    assert dangling_endpoints(View([], set())) == []


@pytest.mark.parametrize(
    "raw,local,builtins,expected",
    [
        ("shared", {"shared": "asset:shared"}, {"directive:shared", "tactic:shared"}, "asset:shared"),
        ("directive:later", {}, set(), "directive:later"),
        ("shared", {}, {"directive:shared"}, "directive:shared"),
    ],
)
def test_public_resolver_success(raw: str, local: dict[str, str], builtins: set[str], expected: str) -> None:
    assert resolve_edge_endpoint(raw, local, builtins) == expected


@pytest.mark.parametrize(
    "raw,builtins,cause",
    [
        ("directive:", set(), "malformed_urn"),
        ("shared", {"directive:shared", "tactic:shared"}, "ambiguous_edge_endpoint"),
        ("directve:shared", set(), "unresolved_edge_endpoint"),
        ("missing", set(), "unresolved_edge_endpoint"),
    ],
)
def test_public_resolver_refusal(raw: str, builtins: set[str], cause: str) -> None:
    with pytest.raises(EndpointResolutionError) as raised:
        resolve_edge_endpoint(raw, {}, builtins)
    assert raised.value.conflict_kind == cause
    assert raised.value.raw == raw


def test_authored_accessors_preserve_order_dumps_and_duplicate_metadata(tmp_path: Path) -> None:
    fragment_path = tmp_path / "drg" / "fragment.yaml"
    fragment_path.parent.mkdir()
    fragment_path.write_text(
        "nodes:\n  - {id: same, kind: directives, title: Authored}\n"
        "  - {id: same, kind: directives, title: Duplicate}\n"
        "edges:\n  - {source: same, target: directive:other, relation: requires, reason: Authored}\n",
        encoding="utf-8",
    )
    artifacts = tmp_path / "directives"
    artifacts.mkdir()
    (artifacts / "same.directive.yaml").write_text("id: same\ntitle: Discovered\n", encoding="utf-8")
    (artifacts / "other.directive.yaml").write_text("id: other\nenhances: missing\n", encoding="utf-8")
    fragment = load_org_pack("test", tmp_path, 1)
    assert [node.id for node in fragment.authored_nodes] == ["same", "same"]
    assert [node.title for node in fragment.authored_nodes] == ["Authored", "Duplicate"]
    assert [node.id for node in fragment.nodes] == ["same", "same", "other"]
    assert fragment.nodes[-1].model_dump() == {"id": "other", "kind": "directives", "title": None, "body_path": None}
    assert len(fragment.edges) == 2 and len(fragment.authored_edges) == 1
    assert fragment.authored_edges[0] is fragment.edges[0]
    assert fragment.authored_edges[0].model_dump() == {
        "source": "same",
        "target": "directive:other",
        "relation": "requires",
        "reason": "Authored",
    }
