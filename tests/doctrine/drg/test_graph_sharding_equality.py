"""WP06 (mission #2680) — behaviour-preserving equality + totality proofs.

These are the correctness gate on the whole sharding migration (WP05 deleted the
``src/charter/offering/graph.yaml`` monolith and replaced it with per-kind
``src/charter/offering/<kind>.graph.yaml`` fragments). They certify that the sharded,
on-disk layout reconstructs *exactly* the same graph the extractor composes in
memory — no node, edge, or node-kind lost or duplicated by the shard/merge round
trip.

**The reference is non-vacuous (DD-11).** It is the ``DRGGraph`` *returned* by
:func:`generate_graph` — the freshly composed / calibrated / deterministically
sorted in-memory graph, written to a throw-away temp directory and never read
back from the sharded files under test. Comparing ``load_built_in_graph()``
against itself (or a re-read of the same fragments) would be always-green and
prove nothing; the reference here is a genuinely independent capture of the
pre-shard graph, produced by the same extractor pipeline that feeds the writer.

* T029 — merged sharded graph equals the reference under the pinned canonical
  contract: node **set**, edge **set**, node/edge **counts**, and ``assert_valid``.
* T030 — partition totality: every populated node-kind owns a fragment; per-kind
  node counts are equal; target-only kinds (e.g. ``template``) survive the round
  trip.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from charter.offering.drg.loader import (
    built_in_graph_source,
    load_built_in_graph,
    load_graph,
)
from charter.offering.drg.migration.extractor import _dump_graph_document
from charter.offering.drg.migration.hand_authored_overlay import (
    generate_reference_graph_with_overlay,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode
from charter.offering.drg.validator import assert_valid

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.corpus]

_FRAGMENT_SUFFIX = ".graph.yaml"

# ``generated_by`` stamped by the extractor onto every graph it composes; used to
# document (in an assertion) that the reference came from the generator pipeline.
_GENERATOR_TAG = "drg-migration-v1"


# ---------------------------------------------------------------------------
# Canonical, layout-independent keys (DD-11): identity by content, not order.
# ``merge_layers`` concatenates fragments in alphabetical load order while the
# extractor globally sorts by ``(source, target, relation)`` — so a raw list
# ``==`` would false-fail. Set + count + canonical-sorted-list comparisons are
# order-independent yet still catch a dropped or duplicated node/edge.
# ---------------------------------------------------------------------------


def _node_key(node: DRGNode) -> tuple[str, str, str | None]:
    """Return the content-identity of a node: ``(urn, kind, label)``.

    ``provenance`` is intentionally excluded — it is a merge-time sidecar that
    is never serialised into the fragments, so both sides read ``None`` and it
    carries no behaviour-preserving signal.
    """
    return (node.urn, node.kind.value, node.label)


def _norm_guard(text: str | None) -> str | None:
    """Trailing-newline-normalise a ``when``/``reason`` guard string.

    The in-memory reference (``generate_graph``) carries guard strings that end
    with a literal ``\\n`` (block-scalar source text). Round-tripping *any*
    on-disk layout through YAML chomps that trailing newline on reload — a
    property of YAML block scalars, **not** of sharding: a monolith reload and a
    shard reload normalise identically (proven by
    :func:`test_sharded_reload_equals_monolith_reload_raw`). Normalising the
    trailing newline lets the DD-11 in-memory-vs-reload comparison assert
    semantic edge identity without tripping on this benign, layout-independent
    artifact.
    """
    return None if text is None else text.rstrip("\n")


def _edge_key(edge: DRGEdge) -> tuple[str, str, str, str | None, str | None]:
    """Return the content-identity of an edge: endpoints + relation + guards."""
    return (
        edge.source,
        edge.target,
        edge.relation.value,
        _norm_guard(edge.when),
        _norm_guard(edge.reason),
    )


def _raw_edge_key(edge: DRGEdge) -> tuple[str, str, str, str | None, str | None]:
    """Byte-exact edge identity (no guard normalisation).

    Used only for the monolith-vs-shard reload equivalence proof, where both
    sides pass through the same YAML reload so the raw guard text must match
    exactly.
    """
    return (edge.source, edge.target, edge.relation.value, edge.when, edge.reason)


def _node_set(graph: DRGGraph) -> set[tuple[str, str, str | None]]:
    return {_node_key(n) for n in graph.nodes}


def _edge_set(graph: DRGGraph) -> set[tuple[str, str, str, str | None, str | None]]:
    return {_edge_key(e) for e in graph.edges}


def _sorted_nodes(graph: DRGGraph) -> list[tuple[str, str, str | None]]:
    return sorted(_node_key(n) for n in graph.nodes)


def _sorted_edges(
    graph: DRGGraph,
) -> list[tuple[str, str, str, str | None, str | None]]:
    return sorted(_edge_key(e) for e in graph.edges)


def _counts_by_kind(graph: DRGGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in graph.nodes:
        counts[node.kind.value] = counts.get(node.kind.value, 0) + 1
    return counts


def _target_only_kinds(graph: DRGGraph) -> set[str]:
    """Return kinds that own nodes but are never an edge *source*.

    These are the trap kinds (e.g. ``template``): a partition that emitted
    fragments only for kinds-with-outgoing-edges would silently drop them on
    reload, changing the node set. Computed from the reference so the test does
    not hardcode a list that could drift.
    """
    kind_by_urn = {n.urn: n.kind.value for n in graph.nodes}
    source_kinds = {kind_by_urn[e.source] for e in graph.edges}
    node_kinds = {n.kind.value for n in graph.nodes}
    return node_kinds - source_kinds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reference_graph() -> DRGGraph:
    """The pre-shard reference: ``generate_graph``'s in-memory return value,
    plus the enumerable hand-authored overlay.

    Written to a throw-away temp directory (never the shipped ``src/doctrine``),
    so the returned graph is the composed / calibrated / sorted in-memory graph
    — *not* a read-back of the sharded files under test. This is what makes the
    equality proof non-vacuous (DD-11).

    Post-WP03 (doctrine-tension-edges-01KY1WPC): the sharded graph under test
    also carries hand-authored ``in_tension_with``/``reconciles_tension``/
    ``rejects`` edges and ``anti_pattern`` nodes the extractor has no
    frontmatter mechanism to mint (C-005) — so the reference must include the
    same enumerable overlay (``charter.offering.drg.migration.hand_authored_overlay``)
    or every equality proof below would spuriously report the hand-authored
    content as "missing" from a bare extractor regeneration.
    """
    pack_root = built_in_graph_source()
    return generate_reference_graph_with_overlay(pack_root)


@pytest.fixture(scope="module")
def sharded_graph() -> DRGGraph:
    """The graph reloaded from the on-disk ``src/charter/offering/*.graph.yaml`` shards."""
    return load_built_in_graph()


# ---------------------------------------------------------------------------
# T029 — merged-graph equality under the pinned DD-11 contract (FR-011)
# ---------------------------------------------------------------------------


def test_reference_is_generated_in_memory_not_a_self_compare(
    reference_graph: DRGGraph,
    sharded_graph: DRGGraph,
) -> None:
    """Guard the non-vacuity contract (renata's finding).

    The reference must be a distinct object composed by the generator, not the
    sharded graph compared against itself. Both graphs carry data (a compare of
    two empty graphs would be trivially equal and prove nothing).
    """
    assert reference_graph is not sharded_graph
    assert reference_graph.generated_by == _GENERATOR_TAG
    assert reference_graph.nodes, "reference graph must carry nodes"
    assert reference_graph.edges, "reference graph must carry edges"
    assert sharded_graph.nodes, "sharded graph must carry nodes"
    assert sharded_graph.edges, "sharded graph must carry edges"


def test_node_sets_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    ref = _node_set(reference_graph)
    shd = _node_set(sharded_graph)
    assert shd == ref, (
        f"node set drift — missing={ref - shd} extra={shd - ref}"
    )


def test_node_counts_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Counts guard against a duplicated node the set comparison would hide."""
    assert len(sharded_graph.nodes) == len(reference_graph.nodes)


def test_edge_sets_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    ref = _edge_set(reference_graph)
    shd = _edge_set(sharded_graph)
    assert shd == ref, (
        f"edge set drift — missing={ref - shd} extra={shd - ref}"
    )


def test_edge_counts_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Counts guard against a duplicated edge the set comparison would hide."""
    assert len(sharded_graph.edges) == len(reference_graph.edges)


def test_canonical_sorted_nodes_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Re-sort both graphs canonically, then compare as ordered lists."""
    assert _sorted_nodes(sharded_graph) == _sorted_nodes(reference_graph)


def test_canonical_sorted_edges_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Re-sort both graphs canonically, then compare as ordered lists.

    This closes the ``merge_layers`` concat-order trap (DD-9): the sharded graph
    arrives in alphabetical-fragment order, the reference in global sort order;
    canonical re-sort makes the layout-independent equality explicit.
    """
    assert _sorted_edges(sharded_graph) == _sorted_edges(reference_graph)


def test_both_graphs_pass_assert_valid(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """``assert_valid`` agrees on both — no dangling edge, duplicate, or cycle."""
    assert_valid(reference_graph)
    assert_valid(sharded_graph)


def test_equality_assertions_are_sensitive_to_perturbation(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Prove the equality checks discriminate (anti-vacuity self-test).

    Drop a single node from the sharded set and confirm the comparison detects
    the difference — so a genuine regression (a lost node) could never pass
    silently.
    """
    perturbed = set(_node_set(sharded_graph))
    perturbed.pop()
    assert perturbed != _node_set(reference_graph)


def test_sharded_reload_equals_monolith_reload_raw(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """The delete-safety certification: shards reload == monolith reload, raw.

    Writes the *same* in-memory reference to a single ``graph.yaml`` monolith
    and reloads it, then compares — with **no** guard-text normalisation —
    against the shipped sharded reload. Both sides traverse the identical YAML
    write→reload path, so any surviving difference would be caused *solely* by
    the shard/merge round trip. Byte-exact equality here is the direct proof
    that removing the monolith (WP05) changed nothing, and it localises the
    trailing-newline artifact to the in-memory-vs-reload boundary (not sharding).
    """
    with tempfile.TemporaryDirectory() as tmp:
        monolith_path = Path(tmp) / "graph.yaml"
        _dump_graph_document(reference_graph, monolith_path)
        monolith_reload = load_graph(monolith_path)

    assert _node_set(monolith_reload) == _node_set(sharded_graph)
    assert {_raw_edge_key(e) for e in monolith_reload.edges} == {
        _raw_edge_key(e) for e in sharded_graph.edges
    }
    assert len(monolith_reload.nodes) == len(sharded_graph.nodes)
    assert len(monolith_reload.edges) == len(sharded_graph.edges)


# ---------------------------------------------------------------------------
# T030 — partition totality (FR-010)
# ---------------------------------------------------------------------------


def test_every_populated_kind_has_a_fragment(sharded_graph: DRGGraph) -> None:
    """Every node-kind present in the merged graph owns exactly one fragment."""
    populated = {n.kind.value for n in sharded_graph.nodes}
    fragment_kinds = {
        p.name[: -len(_FRAGMENT_SUFFIX)]
        for p in built_in_graph_source().glob(f"*{_FRAGMENT_SUFFIX}")
    }
    assert fragment_kinds == populated, (
        "fragment set must equal populated node-kinds exactly; "
        f"missing={populated - fragment_kinds} extra={fragment_kinds - populated}"
    )


def test_per_kind_node_counts_equal(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """No kind loses (or gains) nodes across the shard/merge round trip."""
    assert _counts_by_kind(sharded_graph) == _counts_by_kind(reference_graph)


def test_no_node_urn_lost(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """The reloaded URN set equals the reference URN set exactly."""
    assert sharded_graph.node_urns() == reference_graph.node_urns()


def test_target_only_kinds_survive_round_trip(
    reference_graph: DRGGraph, sharded_graph: DRGGraph
) -> None:
    """Target-only kinds (never an edge source) still round-trip.

    ``template`` is the canonical example: it owns nodes but emits no outgoing
    edge, so a source-kind-only partition would drop it. Computed dynamically
    from the reference; ``template`` is asserted present to pin the known trap.
    """
    target_only = _target_only_kinds(reference_graph)
    assert "template" in target_only, (
        "expected 'template' to be a populated target-only kind (the trap the "
        "partition must not drop); doctrine layout changed — revisit this proof"
    )
    ref_counts = _counts_by_kind(reference_graph)
    shd_counts = _counts_by_kind(sharded_graph)
    for kind in sorted(target_only):
        assert shd_counts.get(kind, 0) == ref_counts[kind] > 0, (
            f"target-only kind {kind!r} lost nodes on reload: "
            f"reference={ref_counts[kind]} sharded={shd_counts.get(kind, 0)}"
        )
