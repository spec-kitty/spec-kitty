"""Org-vs-org precedence: the later-declared org pack wins for every URN.

spec-kitty-charter #87 (ADR-0012 states pack mutability over merge order, so
it needs one precedence). Before this, a non-built-in URN kept the FIRST org
pack's node with no record, a built-in URN kept the LAST, and a relationship
two packs both declared kept the FIRST pack's provenance and reason.

Every path is checked in both declaration orders: the result must flip with
the order, which is what proves the order (and not the pack name or content)
decides it.
"""

from __future__ import annotations

import logging

import pytest

from charter.offering.drg.merge import (
    OrgDRGConflict,
    OrgDRGConflictError,
    merge_three_layers,
)
from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind
from charter.offering.drg.org_pack_loader import OrgDRGFragment

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_ORDERS = [("pack-a", "pack-b"), ("pack-b", "pack-a")]


def _built_in() -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-10-19T00:00:00Z",
        generated_by="unit-test",
        nodes=[
            DRGNode(urn="directive:builtin-alpha", kind=NodeKind.DIRECTIVE, label="Alpha"),
            DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC, label="Built-in label"),
        ],
        edges=[],
    )


def _fragment(
    pack_name: str,
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]] | None = None,
) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": pack_name,
            "source_kind": "local_path",
            "source_ref": f"/nonexistent/{pack_name}",
            "layer_index": 1,
            "nodes": nodes,
            "edges": edges or [],
        }
    )


def _labelled(pack_name: str, node_id: str, kind: str) -> OrgDRGFragment:
    return _fragment(pack_name, [{"id": node_id, "kind": kind, "title": f"{pack_name} label"}])


def _layer_rule_breaker() -> OrgDRGFragment:
    """A pack whose only node hard-fails, so the merge raises and exposes every
    conflict it recorded (advisory records only surface on the raise)."""
    return _fragment(
        "breaker",
        [{"id": "x", "kind": "tactics", "title": "X", "body_path": "src/specify_cli/x.py"}],
    )


def _node_overrides(conflicts: list[OrgDRGConflict], urn: str) -> list[OrgDRGConflict]:
    return [c for c in conflicts if c.kind == "node_override" and c.target_id == urn]


class TestNonBuiltInUrn:
    @pytest.mark.parametrize(("first", "second"), _ORDERS)
    def test_later_declared_pack_wins(self, first: str, second: str) -> None:
        merged = merge_three_layers(
            _built_in(),
            [_labelled(first, "org-only", "directives"), _labelled(second, "org-only", "directives")],
            None,
        )

        node = merged.get_node("directive:org-only")
        assert node is not None
        assert node.label == f"{second} label"
        assert node.provenance == f"org:{second}"

    @pytest.mark.parametrize(("first", "second"), _ORDERS)
    def test_override_is_recorded_naming_the_overridden_pack(self, first: str, second: str, caplog: pytest.LogCaptureFixture) -> None:
        with (
            caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"),
            pytest.raises(OrgDRGConflictError) as exc_info,
        ):
            merge_three_layers(
                _built_in(),
                [
                    _labelled(first, "org-only", "directives"),
                    _labelled(second, "org-only", "directives"),
                    _layer_rule_breaker(),
                ],
                None,
            )

        [record] = _node_overrides(exc_info.value.conflicts, "directive:org-only")
        assert record.conflicting_layers == [f"org:{first}", f"org:{second}"]
        assert record.resolution_applied == "org_override"
        assert record.built_in_value is None
        assert record.org_value["title"] == f"{second} label"
        assert f"'org:{second}' overrides node 'directive:org-only' contributed by 'org:{first}'" in caplog.text

    def test_a_single_pack_records_no_override(self) -> None:
        with pytest.raises(OrgDRGConflictError) as exc_info:
            merge_three_layers(
                _built_in(),
                [_labelled("pack-a", "org-only", "directives"), _layer_rule_breaker()],
                None,
            )
        assert _node_overrides(exc_info.value.conflicts, "directive:org-only") == []


class TestBuiltInUrn:
    @pytest.mark.parametrize(("first", "second"), _ORDERS)
    def test_later_declared_pack_wins(self, first: str, second: str) -> None:
        merged = merge_three_layers(
            _built_in(),
            [_labelled(first, "shared", "tactics"), _labelled(second, "shared", "tactics")],
            None,
        )

        node = merged.get_node("tactic:shared")
        assert node is not None
        assert node.label == f"{second} label"
        assert node.provenance == f"org:{second}"

    @pytest.mark.parametrize(("first", "second"), _ORDERS)
    def test_second_override_names_the_earlier_pack_and_keeps_the_built_in_value(self, first: str, second: str) -> None:
        with pytest.raises(OrgDRGConflictError) as exc_info:
            merge_three_layers(
                _built_in(),
                [
                    _labelled(first, "shared", "tactics"),
                    _labelled(second, "shared", "tactics"),
                    _layer_rule_breaker(),
                ],
                None,
            )

        records = _node_overrides(exc_info.value.conflicts, "tactic:shared")
        assert [r.conflicting_layers for r in records] == [
            ["built-in", f"org:{first}"],
            [f"org:{first}", f"org:{second}"],
        ]
        assert {r.resolution_applied for r in records} == {"org_override"}
        # ``built_in_value`` is the built-in node itself on both records, never
        # the earlier org pack's node.
        built_in_values = [r.built_in_value for r in records]
        assert built_in_values == [records[0].built_in_value] * 2
        assert records[0].built_in_value is not None
        assert records[0].built_in_value["label"] == "Built-in label"


