"""WP01 — library reconciliation seam tests (charter-synthesize-reconciliation).

Companion to the committed red-first ``test_synthesize_node_preservation.py``
(#3270 node/edge preservation). This module covers the T006 numbered cases
from ``kitty-specs/charter-synthesize-reconciliation-01KZJQN6/tasks/
WP01-library-reconciliation-seam.md``:

1. No-op byte-stability (graph.yaml AND manifest) across an identical
   re-synthesis (extends #1912 to the reconcile path).
2. Manifest version-skew reconciliation.
3. Delta shape: a superset on-disk overlay yields non-empty
   ``retained``/``removable``.
4. BLOCKER #1 (FR-009 unlink path): a zero/subset-emit run over a backed
   on-disk overlay must not unlink the preserved ``graph.yaml``.
5. BLOCKER #2 (FR-007 fail-closed AT THE SEAM): a corrupt on-disk overlay
   makes a direct ``synthesize(...)`` call raise, with no write.

Plus: the reconciliation-conflict remediation completeness gate (mirrors
``charter.offering.drg.merge``'s ``test_every_conflict_class_carries_a_remediation_line``),
and focused unit coverage for the new helpers in ``reconcile.py`` (Sonar:
"every new branch/helper needs tests in the same PR").
"""

from __future__ import annotations

import io
import typing
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
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    SynthesisManifest,
    finalize_manifest,
    load_yaml as load_manifest,
)
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.activation.synthesizer.reconcile import (
    ManifestDelta,
    ManifestEntryRef,
    NodeOrEdgeRef,
    ReconciliationConflict,
    ReconciliationDelta,
    ReconciliationOutcome,
    SynthesizeMode,
    _RECONCILE_REMEDIATIONS,
    _backing_path_by_urn,
    apply_prune,
    reconcile_synthesis,
)
from charter.activation.synthesizer.project_drg import apply_post_condition
from charter.offering.drg.loader import DRGLoadError
from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.unit]

_LEGACY_URN = "tactic:legacy-preference-order-3270"
_LEGACY_EDGE_TARGET = "directive:DIRECTIVE_003"


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_synthesize_node_preservation.py's pattern)
# ---------------------------------------------------------------------------


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


