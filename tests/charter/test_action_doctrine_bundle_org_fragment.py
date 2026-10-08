"""WP04 (#3530): the org ``drg/fragment.yaml`` layer reaches the action bundle.

``_load_action_doctrine_bundle`` resolved its DRG via ``load_validated_graph``
without threading the ``org_fragments`` layer, so a pack shipping only
``drg/fragment.yaml`` (this repo's own ``packs/internal`` shape) was silently
dropped from the action-doctrine bundle -- the branch-named silent drop this WP
closes at the second deficient caller (the ``:245`` ActiveCharterService seam is a
different path and stays untouched, squad finding F13).

Red-first: :func:`test_valid_fragment_only_pack_node_reaches_bundle_graph` FAILS
before T018 (the fragment node never reaches ``bundle.merged``) and passes after.
The fragment is deliberately *valid* -- folding valid fragment content is exactly
what the pre-fix bundle path never did.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charter.activation.action_doctrine_bundle import _load_action_doctrine_bundle
from charter.drg import resolve_existing_org_roots
from charter.offering.drg.validator import DRGValidationError

pytestmark = pytest.mark.fast

_TARGET_URN = "directive:OPERATOR_SIGNAL_CONTRACT"
_MISSION_TYPE = "software-dev"


def _register_pack(repo_root: Path, org_root: Path, *, name: str = "test-org") -> None:
    kit = repo_root / ".kittify"
    kit.mkdir(parents=True, exist_ok=True)
    (kit / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": name, "local_path": str(org_root)}]}}}),
        encoding="utf-8",
    )


def _write_fragment_pack(
    repo_root: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]] | None = None,
) -> Path:
    org_root = repo_root.parent / "org-pack"
    (org_root / "drg").mkdir(parents=True, exist_ok=True)
    (org_root / "drg" / "fragment.yaml").write_text(
        yaml.safe_dump(
            {
                "pack_name": "test-org",
                "source_kind": "local_path",
                "source_ref": "org-pack",
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": nodes,
                "edges": edges or [],
            }
        ),
        encoding="utf-8",
    )
    _register_pack(repo_root, org_root)
    return org_root


def test_valid_fragment_only_pack_node_reaches_bundle_graph(tmp_path: Path) -> None:
    """A valid fragment-only pack's node must reach ``bundle.merged``.

    Red-first before T018: without ``org_fragments`` threading, the directive
    authored only in ``drg/fragment.yaml`` never entered the bundle's merged DRG.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fragment_pack(
        repo,
        nodes=[
            {
                "id": "OPERATOR_SIGNAL_CONTRACT",
                "kind": "directives",
                "title": "Operator-Signal Contract",
            }
        ],
    )

    bundle = _load_action_doctrine_bundle(
        repo_root=repo,
        action="implement",
        effective_depth=3,
        mission_type=_MISSION_TYPE,
    )

    assert bundle.merged is not None
    assert _TARGET_URN in {str(node.urn) for node in bundle.merged.nodes}


def test_fragment_node_and_edge_are_folded_once_not_twice(tmp_path: Path) -> None:
    """No-double-fold on the bundle path: fragment content folds ``n`` times, not ``2n``.

    The pack is registered (so ``org_fragments`` carries it) AND passed via
    ``org_roots`` (so the dual-list caller shape is exercised). Its node and edge
    must appear exactly once in ``bundle.merged``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    org_root = _write_fragment_pack(
        repo,
        nodes=[
            {"id": "FRAG_DIR_A", "kind": "directives", "title": "Frag Directive A"},
            {"id": "FRAG_DIR_B", "kind": "directives", "title": "Frag Directive B"},
        ],
        edges=[{"source": "FRAG_DIR_A", "target": "FRAG_DIR_B", "relation": "refines"}],
    )
    org_roots = resolve_existing_org_roots(repo)
    assert org_root in org_roots

    bundle = _load_action_doctrine_bundle(
        repo_root=repo,
        action="implement",
        effective_depth=3,
        org_roots=org_roots,
        mission_type=_MISSION_TYPE,
    )

    assert bundle.merged is not None
    node_count = sum(1 for node in bundle.merged.nodes if str(node.urn) == "directive:FRAG_DIR_A")
    edge_count = sum(
        1
        for edge in bundle.merged.edges
        if (str(edge.source), str(edge.target), edge.relation.value) == ("directive:FRAG_DIR_A", "directive:FRAG_DIR_B", "refines")
    )

    assert node_count == 1
    assert edge_count == 1


def test_nonexistent_org_governance_selection_fails_loud(tmp_path: Path) -> None:
    """T018: an org-tier nonexistent governance selection fails loud here.

    An org pack whose ``mission_types/<type>/governance-profile.yaml`` selects a
    nonexistent directive projects a dangling ``mission_type --scope--> directive``
    edge into the merged DRG. Before this WP the org fragment was dropped, so the
    typo was a total no-op; now it reaches the bundle path and fails loud.

    The escalation is ``load_validated_graph``'s own ``assert_valid``: a bad
    ``selected_*`` becomes a dangling ``mission_type --scope--> <artifact>`` edge
    that ``validate_dangling_references`` raises on as a ``DRGValidationError``
    naming the target. No dedicated governance-scope guard is needed -- the
    silent no-op is gone via the edge-minting plus the existing merged-graph
    validation.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    org_root = _write_fragment_pack(
        repo,
        nodes=[{"id": "FRAG_MARKER", "kind": "directives", "title": "marker"}],
    )
    gov_dir = org_root / "mission_types" / _MISSION_TYPE
    gov_dir.mkdir(parents=True)
    (gov_dir / "governance-profile.yaml").write_text(
        yaml.safe_dump(
            {
                "mission_type": _MISSION_TYPE,
                "selected_directives": ["THIS_DIRECTIVE_DOES_NOT_EXIST"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DRGValidationError) as excinfo:
        _load_action_doctrine_bundle(
            repo_root=repo,
            action="implement",
            effective_depth=3,
            mission_type=_MISSION_TYPE,
        )

    assert "THIS_DIRECTIVE_DOES_NOT_EXIST" in str(excinfo.value)
