"""T012 (WP03) -- the built-in pack must RESOLVE as a loaded DRG node.

This is the load-bearing guard for the mission (NFR-003): a pack that merely
sits on disk but never resolves through the built-in DRG seam is the exact
silent-invisibility trap the mission exists to kill. A guard that only
asserts "node present" is vacuous -- it would stay green even if someone
regressed the fragment's location (B1) or deleted the extractor's emission
block (B2). Every positive assertion below is paired with a **negative-control
arm** that reproduces one of the two blockers and proves resolution actually
goes RED when it is reintroduced.

Two independent seams are exercised:

* B1 -- fragment location. ``load_built_in_graph()``/``load_graph_or_dir``
  glob ``*.graph.yaml`` non-recursively at the doctrine package root. Removing
  just the ``glossary_pack.graph.yaml`` fragment from an otherwise-complete
  copy of the shipped fragments must make the node stop resolving.
* B2 -- extractor emission. ``extract_artifact_edges`` emits the
  ``glossary_pack:<id>`` source node via the dedicated
  ``_emit_glossary_pack_nodes`` helper, keyed off
  ``glossary_packs/built-in/*.glossary-pack.yaml``. Removing that directory
  from a doctrine-root copy must make extraction stop emitting the node.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from charter.offering.drg.loader import built_in_graph_source, load_built_in_graph
from charter.offering.drg.migration.extractor import extract_artifact_edges
from charter.offering.drg.models import NodeKind

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph, DRGNode

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

_PACK_URN = "glossary_pack:spec-kitty-core"
_FRAGMENT_NAME = "glossary_pack.graph.yaml"


def _pack_node(graph: DRGGraph) -> DRGNode | None:
    return next((n for n in graph.nodes if n.urn == _PACK_URN), None)


# ---------------------------------------------------------------------------
# Positive arm: the shipped built-in pack resolves, for real, through the
# canonical built-in-graph seam (not a synthetic fixture).
# ---------------------------------------------------------------------------


def test_builtin_pack_resolves_as_loaded_drg_node(
    built_in_graph: DRGGraph,
) -> None:
    """The shipped ``spec-kitty-core`` pack is a real, loaded DRG node."""
    node = _pack_node(built_in_graph)
    assert node is not None, (
        f"{_PACK_URN} did not resolve in the built-in DRG -- the pack loads "
        "from disk but never becomes a reachable node (NFR-003 trap)."
    )
    assert node.kind == NodeKind.GLOSSARY_PACK


# ---------------------------------------------------------------------------
# Negative-control arm 1 (B1): remove ONLY the root graph fragment from an
# otherwise-complete copy of the shipped fragments. Resolution must go RED.
# ---------------------------------------------------------------------------


def _copy_shipped_fragments(dest: Path, *, omit: str | None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    source_dir = built_in_graph_source()
    for fragment in source_dir.glob("*.graph.yaml"):
        if omit is not None and fragment.name == omit:
            continue
        shutil.copy2(fragment, dest / fragment.name)


class TestFragmentPresenceControlsResolution:
    """B1 negative control: the fragment's presence is what makes it resolve."""

    def test_control_arm_with_fragment_present_resolves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity control: the copy-based harness itself finds the node
        when the fragment IS present -- proves the negative arm below fails
        because the fragment is missing, not because the harness is broken.
        """
        fragments_dir = tmp_path / "doctrine-with-fragment"
        _copy_shipped_fragments(fragments_dir, omit=None)
        assert (fragments_dir / _FRAGMENT_NAME).is_file()

        monkeypatch.setattr(
            "charter.offering.drg.loader.built_in_graph_source", lambda: fragments_dir
        )
        graph = load_built_in_graph()
        assert _pack_node(graph) is not None

    def test_negative_control_arm_without_fragment_does_not_resolve(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The actual non-vacuity proof: delete the root fragment and the
        built-in pack node must NOT resolve, even though every other shipped
        fragment (directives, tactics, ...) is still present and loads fine.
        A fragment nested elsewhere (the B1 defect) is indistinguishable from
        this state from the loader's point of view.
        """
        fragments_dir = tmp_path / "doctrine-without-fragment"
        _copy_shipped_fragments(fragments_dir, omit=_FRAGMENT_NAME)
        assert not (fragments_dir / _FRAGMENT_NAME).exists()
        assert sorted(fragments_dir.glob("*.graph.yaml")), (
            "the negative control must still have OTHER fragments present, "
            "otherwise it would prove nothing about this pack specifically"
        )

        monkeypatch.setattr(
            "charter.offering.drg.loader.built_in_graph_source", lambda: fragments_dir
        )
        graph = load_built_in_graph()
        assert _pack_node(graph) is None, (
            "the pack node resolved even with its root fragment removed -- "
            "this guard would not have caught the B1 mislocation defect"
        )


