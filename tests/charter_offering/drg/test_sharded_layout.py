"""WP05 (mission #2680) — sharded built-in DRG layout invariants.

After ``spec-kitty charter pack regenerate-graph`` the shipped built-in DRG is
stored as one ``src/charter/offering/<kind>.graph.yaml`` fragment per **populated**
node-kind, and the ``src/charter/offering/graph.yaml`` monolith is removed in the same
change (DD-7 atomic retire; DD-8 partition totality).

These assertions read the committed shipped tree through the WP03 seam
(``built_in_graph_source`` / ``load_built_in_graph``) so they lock the
post-flip layout without hardcoding a fragment set:

* the monolith must be **absent** — its presence would make
  ``load_graph_or_dir`` silently prefer it and mask the fragments (loader
  precedence, ``loader.py``);
* at least one ``*.graph.yaml`` fragment must be **present**;
* every populated node-kind must own exactly one fragment (totality — a
  partition that drops target-only kinds would lose nodes on reload);
* the seam must load a valid, ``assert_valid``-clean graph from the fragments.

Authored RED before the generator emits fragments (monolith still present);
turns GREEN once T027 regenerates + commits the sharded layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import built_in_graph_source, load_built_in_graph
from charter.offering.drg.validator import assert_valid

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.corpus]

# Relocated to the flattened built-in pack root (mission
# relocate-builtin-doctrine-packs-01KYT87F): the shipped ``*.graph.yaml``
# fragments and per-kind content now live under ``packs/built-in/``, no longer
# under ``src/charter/offering/``.
DOCTRINE_ROOT = Path(__file__).resolve().parents[3] / "packs" / "built-in"

_FRAGMENT_SUFFIX = ".graph.yaml"


def _fragment_kind(fragment: Path) -> str:
    """Return the node-kind a ``<kind>.graph.yaml`` fragment file owns."""
    return fragment.name[: -len(_FRAGMENT_SUFFIX)]


def test_monolith_absent_from_shipped_doctrine() -> None:
    """DD-7: the ``graph.yaml`` monolith must not survive the flip.

    While it exists ``load_graph_or_dir`` prefers it and ignores the fragments —
    a silent stale read.
    """
    assert not (DOCTRINE_ROOT / "graph.yaml").exists(), (
        "packs/built-in/graph.yaml must be deleted atomically with the fragment "
        "writes (DD-7); its presence masks the *.graph.yaml fragments on load."
    )


def test_shipped_doctrine_has_graph_fragments() -> None:
    """At least one per-kind fragment must ship under the loader glob root."""
    fragments = sorted(DOCTRINE_ROOT.glob(f"*{_FRAGMENT_SUFFIX}"))
    assert fragments, "no packs/built-in/*.graph.yaml fragments present"


def test_built_in_graph_source_resolves_to_a_directory() -> None:
    """The seam yields the doctrine directory (glob root), not a file."""
    source = built_in_graph_source()
    assert source.is_dir()


def test_fragment_per_populated_node_kind() -> None:
    """DD-8 totality: every populated node-kind owns exactly one fragment.

    A partition that emitted fragments only for kinds-with-source-edges would
    silently drop target-only kinds (e.g. ``template``) on reload, changing the
    node set — not behaviour-preserving.
    """
    graph = load_built_in_graph()
    populated_kinds = {node.kind.value for node in graph.nodes}
    fragment_kinds = {
        _fragment_kind(p) for p in DOCTRINE_ROOT.glob(f"*{_FRAGMENT_SUFFIX}")
    }
    assert fragment_kinds == populated_kinds, (
        "fragment set must equal the populated node-kinds exactly; "
        f"missing={populated_kinds - fragment_kinds} "
        f"extra={fragment_kinds - populated_kinds}"
    )


def test_seam_loads_valid_graph_from_fragments() -> None:
    """The merged fragments must load into a valid, assert_valid-clean graph."""
    graph = load_built_in_graph()
    assert graph.nodes, "fragments must contribute nodes"
    assert graph.edges, "fragments must contribute edges"
    # Raises DRGValidationError if the round-tripped graph is malformed.
    assert_valid(graph)
