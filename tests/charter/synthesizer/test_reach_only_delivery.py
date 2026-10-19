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
from charter.activation.synthesizer.reconcile import synthesized_tactic_reason
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


def _write_manifest(repo_root: Path, slugs: tuple[str, ...]) -> None:
    """A synthesis manifest registering *slugs* as synthesized tactics."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, ManifestArtifactEntry, SynthesisManifest, finalize_manifest

    manifest = finalize_manifest(
        SynthesisManifest(
            mission_id=None,
            created_at="2026-10-19T00:00:00+00:00",
            run_id="01TESTRUNID0000000000000001",
            adapter_id="test",
            adapter_version="0.0.0",
            synthesizer_version="0.0.0",
            manifest_hash="0" * 64,
            artifacts=[
                ManifestArtifactEntry(
                    kind="tactic",
                    slug=slug,
                    path=f".kittify/charter-packs/tactic/{slug}.tactic.yaml",
                    provenance_path=f".kittify/charter/provenance/tactic-{slug}.yaml",
                    content_hash="a" * 64,
                )
                for slug in slugs
            ],
        )
    )
    target = repo_root / MANIFEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8")


def _edge_dict(slug: str, *, derived: bool, directive: str = _DIRECTIVE_ID) -> dict[str, str]:
    edge = {"source": f"directive:{directive}", "target": f"tactic:{slug}", "relation": "suggests"}
    edge["reason"] = synthesized_tactic_reason(slug) if derived else "hand-authored"
    return edge


def _write_overlay(
    repo_root: Path,
    *,
    with_edge: bool,
    manifest_slugs: tuple[str, ...] = (_REACH_ONLY, _EDGELESS_SYNTH),
    extra_edges: tuple[dict[str, str], ...] = (),
) -> None:
    """Project overlay: reach-only tactic (+ derived edge), edgeless synthesized tactic, hand-authored tactic."""
    pack = repo_root / ".kittify" / "charter-packs"
    (pack / "tactic").mkdir(parents=True, exist_ok=True)
    for tactic_id in (_REACH_ONLY, _EDGELESS_SYNTH, _HAND_AUTHORED):
        (pack / "tactic" / f"{tactic_id}.tactic.yaml").write_text(_tactic_yaml(tactic_id), encoding="utf-8")
    nodes = [{"urn": f"tactic:{t}", "kind": "tactic", "label": t} for t in (_REACH_ONLY, _EDGELESS_SYNTH, _HAND_AUTHORED)]
    edges = ([_edge_dict(_REACH_ONLY, derived=True)] if with_edge else []) + list(extra_edges)
    (pack / "graph.yaml").write_text(
        yaml.safe_dump({"schema_version": "1.0", "generated_at": "2026-10-19T00:00:00+00:00", "generated_by": "test", "nodes": nodes, "edges": edges}),
        encoding="utf-8",
    )
    _write_manifest(repo_root, manifest_slugs)


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
    merged_has_edge: bool | None = None,
) -> frozenset[str]:
    """Deliver through the real bundle; *merged_has_edge* lets the merged graph differ from the overlay."""
    _write_overlay(repo_root, with_edge=with_edge)
    merged = _merged_graph(with_edge=with_edge if merged_has_edge is None else merged_has_edge)
    with patch("charter.activation._drg_helpers.load_validated_graph", return_value=merged):
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


def test_edge_is_the_only_delivery_route(tmp_path: Path) -> None:
    """Same fixture, same activation: dropping the edge from the merged graph drops the tactic."""
    with_edge = _delivered_tactics(tmp_path, with_edge=True, directives=_DIRECTIVE_ON, tactics=_EXPLICIT_TACTICS)
    without_edge = _delivered_tactics(tmp_path, with_edge=True, directives=_DIRECTIVE_ON, tactics=_EXPLICIT_TACTICS, merged_has_edge=False)

    assert _REACH_ONLY in with_edge
    assert _REACH_ONLY not in without_edge
    assert _CONTROL in without_edge


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


def test_compiler_reference_seeds_exclude_reach_only_tactic(tmp_path: Path) -> None:
    import dataclasses

    from charter.activation.compiler import ConfigActivatedRoots, _direct_root_urns

    _write_overlay(tmp_path, with_edge=True)
    empty = {f.name: [] for f in dataclasses.fields(ConfigActivatedRoots)}
    roots = ConfigActivatedRoots(**{**empty, "tactics": [_REACH_ONLY, _EDGELESS_SYNTH, _CONTROL]})

    urns = _direct_root_urns(roots, tmp_path)

    assert f"tactic:{_REACH_ONLY}" not in urns
    assert {f"tactic:{_EDGELESS_SYNTH}", f"tactic:{_CONTROL}"} <= urns


def test_hand_authored_tactic_with_hand_authored_inbound_edge_stays_a_root(tmp_path: Path) -> None:
    """A manifest-less tactic is never reach-only, whatever edges point at it."""
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(
        tmp_path,
        with_edge=True,
        extra_edges=(_edge_dict(_HAND_AUTHORED, derived=False, directive="DIRECTIVE_010"), _edge_dict(_HAND_AUTHORED, derived=True)),
    )

    assert reach_only_tactic_ids(tmp_path) == frozenset({_REACH_ONLY})


def test_hand_authored_edge_to_a_synthesized_tactic_does_not_make_it_reach_only(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(tmp_path, with_edge=False, extra_edges=(_edge_dict(_EDGELESS_SYNTH, derived=False, directive="DIRECTIVE_010"),))

    assert reach_only_tactic_ids(tmp_path) == frozenset()


def test_org_required_synthesized_tactic_stays_a_root(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(tmp_path, with_edge=True)
    with patch("charter.activation.synthesizer.reach_only.read_org_required_ids", return_value=[_REACH_ONLY]):
        assert reach_only_tactic_ids(tmp_path) == frozenset()
    assert reach_only_tactic_ids(tmp_path) == frozenset({_REACH_ONLY})  # control: not org-required


def test_reach_only_tactic_ids_empty_without_a_manifest(tmp_path: Path) -> None:
    from charter.activation.synthesizer.reach_only import reach_only_tactic_ids

    _write_overlay(tmp_path, with_edge=True, manifest_slugs=())
    assert reach_only_tactic_ids(tmp_path) == frozenset()
