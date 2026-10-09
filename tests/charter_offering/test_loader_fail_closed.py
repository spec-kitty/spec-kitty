"""Fail-closed contract for the built-in DRG loader (DIR-005).

After the relocation mission flattened the built-in DRG fragments out of
``src/charter/offering/`` into ``packs/built-in/``, :func:`built_in_graph_source`
resolves through the shared :func:`charter.offering.pack_paths.built_in_root` seam
(mission ``doctrine-built-in-seam-consolidation-01KYW3TX``, WP01, routed the
loader's bare ``resolve_pack_root("built-in")`` call through this authority).
That seam is deliberately fail-closed: when no ``packs/built-in/`` root can be
located it raises :class:`~charter.offering.pack_paths.PackRootNotFound`.

These tests pin that the loader *propagates* the failure rather than
re-swallowing it into an empty/partial graph (the old ``except -> Path(__file__)``
fallback that would now silently point at the emptied ``src/charter/offering/`` tree and
yield ``0`` nodes / ``0`` edges build-green).
"""

from __future__ import annotations

import pytest

from charter.offering.drg.loader import (
    built_in_graph_source,
    load_built_in_graph,
)
from charter.offering.pack_paths import PackRootNotFound
from tests.charter_offering._builtin_inventory import shipped_builtin_node_count

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


def _raise_pack_root_not_found() -> None:
    raise PackRootNotFound("built-in")


def test_built_in_graph_source_resolves_packs_root_by_default() -> None:
    """Positive control: the seam resolves the flattened ``packs/built-in`` root."""
    source = built_in_graph_source()
    assert source.name == "built-in"
    assert source.parent.name == "packs"
    assert source.is_dir()


def test_built_in_graph_source_propagates_pack_root_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``built_in_graph_source`` must NOT swallow ``PackRootNotFound``."""
    monkeypatch.setattr(
        "charter.offering.drg.loader.built_in_root",
        _raise_pack_root_not_found,
    )
    with pytest.raises(PackRootNotFound):
        built_in_graph_source()


def test_load_built_in_graph_fails_closed_when_pack_root_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loader raises (fail-closed) instead of returning an empty graph.

    Proves DIR-005: with no resolvable ``packs/built-in`` root the loader
    propagates ``PackRootNotFound`` rather than degrading to a ``0/0`` graph.
    """
    monkeypatch.setattr(
        "charter.offering.drg.loader.built_in_root",
        _raise_pack_root_not_found,
    )
    with pytest.raises(PackRootNotFound):
        load_built_in_graph()


def test_load_built_in_graph_loads_full_corpus_when_pack_root_present() -> None:
    """Positive control: the unpatched loader yields the full built-in corpus.

    Node count is DERIVED from the ``packs/built-in`` inventory (#3234), so a
    loader that skips a shipped fragment falls short of the source files it should
    have loaded (red), while a legitimately grown corpus stays green. Exact edge
    integrity is guaranteed by ``regenerate-graph --check``; here the ``edges >=
    nodes`` floor is the contrast to the fail-closed ``0/0`` graph the tests above
    guard against.
    """
    graph = load_built_in_graph()
    assert len(graph.nodes) == shipped_builtin_node_count()
    assert len(graph.edges) >= len(graph.nodes)