# ---------------------------------------------------------------------------
# Negative-control arm 2 (B2): remove the built-in pack directory from a
# doctrine-root copy so the extractor's emission block has nothing to glob.
# Extraction must stop emitting the node.
# ---------------------------------------------------------------------------


#: The built-in subdirectories ``extract_artifact_edges`` actually reads.
#: Symlinking just these (instead of a full ``src/doctrine`` copy) keeps the
#: negative-control fixture fast while still exercising every other kind's
#: real emission block alongside the one under test.
_ARTIFACT_SUBDIRS = (
    "directives",
    "tactics",
    "paradigms",
    "procedures",
    "agent_profiles",
    "styleguides",
    "toolguides",
    "glossary_packs",
)


def _build_partial_pack_root(dest: Path, *, include_glossary_packs: bool) -> Path:
    """Symlink the real built-in artifact subdirs into a fresh *dest* root.

    Omitting ``glossary_packs`` reproduces "the emission block has nothing to
    glob" (the B2 defect shape) while every other kind's real built-in
    content stays reachable, so the control proves the absence is specific
    to glossary packs, not an artefact of an empty root.
    """
    pack_root = built_in_graph_source()
    dest.mkdir(parents=True, exist_ok=True)
    for name in _ARTIFACT_SUBDIRS:
        if name == "glossary_packs" and not include_glossary_packs:
            continue
        source = pack_root / name
        if source.is_dir():
            (dest / name).symlink_to(source, target_is_directory=True)
    return dest


class TestExtractorEmissionControlsResolution:
    """B2 negative control: the emission block is what mints the node."""

    def test_control_arm_extraction_emits_the_node_from_real_root(
        self, tmp_path: Path
    ) -> None:
        """Sanity control: extraction over a root that DOES include
        ``glossary_packs/`` emits the glossary_pack node (proves the emission
        block is wired at all, using the same harness as the negative arm).
        """
        root = _build_partial_pack_root(
            tmp_path / "with-glossary-packs", include_glossary_packs=True
        )
        nodes, _edges = extract_artifact_edges(root)
        urns = {n.urn for n in nodes}
        assert _PACK_URN in urns

    def test_negative_control_arm_without_builtin_pack_dir_emits_nothing(
        self, tmp_path: Path
    ) -> None:
        """The actual non-vacuity proof: a doctrine root with every OTHER
        built-in kind present but ``glossary_packs/`` absent must emit no
        glossary_pack node -- this is what a deleted/never-added emission
        block (the B2 defect) would look like.
        """
        root = _build_partial_pack_root(
            tmp_path / "without-glossary-packs", include_glossary_packs=False
        )
        assert not (root / "glossary_packs").exists()

        nodes, _edges = extract_artifact_edges(root)
        urns = {n.urn for n in nodes}
        assert _PACK_URN not in urns, (
            "the glossary_pack node was emitted even with the built-in pack "
            "directory removed -- this guard would not have caught the B2 "
            "missing-emission defect"
        )
        assert any(u.startswith("directive:") for u in urns), (
            "the negative control must still emit OTHER kinds' nodes, "
            "otherwise it would prove nothing about this emission block "
            "specifically"
        )
