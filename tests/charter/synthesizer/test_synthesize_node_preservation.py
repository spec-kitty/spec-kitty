"""#3270: ``charter synthesize`` must not silently drop pre-existing graph content.

Reproduction for https://github.com/Priivacy-ai/spec-kitty/issues/3270.

Full ``synthesize`` rebuilds ``.kittify/charter-packs/graph.yaml`` purely from the
current run's recomputed target set, with **no reconciliation against the graph
already on disk** (``orchestrator.synthesize._validation_callback`` →
``project_drg.emit_project_layer(targets=targets)`` → whole-file swap in
``write_pipeline.promote``). When the on-disk graph contains nodes/edges the
current target set does not reproduce — e.g. content written by an earlier CLI,
still backed by doctrine artifact files on disk — the rebuild silently deletes
them from the graph index while leaving the artifact files in place, reporting
only "Charter synthesis complete". The node-and-edge-preserving reconciliation
that already exists on the ``resynthesize`` path
(``resynthesize_pipeline._merge_project_overlay``) is never applied here.

This test pins the safety invariant the fix must satisfy: a ``synthesize`` run
must not **silently** drop a graph node — or its edges — that is still backed by
a doctrine artifact on disk. Preserving the content, or refusing/pruning loudly
behind an explicit opt-in, are acceptable remediations; a silent drop is not.
Edge preservation is asserted explicitly because the reporter's dropped
``data-mutation-preference-order`` tactic carried an ``applies`` edge that
vanished with its node — a node-only fix would be incomplete.

Test and remediation land in the same PR, so this is an ordinary red-first
charter-slice test (not ``@pytest.mark.regression`` / ``quarantine``): it fails
against the current lossy rebuild and flips green once reconciliation is added.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from ruamel.yaml import YAML

from charter.activation.synthesizer import (
    FixtureAdapter,
    SynthesisRequest,
    SynthesisTarget,
    synthesize,
)

pytestmark = [pytest.mark.unit]

# A tactic node the current interview/target set will never reproduce, standing
# in for content written into graph.yaml by an earlier CLI whose backing
# artifact file still lives on disk (the reporter's committed state — their
# dropped `data-mutation-preference-order` tactic). Modelled as a tactic with an
# `applies` edge into the built-in DRG so it exercises node *and* edge
# preservation using the exact edge shape synthesize itself emits.
_LEGACY_URN = "tactic:legacy-preference-order-3270"
_LEGACY_EDGE_TARGET = "directive:DIRECTIVE_003"


def _graph_yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    return yaml


def _load_graph(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", _graph_yaml().load(path.read_text()))


def _dump_graph(path: Path, data: dict[str, Any]) -> None:
    import io

    buffer = io.StringIO()
    _graph_yaml().dump(data, buffer)
    path.write_text(buffer.getvalue())


def _request(
    run_id: str,
    interview: dict[str, Any],
    doctrine: dict[str, Any],
    drg: dict[str, Any],
) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot=interview,
        doctrine_snapshot=doctrine,
        drg_snapshot=drg,
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


def test_synthesize_preserves_on_disk_graph_content_backed_by_artifacts(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """A routine re-synthesis must not silently drop live on-disk nodes or edges."""
    # 1. First synthesis establishes graph.yaml + doctrine artifacts on disk.
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    graph_path = doctrine_dir / "graph.yaml"
    assert graph_path.exists(), "first synthesis did not write graph.yaml"

    # 2. Simulate an earlier-CLI tactic: inject an extra node + its `applies`
    #    edge into the on-disk graph, and give it a backing artifact file (clone
    #    an existing tactic) so it is genuinely "live", not an orphan the
    #    rebuild may legitimately prune.
    graph = _load_graph(graph_path)
    graph["nodes"].append(
        {
            "urn": _LEGACY_URN,
            "kind": "tactic",
            "label": "Legacy Preference Order Tactic (3270)",
        }
    )
    graph.setdefault("edges", []).append(
        {
            "source": _LEGACY_URN,
            "target": _LEGACY_EDGE_TARGET,
            "relation": "applies",
            "reason": "Derived from synthesis target 'legacy-preference-order-3270'",
        }
    )
    _dump_graph(graph_path, graph)

    existing_artifact = (
        doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    )
    legacy_artifact = (
        doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    )
    legacy_artifact.write_bytes(existing_artifact.read_bytes())

    assert _LEGACY_URN in graph_path.read_text(), "precondition: legacy content injected"

    # 3. Routine re-synthesis with identical semantic inputs (only run_id
    #    differs, as every real invocation does).
    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

    # 4. The backing artifact file survives (reporter: the .yaml files stay on
    #    disk; only the graph index is truncated) ...
    assert legacy_artifact.exists(), (
        "the backing tactic artifact should remain on disk after re-synthesis"
    )

    merged = _load_graph(graph_path)
    surviving_urns = {node["urn"] for node in merged["nodes"]}
    surviving_edges = {
        (edge["source"], edge["target"], edge["relation"])
        for edge in merged.get("edges", [])
    }

    # ... but neither the node nor its edge may have silently vanished. These
    # are the load-bearing assertions: they fail today because the rebuild
    # overwrites the on-disk graph wholesale, and pass once synthesize
    # reconciles (node- AND edge-preserving) against it.
    assert _LEGACY_URN in surviving_urns, (
        "issue #3270: `charter synthesize` silently dropped graph node "
        f"{_LEGACY_URN!r}, still backed by {legacy_artifact.name} on disk. The "
        "rebuild must reconcile against the on-disk graph — preserve the node, "
        "or refuse/prune loudly behind an explicit opt-in — never delete "
        "unregistered nodes silently."
    )
    assert (_LEGACY_URN, _LEGACY_EDGE_TARGET, "applies") in surviving_edges, (
        "issue #3270: `charter synthesize` silently dropped the edge "
        f"({_LEGACY_URN} --applies--> {_LEGACY_EDGE_TARGET}) belonging to a "
        "preserved node. Reconciliation must preserve edges as well as nodes; a "
        "node-only merge is an incomplete fix."
    )