class TestEdges:
    @pytest.mark.parametrize(("first", "second"), _ORDERS)
    def test_restated_relationship_keeps_the_later_pack_provenance_and_reason(self, first: str, second: str) -> None:
        def _pack(name: str) -> OrgDRGFragment:
            return _fragment(
                name,
                [{"id": "shared-node", "kind": "directives"}],
                [
                    {
                        "source": "shared-node",
                        "target": "directive:builtin-alpha",
                        "relation": "requires",
                        "reason": f"{name} reason",
                    }
                ],
            )

        merged = merge_three_layers(_built_in(), [_pack(first), _pack(second)], None)

        org_edges = [e for e in merged.edges if str(e.provenance).startswith("org:")]
        assert len(org_edges) == 1, "one relationship, one edge"
        assert org_edges[0].provenance == f"org:{second}"
        assert org_edges[0].reason == f"{second} reason"

    def test_replaced_edge_keeps_its_position(self) -> None:
        def _pack(name: str, targets: list[str]) -> OrgDRGFragment:
            return _fragment(
                name,
                [{"id": "src", "kind": "directives"}, {"id": "other", "kind": "directives"}],
                [{"source": "src", "target": t, "relation": "requires"} for t in targets],
            )

        merged = merge_three_layers(
            _built_in(),
            [
                _pack("pack-a", ["directive:builtin-alpha", "other"]),
                _pack("pack-b", ["directive:builtin-alpha"]),
            ],
            None,
        )

        assert [(e.target, e.provenance) for e in merged.edges] == [
            ("directive:builtin-alpha", "org:pack-b"),
            ("directive:other", "org:pack-a"),
        ]

    def test_an_overridden_node_keeps_the_earlier_pack_edges(self) -> None:
        """Edges are additive: overriding a node replaces the node, not the
        relationships another pack declared from it."""
        pack_a = _fragment(
            "pack-a",
            [{"id": "org-only", "kind": "directives", "title": "A"}],
            [{"source": "org-only", "target": "directive:builtin-alpha", "relation": "requires"}],
        )
        pack_b = _fragment("pack-b", [{"id": "org-only", "kind": "directives", "title": "B"}])

        merged = merge_three_layers(_built_in(), [pack_a, pack_b], None)

        node = merged.get_node("directive:org-only")
        assert node is not None
        assert node.provenance == "org:pack-b"
        assert [(e.source, e.target, e.provenance) for e in merged.edges] == [("directive:org-only", "directive:builtin-alpha", "org:pack-a")]


class TestChainAndSamePack:
    def test_three_packs_chain_to_the_last_declared(self) -> None:
        with pytest.raises(OrgDRGConflictError) as exc_info:
            merge_three_layers(
                _built_in(),
                [
                    _labelled("pack-a", "shared", "tactics"),
                    _labelled("pack-b", "shared", "tactics"),
                    _labelled("pack-c", "shared", "tactics"),
                    _layer_rule_breaker(),
                ],
                None,
            )

        records = _node_overrides(exc_info.value.conflicts, "tactic:shared")
        assert [r.conflicting_layers for r in records] == [
            ["built-in", "org:pack-a"],
            ["org:pack-a", "org:pack-b"],
            ["org:pack-b", "org:pack-c"],
        ]
        assert records[-1].org_value["title"] == "pack-c label"

    def test_a_pack_declaring_one_urn_twice_keeps_its_first_declaration(self, caplog: pytest.LogCaptureFixture) -> None:
        pack = _fragment(
            "pack-a",
            [
                {"id": "org-only", "kind": "directives", "title": "first"},
                {"id": "org-only", "kind": "directives", "title": "second"},
            ],
        )
        with (
            caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"),
            pytest.raises(OrgDRGConflictError) as exc_info,
        ):
            merge_three_layers(_built_in(), [pack, _layer_rule_breaker()], None)

        assert _node_overrides(exc_info.value.conflicts, "directive:org-only") == []
        assert "overrides node 'directive:org-only'" not in caplog.text

        merged = merge_three_layers(_built_in(), [pack], None)
        node = merged.get_node("directive:org-only")
        assert node is not None
        assert node.label == "first"


def test_replace_edge_refuses_an_edge_it_cannot_find() -> None:
    from charter.offering.drg.merge import _replace_edge  # noqa: PLC0415 — private helper
    from charter.offering.drg.models import DRGEdge, Relation  # noqa: PLC0415

    def _edge(target: str) -> DRGEdge:
        return DRGEdge(source="directive:a", target=target, relation=Relation.REQUIRES)

    edges = [_edge("directive:b")]
    with pytest.raises(RuntimeError, match="missing from the merged edges"):
        _replace_edge(edges, _edge("directive:c"), _edge("directive:d"))
