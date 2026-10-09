"""T010 (mission ``drg-read-path-bridge-01M0CHVZ``, WP02): the review
gate-binding graph load threads the org ``drg/fragment.yaml`` layer.

FR-001 additive consumer: ``gate_bindings._activated_msc_urns`` — the single
production graph load the gate-binding resolver runs — now passes
``org_fragments=load_org_drg(repo_root, strict=False)`` into
``load_validated_graph`` (mirroring the ``activate``/``deactivate`` cascade call
sites, D4). A ``requires`` edge authored **only** in an org pack's
``drg/fragment.yaml`` (the #3387 ``OrgDRGFragment`` shape, which no root-level
``*.graph.yaml`` carries) therefore enters the graph the gate path resolves
against.

These tests exercise the real threaded call site (``graph_loader=None`` forces
the production default) and capture the graph ``load_validated_graph`` returns:

* the positive arm asserts the org fragment's ``A requires B`` edge is present
  in that graph — proving the bridge is threaded at the gate-binding load site;
* the no-org-pack arm asserts ``load_org_drg`` contributes ``[]`` and the edge is
  absent — proving the no-org-pack path is behaviourally unchanged (NFR-001).

The fixture mirrors ``TestFragmentYamlEdgeCascades`` in
``tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py`` and the
canonical ``charter_packs.org.packs[].local_path`` config shape from WP01's
``tests/charter/test_drg_helpers_fragment_bridge.py``.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from charter.activation._drg_helpers import load_validated_graph as real_load_validated_graph
from charter.offering.drg.models import DRGGraph
from specify_cli.review import gate_bindings

pytestmark = [pytest.mark.fast]

# The org fragment edge, in resolved-URN form (``merge_three_layers``'
# ``resolve_edge_endpoint`` canonicalises the bare-id source to a ``directive:``
# URN — see WP01's ``test_org_fragment_edge_appears_in_returned_graph``).
_BRIDGE_SOURCE = "directive:DIRECTIVE_A"
_BRIDGE_TARGET = "directive:DIRECTIVE_B"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, name: str, local_path: str) -> None:
    """Write ``.kittify/config.yaml`` declaring one org pack (canonical shape)."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: {name}
                    local_path: {local_path}
            mission_type_activations:
              - software-dev
            """
        ),
        encoding="utf-8",
    )


def _write_empty_config(repo_root: Path) -> None:
    """Write a ``.kittify/config.yaml`` with no org packs (no-org-pack path)."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")


def _write_fragment_only_pack(repo_root: Path, rel_path: str) -> None:
    """Write a fragment-only org pack whose ``drg/fragment.yaml`` carries the
    ``A requires B`` edge — and **no** root-level ``*.graph.yaml`` (so the edge
    is invisible to the cascade unless the fragment bridge folds it)."""
    drg_dir = repo_root / rel_path / "drg"
    drg_dir.mkdir(parents=True, exist_ok=True)
    (drg_dir / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: fragment-only-pack
            source_kind: local_path
            source_ref: {rel_path}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: DIRECTIVE_A
                kind: directives
              - id: DIRECTIVE_B
                kind: directives
            edges:
              - source: DIRECTIVE_A
                target: "directive:DIRECTIVE_B"
                relation: requires
            """
        ),
        encoding="utf-8",
    )


def _has_bridge_edge(graph: DRGGraph) -> bool:
    return any(edge.source == _BRIDGE_SOURCE and edge.target == _BRIDGE_TARGET and edge.relation == "requires" for edge in graph.edges)


class _GraphCapture:
    """Wraps the real ``load_validated_graph`` so the test can inspect both the
    ``org_fragments`` the gate path threaded and the graph it produced."""

    def __init__(self) -> None:
        self.org_fragments: object = "UNSET"
        self.graph: DRGGraph | None = None

    def __call__(
        self,
        repo_root: Path,
        *,
        org_roots: list[Path] | None = None,
        org_fragments: object = None,
    ) -> DRGGraph:
        self.org_fragments = org_fragments
        graph = real_load_validated_graph(repo_root, org_roots=org_roots, org_fragments=org_fragments)
        self.graph = graph
        return graph


# ---------------------------------------------------------------------------
# T010 — org fragment edge is visible to the gate-binding graph load
# ---------------------------------------------------------------------------


def test_gate_binding_graph_load_contains_org_fragment_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-001: with a fragment-bearing org pack configured, the graph the
    gate-binding path loads contains the org-authored ``A requires B`` edge."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fragment_only_pack(repo_root, "org-packs/fragment-only-pack")
    _write_org_pack_config(repo_root, "fragment-only-pack", "org-packs/fragment-only-pack")

    capture = _GraphCapture()
    monkeypatch.setattr(gate_bindings, "load_validated_graph", capture)

    # graph_loader=None forces the production default (the threaded call site);
    # pack_resolver returns None so no activation filter narrows the raw graph.
    gate_bindings._activated_msc_urns(repo_root, graph_loader=None, pack_resolver=lambda _root: None)

    assert capture.org_fragments, f"gate-binding path must thread a non-empty org_fragments layer for a fragment-bearing pack; got {capture.org_fragments!r}"
    assert capture.graph is not None
    assert _has_bridge_edge(capture.graph), "org fragment.yaml requires edge was not folded into the graph the gate-binding path loads"


def test_gate_binding_graph_load_no_org_pack_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: with no org pack configured, ``load_org_drg`` contributes ``[]``
    and the bridge edge is absent — the no-org-pack path is unchanged."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_empty_config(repo_root)

    capture = _GraphCapture()
    monkeypatch.setattr(gate_bindings, "load_validated_graph", capture)

    gate_bindings._activated_msc_urns(repo_root, graph_loader=None, pack_resolver=lambda _root: None)

    assert capture.org_fragments == [], f"no-org-pack path must thread an empty org_fragments layer; got {capture.org_fragments!r}"
    assert capture.graph is not None
    assert not _has_bridge_edge(capture.graph), "no org pack is configured, so no org fragment edge may appear"


def test_explicit_graph_loader_override_bypasses_fragment_threading(
    tmp_path: Path,
) -> None:
    """An explicit ``graph_loader`` test double is still called with the single
    ``repo_root`` argument (no org_roots / org_fragments threading), so existing
    overrides are unaffected by the bridge (parity with #3525 Fold B)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fragment_only_pack(repo_root, "org-packs/fragment-only-pack")
    _write_org_pack_config(repo_root, "fragment-only-pack", "org-packs/fragment-only-pack")

    seen: dict[str, object] = {}

    def _loader(root: Path) -> DRGGraph:
        seen["root"] = root
        return real_load_validated_graph(root)

    gate_bindings._activated_msc_urns(repo_root, graph_loader=_loader, pack_resolver=lambda _root: None)

    assert seen["root"] == repo_root, "an explicit graph_loader override must be called with repo_root only"
