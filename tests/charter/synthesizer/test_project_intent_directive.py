"""#6443: the always-synthesized directive is the *project-intent* directive.

FR-006: a fresh synthesis names it ``project-intent-directive`` with a
project-intent title. FR-007: it carries no ``requires --> mission_type:*``
edge, even when the answer names a shipped mission type, and reconcile strips
such an edge from an existing overlay and reports it.
"""

from __future__ import annotations

import pytest

from charter.activation.synthesizer.interview_mapping import resolve_sections
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.reconcile import (
    legacy_applies_edges,
    legacy_strip_notice,
    merge_project_overlay,
)
from charter.activation.synthesizer.targets import build_targets
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.unit, pytest.mark.regression]

_GENERATED_AT = "2026-10-19T00:00:00+00:00"
_DRG_WITH_MISSION_TYPE = {
    "nodes": [{"urn": "mission_type:software-dev", "kind": "mission_type"}],
    "edges": [],
    "schema_version": "1.0",
}
_DEAD_EDGE = DRGEdge(source="directive:PROJECT_001", target="mission_type:software-dev", relation=Relation.REQUIRES)


def _intent_target(answer: str = "software-dev"):
    snapshot = {"mission_type": answer}
    targets = build_targets(snapshot, resolve_sections(snapshot), _DRG_WITH_MISSION_TYPE)
    return next(t for t in targets if t.source_section == "mission_type")


def _graph(nodes: list[DRGNode], edges: list[DRGEdge]) -> DRGGraph:
    return DRGGraph(schema_version="1.0", generated_at=_GENERATED_AT, generated_by="test", nodes=nodes, edges=edges)


def test_fresh_target_is_the_project_intent_directive() -> None:
    target = _intent_target()
    assert target.slug == "project-intent-directive"
    assert target.title == "Project Intent Directive"
    assert target.source_section == "mission_type"
    assert target.artifact_id == "PROJECT_001"


@pytest.mark.parametrize("answer", ["software-dev", "software_dev", "research", "Ship trustworthy agent workflows"])
def test_no_mission_type_source_urn_even_when_the_answer_names_a_shipped_type(answer: str) -> None:
    assert _intent_target(answer).source_urns == ()


def test_emitted_overlay_has_no_mission_type_edge() -> None:
    built_in = _graph([DRGNode(urn="mission_type:software-dev", kind=NodeKind.MISSION_TYPE, label="Software Dev")], [])
    overlay = emit_project_layer([_intent_target()], spec_kitty_version="test", built_in_drg=built_in)
    assert [e for e in overlay.edges if e.target.startswith("mission_type:")] == []


def test_reconcile_strips_an_existing_dead_edge_and_names_it() -> None:
    directive = DRGNode(urn="directive:PROJECT_001", kind=NodeKind.DIRECTIVE, label="Project Intent Directive")
    existing = _graph([directive], [_DEAD_EDGE])
    updated = _graph([directive], [])

    assert legacy_applies_edges(existing, ()) == (_DEAD_EDGE,)
    merged = merge_project_overlay(existing_overlay=existing, updated_overlay=updated)
    assert merged.edges == []
    assert "mission_type:software-dev" in legacy_strip_notice(_DEAD_EDGE)


def test_a_hand_authored_directive_edge_to_a_mission_type_is_not_stripped() -> None:
    hand = DRGEdge(source="directive:DIRECTIVE_003", target="mission_type:software-dev", relation=Relation.REQUIRES)
    assert legacy_applies_edges(_graph([], [hand]), ()) == ()
