"""#6404 -- synthesized how-we-apply tactics reach action context only via their directive.

A synthesized tactic that is the target of an overlay ``directive:* --suggests-->``
edge is *reach-only*: it is never a closure root, so it is delivered exactly while
its directive is delivered. Edgeless synthesized tactics and hand-authored project
tactics stay roots.

Every absence assertion is paired with a positive control on the same fixture
(tactic ``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from charter.activation.action_governance_bundle import _load_action_governance_bundle
from charter.activation.context_renderers.delivery_table import _classify_artifact_urns
from charter.activation.pack_context import PackContext
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast]

_MISSION_TYPE = "software-dev"
_ACTION = "implement"
_ACTION_URN = f"action:{_MISSION_TYPE}/{_ACTION}"

_DIRECTIVE_STEM = "024-locality-of-change"
_DIRECTIVE_ID = "DIRECTIVE_024"
_REACH_ONLY = "how-we-apply-directive-024"
_EDGELESS_SYNTH = "testing-philosophy-tactic"
_HAND_AUTHORED = "my-hand-authored-tactic"
_CONTROL = "adversarial-qa-handoff"  # real built-in, never synthesized

_ALL_KINDS = frozenset({"directives", "tactics", "paradigms", "styleguides", "toolguides", "procedures"})


def _tactic_yaml(tactic_id: str) -> str:
    return yaml.safe_dump(
        {
            "schema_version": "1.0",
            "id": tactic_id,
            "name": tactic_id,
            "purpose": "fixture tactic",
            "steps": [{"title": "Step", "description": "Do the thing."}],
        }
    )


def _write_overlay(repo_root: Path, *, with_edge: bool) -> None:
    """Project overlay: reach-only tactic (+ edge), edgeless synthesized tactic, hand-authored tactic."""
    pack = repo_root / ".kittify" / "charter-packs"
    (pack / "tactic").mkdir(parents=True, exist_ok=True)
    for tactic_id in (_REACH_ONLY, _EDGELESS_SYNTH, _HAND_AUTHORED):
        (pack / "tactic" / f"{tactic_id}.tactic.yaml").write_text(_tactic_yaml(tactic_id), encoding="utf-8")
    nodes = [{"urn": f"tactic:{t}", "kind": "tactic", "label": t} for t in (_REACH_ONLY, _EDGELESS_SYNTH)]
    edges = (
        [{"source": f"directive:{_DIRECTIVE_ID}", "target": f"tactic:{_REACH_ONLY}", "relation": "suggests"}]
        if with_edge
        else []
    )
    (pack / "graph.yaml").write_text(
        yaml.safe_dump({"schema_version": "1.0", "generated_at": "2026-10-19T00:00:00+00:00", "generated_by": "test", "nodes": nodes, "edges": edges}),
        encoding="utf-8",
    )


def _merged_graph(*, with_edge: bool) -> DRGGraph:
    tactic_ids = (_REACH_ONLY, _EDGELESS_SYNTH, _HAND_AUTHORED, _CONTROL)
    nodes = [
        DRGNode(urn=_ACTION_URN, kind=NodeKind.ACTION),
        DRGNode(urn=f"directive:{_DIRECTIVE_ID}", kind=NodeKind.DIRECTIVE),
        *(DRGNode(urn=f"tactic:{t}", kind=NodeKind.TACTIC) for t in tactic_ids),
    ]
    edges = [DRGEdge(source=f"directive:{_DIRECTIVE_ID}", target=f"tactic:{_REACH_ONLY}", relation=Relation.SUGGESTS)] if with_edge else []
    return DRGGraph(schema_version="1.0", generated_at="2026-10-19T00:00:00+00:00", generated_by="test_reach_only_delivery", nodes=nodes, edges=edges)


def _pack_context(
    repo_root: Path,
    *,
    directives: frozenset[str] | None,
    tactics: frozenset[str] | None,
) -> PackContext:
    return PackContext(
        activated_kinds=_ALL_KINDS,
        activated_mission_types=frozenset({_MISSION_TYPE}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=directives,
        activated_tactics=tactics,
    )


def _delivered_tactics(
    repo_root: Path,
    *,
    with_edge: bool,
    directives: frozenset[str] | None,
    tactics: frozenset[str] | None,
) -> frozenset[str]:
    _write_overlay(repo_root, with_edge=with_edge)
    with patch("charter.activation._drg_helpers.load_validated_graph", return_value=_merged_graph(with_edge=with_edge)):
        bundle = _load_action_governance_bundle(
            repo_root=repo_root,
            action=_ACTION,
            effective_depth=2,
            mission_type=_MISSION_TYPE,
            pack_context=_pack_context(repo_root, directives=directives, tactics=tactics),
        )
    return frozenset(bundle.tactic_ids)


_EXPLICIT_TACTICS = frozenset({_REACH_ONLY, _EDGELESS_SYNTH, _HAND_AUTHORED, _CONTROL})
_DIRECTIVE_ON = frozenset({_DIRECTIVE_STEM})


def test_reach_only_tactic_delivered_via_directive_edge(tmp_path: Path) -> None:
    delivered = _delivered_tactics(tmp_path, with_edge=True, directives=_DIRECTIVE_ON, tactics=_EXPLICIT_TACTICS)

    assert _REACH_ONLY in delivered
    assert _CONTROL in delivered  # control: the fixture delivers tactics at all


def test_edge_removed_tactic_is_not_delivered_on_the_same_fixture(tmp_path: Path) -> None:
    delivered = _delivered_tactics(tmp_path, with_edge=False, directives=_DIRECTIVE_ON, tactics=_EXPLICIT_TACTICS)

    assert _REACH_ONLY not in delivered
    assert _CONTROL in delivered


def test_deactivated_directive_removes_tactic_but_not_unrelated_activated_tactic(tmp_path: Path) -> None:
    delivered = _delivered_tactics(tmp_path, with_edge=True, directives=frozenset(), tactics=_EXPLICIT_TACTICS)

    assert _REACH_ONLY not in delivered
    assert _CONTROL in delivered


def test_explicit_list_containing_the_tactic_does_not_make_it_a_root(tmp_path: Path) -> None:
    on = _delivered_tactics(tmp_path, with_edge=True, directives=_DIRECTIVE_ON, tactics=_EXPLICIT_TACTICS)
    off = _delivered_tactics(tmp_path, with_edge=True, directives=frozenset(), tactics=_EXPLICIT_TACTICS)

    assert _REACH_ONLY in on
    assert _REACH_ONLY not in off


def test_absent_activated_tactics_key_is_not_a_root_but_edge_still_delivers(tmp_path: Path) -> None:
    off = _delivered_tactics(tmp_path, with_edge=True, directives=frozenset(), tactics=None)
    on = _delivered_tactics(tmp_path, with_edge=True, directives=_DIRECTIVE_ON, tactics=None)

    assert _REACH_ONLY not in off
    assert _CONTROL in off  # absent key still seeds every non-reach-only tactic
    assert _REACH_ONLY in on


def test_edgeless_synthesized_and_hand_authored_tactics_remain_roots(tmp_path: Path) -> None:
    delivered = _delivered_tactics(tmp_path, with_edge=True, directives=frozenset(), tactics=_EXPLICIT_TACTICS)

    assert _EDGELESS_SYNTH in delivered
    assert _HAND_AUTHORED in delivered


def test_reach_only_tactic_ids_lists_only_directive_suggests_targets(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(tmp_path, with_edge=True)

    ids = reach_only_tactic_ids(tmp_path)

    assert ids == frozenset({_REACH_ONLY})
    assert _EDGELESS_SYNTH not in ids
    assert _HAND_AUTHORED not in ids


def test_reach_only_tactic_ids_empty_without_overlay_or_edge(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    assert reach_only_tactic_ids(tmp_path) == frozenset()  # no overlay
    _write_overlay(tmp_path, with_edge=False)
    assert reach_only_tactic_ids(tmp_path) == frozenset()  # overlay, no edge


def test_reach_only_tactic_ids_degrades_on_invalid_overlay(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(tmp_path, with_edge=True)
    (tmp_path / ".kittify" / "charter-packs" / "graph.yaml").write_text("nodes: [\n  {urn: broken\n", encoding="utf-8")

    assert reach_only_tactic_ids(tmp_path) == frozenset()


def test_classify_delivers_reach_only_tactic_from_a_seeded_directive() -> None:
    graph = _merged_graph(with_edge=True)

    delivered = _classify_artifact_urns(
        {_ACTION_URN},
        graph,
        {_DIRECTIVE_ID},
        set(),  # reach-only tactic is not a seed
        set(),
        action_urn=_ACTION_URN,
    )
    undelivered = _classify_artifact_urns(
        {_ACTION_URN},
        graph,
        set(),
        set(),
        set(),
        action_urn=_ACTION_URN,
    )

    assert _REACH_ONLY in delivered["tactics"]
    assert _REACH_ONLY not in undelivered["tactics"]
