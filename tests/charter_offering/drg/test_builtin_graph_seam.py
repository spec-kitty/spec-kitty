"""Unit tests for the canonical built-in-graph seam (WP03, mission #2680).

``load_built_in_graph`` / ``built_in_graph_source`` are the single accessor
every source reader of the shipped DRG must route through. Routing every reader
to the *directory* is what let WP05 delete the ``src/charter/offering/graph.yaml``
monolith and flip all consumers to ``*.graph.yaml`` fragments with no
call-site edits — this test locks in the post-flip sharded layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import (
    built_in_graph_source,
    load_built_in_graph,
)
from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.corpus]


def test_source_points_at_built_in_pack_root_directory() -> None:
    """The seam yields the doctrine *directory*, not a ``graph.yaml`` file.

    Routing every reader to the directory is what let WP05 delete the monolith
    and flip all consumers to ``*.graph.yaml`` fragments with no further edits.
    """
    source = built_in_graph_source()

    assert source.is_dir()
    # Relocated built-in pack root (mission relocate-builtin-doctrine-packs-01KYT87F):
    # the seam now yields the ``packs/built-in/`` pack directory, not ``src/doctrine``.
    assert source.name == "built-in"
    # Post-flip sharded layout (WP05): the monolith is retired; the built-in DRG
    # ships as per-kind ``*.graph.yaml`` fragments the seam merges on load.
    assert not (source / "graph.yaml").exists()
    assert sorted(source.glob("*.graph.yaml")), "no *.graph.yaml fragments present"


def test_seam_returns_a_populated_graph() -> None:
    """Sanity: the shipped built-in graph is non-empty (nodes and edges)."""
    graph = load_built_in_graph()

    assert graph.nodes, "built-in graph should ship nodes"
    assert graph.edges, "built-in graph should ship edges"


@pytest.fixture
def counted_parses(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Isolate the per-process memo and record every real graph parse (#5526)."""
    from charter.offering.drg import loader

    calls: list[object] = []
    original = loader.load_graph_or_dir

    def _counted(path: Path) -> DRGGraph:
        calls.append(path)
        return original(path)

    monkeypatch.setattr(loader, "_BUILT_IN_GRAPH_MEMO", {}, raising=False)
    monkeypatch.setattr(loader, "load_graph_or_dir", _counted)
    return calls


def test_repeat_loads_parse_once_and_return_independent_copies(counted_parses: list[object]) -> None:
    first = load_built_in_graph()
    second = load_built_in_graph()

    assert len(counted_parses) == 1
    assert first == second
    assert first is not second
    first.nodes.clear()
    assert load_built_in_graph().nodes, "mutating one caller's graph leaked into the memo"


def test_an_edited_fragment_is_reparsed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, counted_parses: list[object]) -> None:
    import shutil

    from charter.offering.drg import loader

    source = tmp_path / "built-in"
    source.mkdir()
    for fragment in sorted(built_in_graph_source().glob("*.graph.yaml")):
        shutil.copy2(fragment, source / fragment.name)
    monkeypatch.setattr(loader, "built_in_graph_source", lambda: source)

    baseline = load_built_in_graph()
    load_built_in_graph()
    edited = sorted(source.glob("*.graph.yaml"))[0]
    edited.write_text(edited.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    reparsed = load_built_in_graph()

    assert len(counted_parses) == 2
    assert reparsed == baseline
