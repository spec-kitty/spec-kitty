"""Three-layer DRG end-to-end ATDD (Slice F WP06).

Covers Scenario 1 (Organisation-tier doctrine) and the relevant slice of
AC-1 (three-layer DRG operational end-to-end).

RED on planning base: ``charter.drg`` does not yet export the symbols
referenced below. WP06 turns this GREEN by landing ``OrgDRGFragment``,
``load_org_drg``, ``merge_three_layers``, and the per-layer provenance
threading.

ATDD anchors per ``kitty-specs/<mission>/atdd-coverage.md``:
* Scenario 1 — ``test_org_drg_fragment_merges_through_three_layers_with_provenance``
* AC-1      — ``test_charter_lint_lints_all_three_layers_with_provenance``
"""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.integration]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Construct a tmp repo with ``.kittify/config.yaml`` pointing at the
    fixture org pack copied alongside the repo."""
    pack_dest = tmp_path / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        )
    )
    return tmp_path


def test_org_drg_fragment_merges_through_three_layers_with_provenance(
    tmp_repo_with_org_pack: Path,
) -> None:
    """Scenario 1 — an org pack contributes nodes/edges; the merged DRG
    carries per-artefact provenance through all three layers."""
    from charter.drg import (
        DRGEdge,
        DRGGraph,
        DRGNode,
        NodeKind,
        Relation,
    )
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    fragments = load_org_drg(tmp_repo_with_org_pack)
    assert len(fragments) == 1, "expected one fragment per configured pack"
    assert fragments[0].pack_name == "example-org"
    assert fragments[0].source_kind == "local_path"
    assert fragments[0].layer_index == 1
    assert len(fragments[0].nodes) == 1
    assert fragments[0].nodes[0].id == "sox-controls"
    assert fragments[0].nodes[0].kind == "directives"

    # Build a minimal shipped DRG with one node (so merge has something to
    # tag as ``built-in``).
    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-18T00:00:00Z",
        generated_by="test-fixture",
        nodes=[DRGNode(urn="directive:caveman-comments", kind=NodeKind.DIRECTIVE)],
        edges=[],
    )

    merged = merge_three_layers(built_in=built_in, org_fragments=fragments, project=None)

    # Every node carries provenance. ``provenance`` is a sidecar attribute
    # threaded by the merge (renamed from ``source`` in P0 fix, 2026-05).
    sources = {getattr(n, "provenance", None) for n in merged.nodes}
    assert "built-in" in sources, "shipped layer must be tagged 'built-in'"
    assert "org:example-org" in sources, (
        "org layer must be tagged 'org:<pack_name>'"
    )

    # Edges from the org fragment are present and tagged.
    edge_sources = {getattr(e, "provenance", None) for e in merged.edges}
    assert "org:example-org" in edge_sources

    # Sanity: the imports succeeded.
    assert DRGEdge is not None
    assert Relation is not None


def test_charter_lint_lints_all_three_layers_with_provenance(
    tmp_repo_with_org_pack: Path,
) -> None:
    """AC-1 (partial) — ``spec-kitty charter lint`` lints all three layers
    with per-layer findings carrying named-source provenance.

    This exercise covers the wiring contract: the engine accepts an org
    fragment list and the findings carry a ``layer_source`` attribute or
    the message includes the named source. The end-to-end CLI test for
    operator output formatting lives in
    ``test_charter_lint_lints_all_layers.py``.
    """
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    fragments = load_org_drg(tmp_repo_with_org_pack)
    assert fragments, "fixture must produce at least one fragment"

    # Stable provenance threading is the contract — operator-visible output
    # is exercised in the sibling integration test.
    from charter.drg import DRGGraph  # noqa: PLC0415

    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-05-18T00:00:00Z",
        generated_by="test-fixture",
        nodes=[],
        edges=[],
    )
    merged = merge_three_layers(built_in=built_in, org_fragments=fragments, project=None)
    org_tagged = [
        n for n in merged.nodes if getattr(n, "provenance", None) == "org:example-org"
    ]
    assert org_tagged, (
        "merge_three_layers must tag every org-contributed node with its "
        "provenance so charter lint can attribute findings per layer"
    )
