"""WP06 (relocate-builtin-doctrine-packs, T018) — regeneration round-trips to the
flattened ``packs/built-in/`` home.

The flatten (WP03) moved the built-in artifact content and the sharded
``*.graph.yaml`` fragments from ``src/charter/offering/`` to ``packs/built-in/`` and this
WP repointed the regeneration surface (the extractor's artifact walks +
``_PATH_KIND_PATTERNS`` and the CLI's ``_built_in_pack_root``) to that home. This
module is the committed proof that a real regeneration reproduces the on-disk
fragments **exactly** — not as a byte diff alone but as a *full projection*
(nodes + edges, edges carrying their ``when``/``reason`` metadata) so a dropped
or mutated ``when`` gate (the live ``suggests``-``when`` links the profile
channel delivers, D-7) would be caught.

It also pins the *write target*: regeneration lands in ``packs/built-in/`` and
the retired ``src/charter/offering/`` home carries no fragments — a silent write to the
old, emptied tree would leave the shipped source stale while the build stayed
green.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from charter.offering.drg.loader import built_in_graph_source, load_graph_or_dir
from charter.offering.drg.migration.hand_authored_overlay import (
    write_reference_graph_with_overlay,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode
from specify_cli.cli.commands.charter.pack_tooling import _built_in_pack_root

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _node_projection(graph: DRGGraph) -> set[tuple[str, str, str | None]]:
    """Full node identity: ``(urn, kind, label)`` — order-independent."""
    return {(n.urn, n.kind.value, n.label) for n in graph.nodes}


def _edge_projection(
    graph: DRGGraph,
) -> set[tuple[str, str, str, str | None, str | None]]:
    """Full edge identity incl. gate metadata: ``(source, target, relation,
    when, reason)`` — so a dropped or mutated ``when`` is not silently tolerated.
    """
    return {
        (e.source, e.target, e.relation.value, e.when, e.reason) for e in graph.edges
    }


def _regenerate_into(directory: Path) -> DRGGraph:
    """Regenerate the shipped built-in DRG (extractor + hand-authored overlay)
    into *directory* as per-kind fragments; return the composed graph."""
    return write_reference_graph_with_overlay(
        built_in_graph_source(), directory / "graph.yaml"
    )


class TestRegenerationWriteTarget:
    """Regeneration targets the flattened ``packs/built-in/`` home, not the
    retired ``src/charter/offering/`` tree."""

    def test_built_in_pack_root_resolves_flattened_pack_home(self) -> None:
        resolved = _built_in_pack_root()
        assert resolved.name == "built-in"
        assert resolved.parent.name == "packs"
        assert resolved == built_in_graph_source()

    def test_offering_source_tree_carries_no_fragments(self) -> None:
        stale = sorted((_REPO_ROOT / "src" / "charter" / "offering").glob("*.graph.yaml"))
        assert stale == [], (
            "graph fragments still sit under the retired src/doctrine home: "
            f"{[p.name for p in stale]}"
        )


class TestRegenerationRoundTrips:
    """A fresh regeneration reproduces the on-disk fragments as a full
    projection (nodes + edges incl. ``when``)."""

    def test_regenerated_fragments_match_on_disk_full_projection(self) -> None:
        on_disk = load_graph_or_dir(built_in_graph_source())
        with tempfile.TemporaryDirectory() as tmp:
            _regenerate_into(Path(tmp))
            regenerated = load_graph_or_dir(Path(tmp))

        assert _node_projection(regenerated) == _node_projection(on_disk)
        assert _edge_projection(regenerated) == _edge_projection(on_disk)

    def test_regenerated_fragments_are_byte_identical(self) -> None:
        def _fragments(directory: Path) -> dict[str, str]:
            return {
                p.name: p.read_text(encoding="utf-8")
                for p in sorted(directory.glob("*.graph.yaml"))
            }

        committed = _fragments(built_in_graph_source())
        with tempfile.TemporaryDirectory() as tmp:
            _regenerate_into(Path(tmp))
            regenerated = _fragments(Path(tmp))

        assert set(regenerated) == set(committed)
        assert regenerated == committed, "regeneration is not byte-stable"

    def test_when_gated_edges_survive_the_round_trip(self) -> None:
        """The projection guard is non-vacuous: there IS at least one
        ``when``-carrying edge, and every such edge round-trips identically."""
        on_disk = load_graph_or_dir(built_in_graph_source())
        gated = {
            (e.source, e.target, e.relation.value, e.when)
            for e in on_disk.edges
            if e.when is not None
        }
        assert gated, "no when-gated edges on disk — the guard would be vacuous"

        with tempfile.TemporaryDirectory() as tmp:
            _regenerate_into(Path(tmp))
            regenerated = load_graph_or_dir(Path(tmp))
        regenerated_gated = {
            (e.source, e.target, e.relation.value, e.when)
            for e in regenerated.edges
            if e.when is not None
        }
        assert regenerated_gated == gated


def test_projection_helpers_are_perturbation_sensitive() -> None:
    """A guard on the guard: perturbing a ``when`` changes the edge projection
    (so the equality assertions above cannot pass a mutated gate)."""
    node_a = DRGNode(urn="tactic:a", kind="tactic")
    node_b = DRGNode(urn="tactic:b", kind="tactic")
    base = DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[node_a, node_b],
        edges=[DRGEdge(source="tactic:a", target="tactic:b", relation="suggests", when="X")],
    )
    mutated = DRGGraph(
        schema_version="1.0",
        generated_at="STATIC",
        generated_by="test",
        nodes=[node_a, node_b],
        edges=[DRGEdge(source="tactic:a", target="tactic:b", relation="suggests", when="Y")],
    )
    assert _edge_projection(base) != _edge_projection(mutated)