def _inject_legacy_overlay_content(tmp_path: Path) -> tuple[Path, Path]:
    """Append the #3270 legacy tactic node+edge to the on-disk overlay.

    Returns ``(graph_path, legacy_artifact_path)``. Mirrors the committed
    preservation test's injection so a "backed" (artifact file present)
    on-disk-only node exists for the current run's target set to omit.
    """
    doctrine_dir = tmp_path / ".kittify" / "doctrine"
    graph_path = doctrine_dir / "graph.yaml"
    graph = _load_graph(graph_path)
    graph["nodes"].append(
        {"urn": _LEGACY_URN, "kind": "tactic", "label": "Legacy Preference Order Tactic (3270)"}
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

    existing_artifact = doctrine_dir / "tactic" / "how-we-apply-directive-003.tactic.yaml"
    legacy_artifact = doctrine_dir / "tactic" / "legacy-preference-order-3270.tactic.yaml"
    legacy_artifact.write_bytes(existing_artifact.read_bytes())
    return graph_path, legacy_artifact


# ---------------------------------------------------------------------------
# Case 1 — no-op byte-stability (graph.yaml AND manifest)
# ---------------------------------------------------------------------------


def test_noop_resynthesis_is_byte_stable_for_graph_and_manifest(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """NFR-002: an identical re-synthesis leaves graph.yaml + manifest untouched.

    Extends the pre-existing #1912 provenance/manifest byte-stability guard
    to the reconcile path, and additionally pins graph.yaml (not previously
    covered by ``TestNoOpStableSynthesis``).
    """
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    manifest_path = tmp_path / MANIFEST_PATH
    graph_before = graph_path.read_bytes()
    manifest_before = manifest_path.read_bytes()

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

    assert graph_path.read_bytes() == graph_before, "no-op re-synthesis churned graph.yaml"
    assert manifest_path.read_bytes() == manifest_before, "no-op re-synthesis churned the manifest"


# ---------------------------------------------------------------------------
# Case 2 — manifest version-skew reconciliation
# ---------------------------------------------------------------------------


def test_manifest_version_skew_is_reconciled_on_next_synthesize(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """A manifest registering fewer artifacts than the graph must self-heal.

    Simulates version-skew (e.g. an older tool truncated the manifest) by
    stripping one artifact entry from the on-disk manifest while its backing
    artifact file and graph node survive untouched. The SAME target set is
    re-synthesized (so the stripped artifact is genuinely regenerated this
    run) — the manifest must register it again afterwards (no permanent
    manifest-narrower-than-graph skew), with the SAME content_hash as before
    (the artifact body did not change).
    """
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    manifest_path = tmp_path / MANIFEST_PATH
    manifest = load_manifest(manifest_path)
    assert len(manifest.artifacts) >= 2, "fixture setup expected >=2 synthesized artifacts"
    dropped = manifest.artifacts[0]

    # Strip the entry (simulate skew) — leave the artifact file + graph node
    # in place untouched.
    skewed = manifest.model_copy(
        update={"artifacts": [e for e in manifest.artifacts if e is not dropped]}
    )
    manifest_path.write_text(
        canonical_yaml(skewed.model_dump(mode="python")).decode("utf-8"),
        encoding="utf-8",
    )
    assert dropped.kind not in {e.kind for e in load_manifest(manifest_path).artifacts if e.slug == dropped.slug}

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

    healed = load_manifest(manifest_path)
    healed_entry = next(
        (e for e in healed.artifacts if e.kind == dropped.kind and e.slug == dropped.slug), None
    )
    assert healed_entry is not None, (
        f"manifest version-skew was not reconciled: {dropped.kind}:{dropped.slug} "
        "missing from the manifest after synthesize()"
    )
    assert healed_entry.content_hash == dropped.content_hash, (
        "reconciled entry's content_hash must match the unchanged artifact body"
    )


# ---------------------------------------------------------------------------
# Case 3 — delta shape: superset overlay -> retained + removable populated
# ---------------------------------------------------------------------------


def test_delta_shape_reports_retained_and_removable_for_superset_overlay(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """A superset on-disk overlay yields a non-empty ``retained``/``removable``.

    Under the ``preserve`` default, ``removable`` describes the SAME
    preserved-but-untargeted content ``retained`` reports (data-model.md:
    "removable ... here default preserve retains them") — both non-empty
    together, distinguished only by intent (what a ``--prune`` run would
    act on).
    """
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)
    _inject_legacy_overlay_content(tmp_path)

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    result = synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

    assert result.reconciliation is not None
    delta = result.reconciliation
    retained_urns = {ref.urn for ref in delta.retained}
    removable_urns = {ref.urn for ref in delta.removable}

    assert _LEGACY_URN in retained_urns, f"expected {_LEGACY_URN!r} in delta.retained, got {retained_urns}"
    assert _LEGACY_URN in removable_urns, (
        f"expected {_LEGACY_URN!r} in delta.removable (preserve-mode candidate), got {removable_urns}"
    )
    assert any(
        ref.ref_kind == "edge" and ref.urn.startswith(_LEGACY_URN) for ref in delta.retained
    ), "expected the legacy tactic's applies-edge in delta.retained too (FR-002 atomicity)"


# ---------------------------------------------------------------------------
# Case 4 — BLOCKER #1: FR-009 post-condition driven by the MERGED graph
# ---------------------------------------------------------------------------


def test_zero_emit_reconciliation_does_not_unlink_preserved_graph(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """Amendment #1 (BLOCKER): a zero-node fresh emit must not delete graph.yaml.

    Going through the public ``synthesize()`` entry point cannot literally
    reach a zero-node fresh emit: both ``run_all`` and orchestrator's own
    target computation share the SAME "if not targets: targets =
    [request.target]" fallback, and ``request.target`` is always a supported
    (directive/tactic/styleguide) kind in every real caller — so the fresh
    emit is always >= 1 node through that path. This test instead drives the
    exact two production functions the amendment's fix touches —
    ``reconcile.reconcile_synthesis`` (computes ``merged_overlay`` from a
    hand-built EMPTY fresh emit against REAL on-disk backed content) and
    ``project_drg.apply_post_condition`` (the FR-009 post-condition that
    amendment #1 requires be driven from the MERGED graph, not the fresh
    emit) — against a REAL on-disk overlay established via a genuine prior
    ``synthesize()`` call. Pre-fix, wiring ``has_project_graph`` from the
    (empty) fresh emit here would unlink the preserved ``graph.yaml``; this
    pins that it must not.
    """
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    assert graph_path.exists(), "prior synthesis did not establish a backed overlay"
    manifest_path = tmp_path / MANIFEST_PATH
    assert load_manifest(manifest_path).built_in_only is False

    built_in_drg = DRGGraph.model_validate(
        {
            **minimal_drg_snapshot,
            "schema_version": "1.0",
            "generated_at": "1970-01-01T00:00:00+00:00",
            "generated_by": "test",
        }
    )
    empty_fresh_overlay = DRGGraph(
        schema_version="1.0", generated_at="1970-01-01T00:00:00+00:00", generated_by="test", nodes=[], edges=[]
    )

    outcome = reconcile_synthesis(
        repo_root=tmp_path,
        fresh_overlay=empty_fresh_overlay,
        new_results=[],
        run_id="01CCCCCCCCCCCCCCCCCCCCCCCCC",
        built_in_drg=built_in_drg,
    )

    # The merged overlay must still carry the backed content even though this
    # run's fresh emit is empty.
    assert outcome.merged_overlay.nodes, "merged overlay lost all preserved content on a zero-emit run"

    apply_post_condition(tmp_path, has_project_graph=bool(outcome.merged_overlay.nodes))

    assert graph_path.exists(), (
        "BLOCKER #1 regression: apply_post_condition unlinked the preserved "
        "graph.yaml on a zero-emit reconciliation run"
    )
    assert load_manifest(manifest_path).built_in_only is False, (
        "BLOCKER #1 regression: manifest flipped to built_in_only=True despite preserved content"
    )


# ---------------------------------------------------------------------------
# Case 5 — BLOCKER #2: corrupt on-disk overlay fails closed AT THE SEAM
# ---------------------------------------------------------------------------


def test_corrupt_overlay_fails_closed_at_the_library_seam(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """FR-007: an unparseable on-disk graph.yaml raises via a direct synthesize() call.

    Proven at the library seam (not only the CLI) because the in-process
    activate/deactivate path (WP05) bypasses the CLI guard.
    """
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    manifest_path = tmp_path / MANIFEST_PATH
    manifest_before = manifest_path.read_bytes()

    # Half-written / unparseable YAML (truncated mapping, bad indentation).
    graph_path.write_text("schema_version: '1.0'\nnodes: [\n  {urn: broken\n", encoding="utf-8")

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    with pytest.raises(DRGLoadError):
        synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path)

    assert manifest_path.read_bytes() == manifest_before, "live manifest must not be rewritten on fail-closed"


# ---------------------------------------------------------------------------
# Bonus: mode-seam smoke tests (dry_run writes nothing; prune excises removable)
# ---------------------------------------------------------------------------


def test_dry_run_mode_computes_delta_without_writing(
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
    _inject_legacy_overlay_content(tmp_path)
    manifest_before = (tmp_path / MANIFEST_PATH).read_bytes()
    graph_before = (tmp_path / ".kittify" / "doctrine" / "graph.yaml").read_bytes()

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    result = synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path, mode=SynthesizeMode.dry_run)

    assert result.reconciliation is not None
    assert _LEGACY_URN in {ref.urn for ref in result.reconciliation.retained}
    assert (tmp_path / MANIFEST_PATH).read_bytes() == manifest_before, "dry_run must not write the manifest"
    assert (tmp_path / ".kittify" / "doctrine" / "graph.yaml").read_bytes() == graph_before, (
        "dry_run must not write graph.yaml"
    )


def test_prune_mode_excises_removable_content(
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
    _inject_legacy_overlay_content(tmp_path)

    req_b = _request(
        "01BBBBBBBBBBBBBBBBBBBBBBBBB",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_b, adapter=fixture_adapter, repo_root=tmp_path, mode=SynthesizeMode.prune)

    graph_path = tmp_path / ".kittify" / "doctrine" / "graph.yaml"
    pruned_urns = {node["urn"] for node in _load_graph(graph_path)["nodes"]}
    assert _LEGACY_URN not in pruned_urns, "--prune must excise removable (preserved-but-untargeted) nodes"


# ---------------------------------------------------------------------------
# Remediation completeness gate (mirrors charter.offering.drg.merge's gate of the
# same name).
# ---------------------------------------------------------------------------


def test_every_conflict_class_carries_a_remediation_line() -> None:
    """Every ``ReconciliationConflict.kind`` needs an operator remediation entry."""
    # ``from __future__ import annotations`` makes __annotations__ strings;
    # resolve them so the gate reads the real Literal members (mirrors
    # charter.offering.drg.merge's test_every_conflict_class_carries_a_remediation_line).
    hints = typing.get_type_hints(ReconciliationConflict)
    declared = set(typing.get_args(hints["kind"]))
    assert declared == {"duplicate_triple", "preserved_dangling_endpoint"}
    assert declared == set(_RECONCILE_REMEDIATIONS), (
        "conflict classes without operator remediation: "
        f"{sorted(declared - set(_RECONCILE_REMEDIATIONS))}; "
        "remediation entries for no conflict class: "
        f"{sorted(set(_RECONCILE_REMEDIATIONS) - declared)}"
    )
    for kind, remediation in _RECONCILE_REMEDIATIONS.items():
        assert remediation, f"{kind} carries an empty remediation string"


def test_reconciliation_conflict_rejects_empty_remediation() -> None:
    with pytest.raises(ValueError, match="carries no remediation"):
        ReconciliationConflict(
            kind="duplicate_triple",
            target_id="tactic:x--applies-->directive:DIRECTIVE_003",
            backing_artifact=None,
            remediation="",
            provenance="preserved",
        )


# ---------------------------------------------------------------------------
# Focused unit coverage for new reconcile.py helpers
# ---------------------------------------------------------------------------


def test_reconciliation_delta_is_empty_when_all_fields_empty() -> None:
    assert ReconciliationDelta().is_empty is True


def test_reconciliation_delta_is_not_empty_with_retained_content() -> None:
    delta = ReconciliationDelta(retained=(NodeOrEdgeRef(ref_kind="node", urn="tactic:x"),))
    assert delta.is_empty is False


def test_manifest_delta_default_is_empty_tuples() -> None:
    delta = ManifestDelta()
    assert delta.retained == ()
    assert delta.added == ()
    assert delta.removable == ()


def test_manifest_entry_ref_defaults_backing_artifact_to_none() -> None:
    ref = ManifestEntryRef(kind="tactic", slug="x")
    assert ref.backing_artifact is None


def test_backing_path_by_urn_resolves_backed_and_orphans_missing(
    minimal_interview_snapshot: dict[str, Any],
    minimal_doctrine_snapshot: dict[str, Any],
    minimal_drg_snapshot: dict[str, Any],
    fixture_adapter: FixtureAdapter,
    tmp_path: Path,
) -> None:
    """MAJOR amendment #4: backed vs orphaned is a real filesystem probe."""
    req_a = _request(
        "01AAAAAAAAAAAAAAAAAAAAAAAAA",
        minimal_interview_snapshot,
        minimal_doctrine_snapshot,
        minimal_drg_snapshot,
    )
    synthesize(req_a, adapter=fixture_adapter, repo_root=tmp_path)

    manifest = load_manifest(tmp_path / MANIFEST_PATH)
    urn_to_path = _backing_path_by_urn(tmp_path, manifest)
    assert urn_to_path, "expected at least one resolvable backing artifact"
    for urn, rel_path in urn_to_path.items():
        assert (tmp_path / rel_path).exists(), f"{urn} maps to a non-existent path {rel_path}"

    # Delete one backing artifact file on disk (orphan it) and confirm the
    # probe no longer resolves it, without touching the manifest/provenance.
    target_urn, target_path = next(iter(urn_to_path.items()))
    (tmp_path / target_path).unlink()
    urn_to_path_after = _backing_path_by_urn(tmp_path, manifest)
    assert target_urn not in urn_to_path_after, "deleting a backing artifact file must orphan its URN"


def test_apply_prune_excises_removable_nodes_edges_and_manifest_entries() -> None:
    """Direct unit coverage for ``apply_prune`` (both the graph AND manifest branches)."""
    from charter.offering.drg.models import DRGEdge, DRGNode, NodeKind, Relation

    keep_node = DRGNode(urn="tactic:keep", kind=NodeKind.TACTIC, label="Keep")
    prune_node = DRGNode(urn="tactic:prune-me", kind=NodeKind.TACTIC, label="Prune me")
    keep_edge = DRGEdge(source="tactic:keep", target="directive:DIRECTIVE_003", relation=Relation.APPLIES)
    prune_edge = DRGEdge(source="tactic:prune-me", target="directive:DIRECTIVE_003", relation=Relation.APPLIES)
    overlay = DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[keep_node, prune_node],
        edges=[keep_edge, prune_edge],
    )

    manifest = finalize_manifest(
        SynthesisManifest(
            mission_id=None,
            created_at="2026-01-01T00:00:00+00:00",
            run_id="01TESTRUNID0000000000000001",
            adapter_id="test",
            adapter_version="0.0.0",
            synthesizer_version="0.0.0",
            manifest_hash="0" * 64,
            artifacts=[
                ManifestArtifactEntry(
                    kind="tactic", slug="keep", path=".kittify/doctrine/tactic/keep.tactic.yaml",
                    provenance_path=".kittify/charter/provenance/tactic-keep.yaml", content_hash="a" * 64,
                ),
                ManifestArtifactEntry(
                    kind="tactic", slug="prune-me", path=".kittify/doctrine/tactic/prune-me.tactic.yaml",
                    provenance_path=".kittify/charter/provenance/tactic-prune-me.yaml", content_hash="b" * 64,
                ),
            ],
        )
    )

    delta = ReconciliationDelta(
        removable=(
            NodeOrEdgeRef(ref_kind="node", urn="tactic:prune-me"),
            NodeOrEdgeRef(ref_kind="edge", urn="tactic:prune-me--Relation.APPLIES-->directive:DIRECTIVE_003"),
        ),
        manifest_delta=ManifestDelta(removable=(ManifestEntryRef(kind="tactic", slug="prune-me"),)),
    )
    outcome = ReconciliationOutcome(merged_overlay=overlay, merged_manifest=manifest, delta=delta)

    pruned = apply_prune(outcome)

    pruned_node_urns = {n.urn for n in pruned.merged_overlay.nodes}
    assert pruned_node_urns == {"tactic:keep"}
    assert all(e.source != "tactic:prune-me" for e in pruned.merged_overlay.edges)
    pruned_manifest_keys = {(e.kind, e.slug) for e in pruned.merged_manifest.artifacts}
    assert pruned_manifest_keys == {("tactic", "keep")}
    # apply_prune preserves the delta as-is (WP03 owns reporting the CLI diff).
    assert pruned.delta is delta


# ---------------------------------------------------------------------------
# Org-aware conflict classification (#4121, squad MAJOR 2)
# ---------------------------------------------------------------------------

_ORG_URN = "procedure:org-runbook"


def _org_reference_overlay() -> DRGGraph:
    from charter.offering.drg.models import DRGEdge, DRGNode, NodeKind, Relation

    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-09-10T00:00:00+00:00",
        generated_by="test-org-reference-overlay",
        nodes=[DRGNode(urn="agent_profile:ops-responder", kind=NodeKind.AGENT_PROFILE)],
        edges=[
            DRGEdge(
                source="agent_profile:ops-responder",
                target=_ORG_URN,
                relation=Relation.REQUIRES,
                provenance="project",
            )
        ],
    )


def _org_base_graph(nodes: list[str]) -> DRGGraph:
    from charter.offering.drg.models import DRGNode, NodeKind

    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-09-10T00:00:00+00:00",
        generated_by="test-org-base",
        nodes=[DRGNode(urn=urn, kind=NodeKind(urn.split(":", 1)[0])) for urn in nodes],
        edges=[],
    )


def test_org_referencing_edge_is_not_classified_dangling_with_org_base(tmp_path: Path) -> None:
    """With the org-chain base, a fresh overlay's org-referencing edge is a
    legitimate reference, not a preserved_dangling_endpoint conflict."""
    fresh = _org_reference_overlay()
    empty_built_in = _org_base_graph([])
    org = _org_base_graph([_ORG_URN])

    outcome = reconcile_synthesis(
        repo_root=tmp_path,
        fresh_overlay=fresh,
        new_results=[],
        run_id="01ORGREFERENCE000000000000000",
        built_in_drg=empty_built_in,
        org_drg=org,
    )
    assert outcome.delta.conflicts == ()


def test_org_referencing_edge_without_org_base_is_classified_dangling(tmp_path: Path) -> None:
    """Regression contrast: the org-blind classifier this fix replaces."""
    fresh = _org_reference_overlay()
    empty_built_in = _org_base_graph([])

    outcome = reconcile_synthesis(
        repo_root=tmp_path,
        fresh_overlay=fresh,
        new_results=[],
        run_id="01ORGREFERENCE000000000000000",
        built_in_drg=empty_built_in,
    )
    assert any(_ORG_URN in conflict.target_id for conflict in outcome.delta.conflicts)
