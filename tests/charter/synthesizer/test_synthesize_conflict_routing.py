"""WP02 — merged-overlay conflict routing (report, not crash).

Covers T007-T010 (`kitty-specs/charter-synthesize-reconciliation-01KZJQN6/
tasks/WP02-merged-overlay-conflict-routing.md`): ``validation_gate.validate``
receives WP01's classified ``ReconciliationConflict`` sequence in-memory
(widened signature, no ``.reconcile-conflicts.json`` sidecar) and makes the
suppress-vs-raise routing decision:

- ``provenance="preserved"`` (content that survived only because the
  reconciliation seam preserved it, not because the current run emitted it)
  is suppressed — already reported via ``ReconciliationDelta.conflicts`` —
  and must NOT raise (NFR-003: no silent-loss input may crash instead).
- ``provenance="new_emit"`` (the current run's own output colliding with
  itself or the built-in layer) remains a hard error, unchanged.

Two layers of coverage:

1. ``TestPreserved*``/``TestNewEmit*``/``TestUnrelatedErrors*`` call
   ``validation_gate.validate`` directly — the same pattern
   ``test_validation_gate.py`` already uses — with hand-built
   ``ReconciliationConflict`` objects standing in for WP01's classification.
   These pin the routing decision in isolation, independent of any one
   caller's wiring.
2. ``TestFullPipeline*`` drives the REAL ``orchestrator.synthesize()`` entry
   point end-to-end (``orchestrator.py``'s ``_validation_callback`` now
   threads ``outcome.delta.conflicts`` into ``validate()`` — the WP01<->WP02
   integration seam wired under documented ownership leeway, since a widened
   ``validate()`` nothing calls with conflicts does not satisfy NFR-003 in
   practice). These prove the suppression is not just correct in isolation
   but actually reachable from a real synthesize() run.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, cast

import pytest
from ruamel.yaml import YAML

from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize
from charter.activation.synthesizer.errors import ProjectDRGValidationError
from charter.activation.synthesizer.reconcile import _RECONCILE_REMEDIATIONS, ReconciliationConflict, _edge_label
from charter.activation.synthesizer.validation_gate import _edge_conflict_key, validate
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers (mirrors test_validation_gate.py's local graph-building pattern)
# ---------------------------------------------------------------------------


def _make_shipped_graph(
    nodes: list[tuple[str, NodeKind]] | None = None,
    edges: list[tuple[str, str, Relation]] | None = None,
) -> DRGGraph:
    drg_nodes = [DRGNode(urn=urn, kind=kind) for urn, kind in (nodes or [])]
    drg_edges = [DRGEdge(source=src, target=tgt, relation=rel) for src, tgt, rel in (edges or [])]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-04-17T00:00:00+00:00",
        generated_by="test-shipped-layer",
        nodes=drg_nodes,
        edges=drg_edges,
    )


def _make_overlay(
    nodes: list[tuple[str, NodeKind]] | None = None,
    edges: list[tuple[str, str, Relation]] | None = None,
) -> DRGGraph:
    drg_nodes = [DRGNode(urn=urn, kind=kind) for urn, kind in (nodes or [])]
    drg_edges = [DRGEdge(source=src, target=tgt, relation=rel) for src, tgt, rel in (edges or [])]
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-04-17T12:00:00+00:00",
        generated_by="spec-kitty charter synthesize 0.1.0",
        nodes=drg_nodes,
        edges=drg_edges,
    )


def _write_overlay(staging_dir: Path, graph: DRGGraph) -> None:
    """Write a DRGGraph YAML to staging_dir/doctrine/graph.yaml."""
    doctrine_dir = staging_dir / "charter-packs"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    graph_path = doctrine_dir / "graph.yaml"

    nodes_data = [
        {"urn": n.urn, "kind": n.kind.value, **({"label": n.label} if n.label else {})} for n in graph.nodes
    ]
    edges_data = [{"source": e.source, "target": e.target, "relation": e.relation.value} for e in graph.edges]
    payload = {
        "schema_version": graph.schema_version,
        "generated_at": graph.generated_at,
        "generated_by": graph.generated_by,
        "nodes": nodes_data,
        "edges": edges_data,
    }
    yaml = YAML()
    yaml.default_flow_style = False
    buf = io.StringIO()
    yaml.dump(payload, buf)
    graph_path.write_text(buf.getvalue())


def _edge_key(source: str, relation: Relation, target: str) -> str:
    """Same label format ``validation_gate._edge_conflict_key`` builds."""
    return f"{source}--{relation.value}-->{target}"


# ---------------------------------------------------------------------------
# Case 1 — preserved duplicate-triple: reported, not raised
# ---------------------------------------------------------------------------


class TestPreservedDuplicateTripleIsReportedNotRaised:
    def test_preserved_duplicate_edge_does_not_raise(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph(nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)])
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
                # A second, identical (source, target, relation) triple -- the
                # kind of leftover on-disk repeat reconciliation preserves.
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
            ],
        )
        _write_overlay(tmp_path, overlay)

        conflict = ReconciliationConflict(
            kind="duplicate_triple",
            target_id=_edge_key("directive:PROJECT_001", Relation.REQUIRES, "directive:DIRECTIVE_003"),
            backing_artifact=None,
            remediation=_RECONCILE_REMEDIATIONS["duplicate_triple"],
            provenance="preserved",
        )
        assert conflict.remediation, "reported conflict class must carry a non-empty remediation"

        validate(tmp_path, shipped, conflicts=(conflict,))  # must not raise

    def test_same_duplicate_without_conflict_routing_still_raises(self, tmp_path: Path) -> None:
        """Control: without the conflict, the pre-WP02 hard-fail is unchanged."""
        shipped = _make_shipped_graph(nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)])
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
            ],
        )
        _write_overlay(tmp_path, overlay)

        with pytest.raises(ProjectDRGValidationError):
            validate(tmp_path, shipped)


# ---------------------------------------------------------------------------
# Case 2 — preserved dangling endpoint: reported, not raised
# ---------------------------------------------------------------------------


class TestPreservedDanglingEndpointIsReportedNotRaised:
    def test_preserved_dangling_target_does_not_raise(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph()
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[
                # Target URN absent from both the current built-in snapshot
                # and the overlay's own nodes -- a preserved edge whose
                # endpoint the current run no longer emits.
                ("directive:PROJECT_001", "tactic:retired-legacy-tactic", Relation.APPLIES),
            ],
        )
        _write_overlay(tmp_path, overlay)

        conflict = ReconciliationConflict(
            kind="preserved_dangling_endpoint",
            target_id=_edge_key("directive:PROJECT_001", Relation.APPLIES, "tactic:retired-legacy-tactic"),
            backing_artifact=".kittify/charter-packs/tactic/retired-legacy-tactic.tactic.yaml",
            remediation=_RECONCILE_REMEDIATIONS["preserved_dangling_endpoint"],
            provenance="preserved",
        )
        assert conflict.remediation, "reported conflict class must carry a non-empty remediation"

        validate(tmp_path, shipped, conflicts=(conflict,))  # must not raise; graph not silently truncated

    def test_same_dangling_edge_without_conflict_routing_still_raises(self, tmp_path: Path) -> None:
        """Control: without the conflict, the pre-WP02 hard-fail is unchanged."""
        shipped = _make_shipped_graph()
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[("directive:PROJECT_001", "tactic:retired-legacy-tactic", Relation.APPLIES)],
        )
        _write_overlay(tmp_path, overlay)

        with pytest.raises(ProjectDRGValidationError):
            validate(tmp_path, shipped)


# ---------------------------------------------------------------------------
# Case 3 — new-emit collision still raises (regression guard)
# ---------------------------------------------------------------------------


class TestNewEmitCollisionStillRaises:
    def test_new_emit_duplicate_edge_still_raises(self, tmp_path: Path) -> None:
        """A ``new_emit`` conflict is left untouched -- the additive guard still bites."""
        shipped = _make_shipped_graph(nodes=[("directive:DIRECTIVE_003", NodeKind.DIRECTIVE)])
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
                ("directive:PROJECT_001", "directive:DIRECTIVE_003", Relation.REQUIRES),
            ],
        )
        _write_overlay(tmp_path, overlay)

        conflict = ReconciliationConflict(
            kind="duplicate_triple",
            target_id=_edge_key("directive:PROJECT_001", Relation.REQUIRES, "directive:DIRECTIVE_003"),
            backing_artifact=None,
            remediation=_RECONCILE_REMEDIATIONS["duplicate_triple"],
            provenance="new_emit",
        )

        with pytest.raises(ProjectDRGValidationError) as exc_info:
            validate(tmp_path, shipped, conflicts=(conflict,))
        assert any("Duplicate" in e for e in exc_info.value.errors)

    def test_conflict_not_classified_preserved_still_raises(self, tmp_path: Path) -> None:
        """Belt-and-suspenders: only an explicit ``preserved`` provenance suppresses."""
        shipped = _make_shipped_graph()
        overlay = _make_overlay(
            nodes=[("directive:PROJECT_001", NodeKind.DIRECTIVE)],
            edges=[("directive:PROJECT_001", "directive:GHOST", Relation.REQUIRES)],
        )
        _write_overlay(tmp_path, overlay)

        conflict = ReconciliationConflict(
            kind="preserved_dangling_endpoint",
            target_id=_edge_key("directive:PROJECT_001", Relation.REQUIRES, "directive:GHOST"),
            backing_artifact=None,
            remediation=_RECONCILE_REMEDIATIONS["preserved_dangling_endpoint"],
            provenance="new_emit",
        )

        with pytest.raises(ProjectDRGValidationError):
            validate(tmp_path, shipped, conflicts=(conflict,))


# ---------------------------------------------------------------------------
# Unrelated errors (e.g. cycles) still raise even with suppressed conflicts
# ---------------------------------------------------------------------------


class TestUnrelatedErrorsStillRaiseAlongsideSuppressedConflicts:
    def test_cycle_error_survives_when_an_unrelated_conflict_is_suppressed(self, tmp_path: Path) -> None:
        shipped = _make_shipped_graph()
        overlay = _make_overlay(
            nodes=[
                ("directive:PROJECT_001", NodeKind.DIRECTIVE),
                ("directive:PROJECT_002", NodeKind.DIRECTIVE),
            ],
            edges=[
                ("directive:PROJECT_001", "directive:PROJECT_002", Relation.REQUIRES),
                ("directive:PROJECT_002", "directive:PROJECT_001", Relation.REQUIRES),
                # An unrelated preserved dangling edge that must be suppressed
                # without hiding the genuine cycle above.
                ("directive:PROJECT_001", "tactic:retired-legacy-tactic", Relation.APPLIES),
            ],
        )
        _write_overlay(tmp_path, overlay)

        conflict = ReconciliationConflict(
            kind="preserved_dangling_endpoint",
            target_id=_edge_key("directive:PROJECT_001", Relation.APPLIES, "tactic:retired-legacy-tactic"),
            backing_artifact=None,
            remediation=_RECONCILE_REMEDIATIONS["preserved_dangling_endpoint"],
            provenance="preserved",
        )

        with pytest.raises(ProjectDRGValidationError) as exc_info:
            validate(tmp_path, shipped, conflicts=(conflict,))
        assert any("Cycle" in e or "cycle" in e for e in exc_info.value.errors)
        assert not any("retired-legacy-tactic" in e for e in exc_info.value.errors), (
            "suppressed preserved-dangling conflict leaked into the surfaced errors"
        )


# ---------------------------------------------------------------------------
# Full-pipeline coverage (orchestrator.synthesize() end-to-end)
#
# These prove the WP01<->WP02 integration seam wired into
# orchestrator.py's _validation_callback (outcome.delta.conflicts threaded
# into validate()) actually suppresses a preserved conflict reached through
# a real synthesize() run, and that a new-emit conflict reached the same way
# still raises.
# ---------------------------------------------------------------------------

_LEGACY_URN = "tactic:legacy-preference-order-3270"


def _graph_yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    return yaml


def _load_graph(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", _graph_yaml().load(path.read_text()))


def _dump_graph(path: Path, data: dict[str, Any]) -> None:
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


def _inject_legacy_node_with_duplicate_edge(tmp_path: Path) -> None:
    """Preserved node whose own on-disk edge repeats itself (duplicate triple).

    Both copies of the ``(legacy_urn, DIRECTIVE_003, applies)`` triple belong
    to a node the current run's target set does not re-emit, so both are
    ``provenance="preserved"`` once reconciled — this is the leftover-content
    shape amendment #3 describes, not a collision the current run created.
    """
    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    graph_path = doctrine_dir / "graph.yaml"
    graph = _load_graph(graph_path)
    graph["nodes"].append(
        {"urn": _LEGACY_URN, "kind": "tactic", "label": "Legacy Preference Order Tactic (3270)"}
    )
    duplicate_edge = {
        "source": _LEGACY_URN,
        "target": "directive:DIRECTIVE_003",
        "relation": "applies",
        "reason": "Derived from synthesis target 'legacy-preference-order-3270'",
    }
    graph.setdefault("edges", []).append(duplicate_edge)
    graph["edges"].append(dict(duplicate_edge))  # exact repeat -> duplicate_triple
    _dump_graph(graph_path, graph)

    existing_artifact = doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    legacy_artifact = doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    legacy_artifact.write_bytes(existing_artifact.read_bytes())


def _inject_legacy_node_with_dangling_edge(tmp_path: Path) -> None:
    """Preserved node whose on-disk edge targets a URN nothing emits anymore."""
    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    graph_path = doctrine_dir / "graph.yaml"
    graph = _load_graph(graph_path)
    graph["nodes"].append(
        {"urn": _LEGACY_URN, "kind": "tactic", "label": "Legacy Preference Order Tactic (3270)"}
    )
    graph.setdefault("edges", []).append(
        {
            "source": _LEGACY_URN,
            "target": "tactic:retired-nothing-emits-this",
            "relation": "applies",
            "reason": "Derived from synthesis target 'legacy-preference-order-3270'",
        }
    )
    _dump_graph(graph_path, graph)

    existing_artifact = doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    legacy_artifact = doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    legacy_artifact.write_bytes(existing_artifact.read_bytes())


class TestFullPipelinePreservedConflictIsSuppressed:
    """Preserved-content conflicts reached through a real synthesize() run."""

    def test_preserved_duplicate_triple_does_not_raise_and_is_reported(
        self,
        minimal_interview_snapshot: dict[str, Any],
        minimal_doctrine_snapshot: dict[str, Any],
        minimal_drg_snapshot: dict[str, Any],
        fixture_adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        req_a = _request(
            "01AAAAAAAAAAAAAAAAAAAAAAAAA",
            minimal_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

        _inject_legacy_node_with_duplicate_edge(tmp_path)

        req_b = _request(
            "01BBBBBBBBBBBBBBBBBBBBBBBBB",
            minimal_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        # Must not raise -- pre-integration-wiring, this crashed via
        # validate_graph's duplicate-edge hard-fail (the exact P0 this seam
        # closes).
        result = synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

        assert result.reconciliation is not None
        reported = [c for c in result.reconciliation.conflicts if c.kind == "duplicate_triple"]
        assert reported, "expected the preserved duplicate triple on delta.conflicts"
        assert all(c.provenance == "preserved" for c in reported)
        assert all(c.remediation for c in reported)

    def test_preserved_dangling_endpoint_does_not_raise_and_is_reported(
        self,
        minimal_interview_snapshot: dict[str, Any],
        minimal_doctrine_snapshot: dict[str, Any],
        minimal_drg_snapshot: dict[str, Any],
        fixture_adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        req_a = _request(
            "01AAAAAAAAAAAAAAAAAAAAAAAAA",
            minimal_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

        _inject_legacy_node_with_dangling_edge(tmp_path)

        req_b = _request(
            "01BBBBBBBBBBBBBBBBBBBBBBBBB",
            minimal_interview_snapshot,
            minimal_doctrine_snapshot,
            minimal_drg_snapshot,
        )
        result = synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

        assert result.reconciliation is not None
        reported = [c for c in result.reconciliation.conflicts if c.kind == "preserved_dangling_endpoint"]
        assert reported, "expected the preserved dangling endpoint on delta.conflicts"
        assert all(c.provenance == "preserved" for c in reported)
        assert all(c.remediation for c in reported)

        # NFR-003: graph not silently truncated -- the preserved node survives.
        graph_path = tmp_path / ".kittify" / "charter-packs" / "graph.yaml"
        surviving_urns = {n["urn"] for n in _load_graph(graph_path)["nodes"]}
        assert _LEGACY_URN in surviving_urns


class TestFullPipelineNewEmitCollisionStillRaises:
    """A new-emit conflict reached through a real synthesize() run still hard-fails.

    ``build_targets()`` runs an EC-2 early gate (``_validate_source_urns``)
    that rejects any *explicit* interview-mapped ``source_urns`` not already
    present in ``drg_snapshot`` before a target is even built -- so a
    "current run references a URN nothing defines" scenario can never reach
    reconciliation/``validate()`` through the real mapped-target path (only
    through the ``request.target`` fallback, which -- per
    ``test_synthesize_reconcile.py``'s BLOCKER #1 test docstring -- is
    itself unreachable through ``synthesize()`` for any real interview
    snapshot: ``mission_type`` has ``requires_nonempty=False`` and always
    yields >=1 mapped target). The reachable "current target collides"
    shape is exactly what the WP text names: a target's OWN freshly emitted
    edge duplicating one already in the BUILT-IN layer -- caught by
    ``emit_project_layer``'s FR-020 additive-only guard, unchanged by this
    WP. Pre-seeding ``drg_snapshot`` with the tactic's own about-to-be-
    emitted triple exercises exactly that guard end-to-end.
    """

    def test_new_emit_edge_colliding_with_built_in_still_raises(
        self,
        fixture_adapter: FixtureAdapter,
        tmp_path: Path,
    ) -> None:
        interview = {"selected_directives": ["DIRECTIVE_003"]}
        doctrine = {
            "directives": {
                "DIRECTIVE_003": {
                    "id": "DIRECTIVE_003",
                    "title": "Decision Documentation",
                    "body": "Document significant architectural decisions via ADRs.",
                }
            },
            "tactics": {},
            "styleguides": {},
        }
        # The built-in layer already carries the EXACT triple the
        # "how-we-apply-directive-003" tactic target is about to emit
        # (tactic:how-we-apply-directive-003 --applies--> directive:DIRECTIVE_003).
        drg = {
            "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
            "edges": [
                {
                    "source": "tactic:how-we-apply-directive-003",
                    "target": "directive:DIRECTIVE_003",
                    "relation": "applies",
                }
            ],
            "schema_version": "1",
        }
        target = SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )
        request = SynthesisRequest(
            target=target,
            interview_snapshot=interview,
            doctrine_snapshot=doctrine,
            drg_snapshot=drg,
            run_id="01NEWEMITCOLLISIONTEST0001",
            adapter_hints={"language": "python"},
        )

        with pytest.raises(ProjectDRGValidationError) as exc_info:
            synthesize(request, adapter=fixture_adapter, repo_root=tmp_path)
        assert any("Duplicate edge" in e for e in exc_info.value.errors)


# ---------------------------------------------------------------------------
# Edge-label format parity (reconcile._edge_label <-> validation_gate._edge_conflict_key)
# ---------------------------------------------------------------------------


def test_edge_conflict_key_matches_reconcile_edge_label() -> None:
    """The two independently-declared edge-label formats must stay identical.

    ``validation_gate._edge_conflict_key`` intentionally hand-reconstructs
    ``reconcile._edge_label``'s ``f"{source}--{relation.value}-->{target}"``
    format rather than importing the private helper — see
    ``validation_gate._edge_conflict_key``'s docstring for the documented
    ownership-boundary rationale (this module's only dependency on the
    reconciliation seam stays at the public ``ReconciliationConflict``
    shape). That means the two formats can drift silently if either one is
    edited without the other; this test is the binding parity check that
    fails loudly on drift instead.
    """
    edge = DRGEdge(source="tactic:x", target="directive:DIRECTIVE_003", relation=Relation.APPLIES)
    assert _edge_conflict_key(edge) == _edge_label(edge)
