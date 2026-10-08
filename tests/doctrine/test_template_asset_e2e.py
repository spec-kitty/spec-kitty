"""End-to-end fixture proof for the TEMPLATE + ASSET doctrine kinds (WP08).

Mission ``doctrine-template-asset-kinds-01KX2YQ7`` (#2495 + #2469), Phase 5.
WP01-WP07 land the ``ArtifactKind.ASSET`` / ``NodeKind.ASSET`` enum members,
the ``AssetManifest`` sidecar model + ``pack_validator`` safety checks, the
global ``asset:``/``template:`` URN-uniqueness merge scan, the
``resolve_transitive_refs`` ``assets`` field, and the totality/lockstep
guards. This module is the acceptance proof that the two kinds work
end-to-end on a realistic (Regnology-shaped) org pack and that nothing
regressed for the 9 pre-existing kinds.

Unlike ``tests/doctrine/test_drg_merge.py::TestGlobalURNUniquenessScan``
(which hand-constructs :class:`~charter.offering.drg.org_pack_loader.OrgDRGFragment`
instances directly), every test here drives the **real** on-disk pipeline:

1. :func:`charter.offering.drg.org_pack_loader.load_org_pack` parses an actual
   ``drg/fragment.yaml`` (and, for the negative path/mime cases,
   :func:`charter.offering.packs.pack_validator.validate_pack` scans an actual
   ``assets/*.asset.yaml`` sidecar) from
   ``tests/doctrine/fixtures/org_pack_template_asset/``.
2. :func:`charter.offering.drg.merge.merge_three_layers` merges the loaded fragment(s)
   onto the **real, shipped** built-in DRG (``src/charter/offering/graph.yaml``, not a
   synthetic stub) — the strongest available proof that the two kinds compose
   correctly with the full built-in node/edge set.
3. :func:`charter.offering.drg.query.resolve_transitive_refs` walks the merged graph.

No mocked shortcuts (NFR-004): behavior is asserted from what the real loader
produces, not from API shape alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.merge import DuplicateURNError, merge_three_layers
from charter.offering.drg.models import DRGGraph, NodeKind, Relation
from charter.offering.drg.org_pack_loader import OrgDRGFragment, load_org_pack
from charter.offering.drg.query import resolve_transitive_refs
from charter.offering.packs.pack_validator import validate_pack
from tests.doctrine._builtin_inventory import builtin_asset_urns

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "org_pack_template_asset"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _built_in_graph() -> DRGGraph:
    """Load the real, shipped built-in DRG via the WP03 seam.

    Using the real built-in graph (rather than a synthetic stub, as
    ``test_drg_merge.py`` uses for its narrower unit tests) is the stronger
    e2e proof: it demonstrates the two new kinds compose correctly against
    the full shipped graph, not just an isolated fixture pair. Routing through
    ``load_built_in_graph()`` keeps this reader layout-agnostic across the
    WP05 monolith->fragment migration.
    """
    return load_built_in_graph()


def _load_fragment(pack_dir_name: str, *, pack_name: str, layer_index: int = 1) -> OrgDRGFragment:
    """Load one fixture pack through the real filesystem loader."""
    return load_org_pack(pack_name, _FIXTURES_ROOT / pack_dir_name, layer_index)


# ---------------------------------------------------------------------------
# T031 — positive e2e: node + edge + transitive query + valid orphan
# ---------------------------------------------------------------------------


class TestPositiveE2E:
    """TT-1 / AT-1 / AT-7: a real org pack's TEMPLATE + ASSET nodes and the
    edge between them survive the real loader -> merge -> query pipeline."""

    def test_pack_loads_through_real_loader(self) -> None:
        fragment = _load_fragment(
            "valid_pack", pack_name="regnology-template-asset-fixture"
        )

        node_kinds = {node.id: node.kind for node in fragment.nodes}
        assert node_kinds == {
            "regnology-house-style": "styleguides",
            "meeting-minutes": "templates",
            "meeting-minutes-orphan": "templates",
            "company-logo": "assets",
        }

    def test_merged_drg_contains_template_and_asset_nodes_and_edge(self) -> None:
        fragment = _load_fragment(
            "valid_pack", pack_name="regnology-template-asset-fixture"
        )

        merged = merge_three_layers(
            built_in=_built_in_graph(), org_fragments=[fragment], project=None
        )

        # AT-1: the ASSET sidecar is registered as a bare `asset:<id>` node.
        asset_node = merged.get_node("asset:company-logo")
        assert asset_node is not None
        assert asset_node.kind == NodeKind.ASSET

        # TT-1: the TEMPLATE node is present and edge-wireable.
        template_node = merged.get_node("template:meeting-minutes")
        assert template_node is not None
        assert template_node.kind == NodeKind.TEMPLATE

        # The valid-orphan template: present as a node, no edges required.
        orphan_node = merged.get_node("template:meeting-minutes-orphan")
        assert orphan_node is not None
        assert orphan_node.kind == NodeKind.TEMPLATE
        assert merged.edges_from("template:meeting-minutes-orphan") == []
        assert merged.edges_to("template:meeting-minutes-orphan") == []

        # TT-1: the styleguide -> template `requires` edge merged in.
        style_edges = merged.edges_from(
            "styleguide:regnology-house-style", relation=Relation.REQUIRES
        )
        assert any(e.target == "template:meeting-minutes" for e in style_edges)

        # The template -> asset `requires` edge merged in (chains to AT-7 below).
        template_edges = merged.edges_from(
            "template:meeting-minutes", relation=Relation.REQUIRES
        )
        assert any(e.target == "asset:company-logo" for e in template_edges)

    def test_transitive_query_reaches_template_and_asset(self) -> None:
        """AT-7: an asset node reached via `resolve_transitive_refs` appears
        in the `.assets` bucket — it is not silently dropped."""
        fragment = _load_fragment(
            "valid_pack", pack_name="regnology-template-asset-fixture"
        )
        merged = merge_three_layers(
            built_in=_built_in_graph(), org_fragments=[fragment], project=None
        )

        result = resolve_transitive_refs(
            merged,
            start_urns={"styleguide:regnology-house-style"},
            relations={Relation.REQUIRES},
        )

        assert "meeting-minutes" in result.templates
        assert "company-logo" in result.assets
        assert "regnology-house-style" in result.styleguides
        # The orphan template has no inbound edge from the start node, so the
        # transitive walk must not reach it (unlike the direct node lookup
        # above, which finds it in the merged graph regardless of reachability).
        assert "meeting-minutes-orphan" not in result.templates
        assert result.unresolved == []


# ---------------------------------------------------------------------------
# T032 — negative cases: four distinct, fail-loud structured errors
# ---------------------------------------------------------------------------


class TestNegativeCases:
    """AT-3, TT-3, AT-4, AT-5: each failure mode raises/emits a DISTINCT,
    structured error — never a silent drop or a shared generic category."""

    def test_duplicate_asset_id_across_two_packs_hard_fails(self) -> None:
        """(a) Two independent org packs each ship `asset:company-logo`."""
        pack_a = _load_fragment(
            "duplicate_asset_pack_a", pack_name="regnology-pack-a", layer_index=1
        )
        pack_b = _load_fragment(
            "duplicate_asset_pack_b", pack_name="regnology-pack-b", layer_index=2
        )

        with pytest.raises(DuplicateURNError) as exc_info:
            merge_three_layers(
                built_in=_built_in_graph(), org_fragments=[pack_a, pack_b], project=None
            )

        err = exc_info.value
        assert err.code == "duplicate_asset_id"
        assert err.urn == "asset:company-logo"
        assert err.count == 2

    def test_duplicate_template_id_across_two_producers_hard_fails(self) -> None:
        """(b) Two independent org packs each ship `template:quarterly-report`."""
        pack_a = _load_fragment(
            "duplicate_template_pack_a", pack_name="regnology-pack-a", layer_index=1
        )
        pack_b = _load_fragment(
            "duplicate_template_pack_b", pack_name="regnology-pack-b", layer_index=2
        )

        with pytest.raises(DuplicateURNError) as exc_info:
            merge_three_layers(
                built_in=_built_in_graph(), org_fragments=[pack_a, pack_b], project=None
            )

        err = exc_info.value
        assert err.code == "duplicate_template_id"
        assert err.urn == "template:quarterly-report"
        assert err.count == 2

    def test_asset_path_escape_rejected(self) -> None:
        """(c) `path: ../../../etc/passwd` -> `asset_path_escape`."""
        result = validate_pack(_FIXTURES_ROOT / "path_escape_pack")

        assert result.ok is False
        escape_errors = [
            issue for issue in result.errors if issue.category == "asset_path_escape"
        ]
        assert escape_errors, result.errors
        assert escape_errors[0].artifact_id == "evil-asset"
        # Distinct from the mime category — never conflated.
        assert not any(issue.category == "asset_mime_invalid" for issue in result.errors)

    def test_asset_mime_invalid_rejected_for_malformed_and_mismatched(self) -> None:
        """(d) A malformed-shape mime AND a path-extension mismatch both
        raise the SAME distinct `asset_mime_invalid` category (never
        `asset_path_escape` or `schema_invalid`)."""
        result = validate_pack(_FIXTURES_ROOT / "bad_mime_pack")

        assert result.ok is False
        mime_errors = {
            issue.artifact_id: issue
            for issue in result.errors
            if issue.category == "asset_mime_invalid"
        }
        assert "malformed-mime-asset" in mime_errors
        assert "mismatched-mime-asset" in mime_errors
        assert not any(issue.category == "asset_path_escape" for issue in result.errors)


# ---------------------------------------------------------------------------
# T033 — no-regression: the 9 pre-existing kinds are unaffected
# ---------------------------------------------------------------------------


class TestNoRegressionForExistingKinds:
    """Spot-check (per the WP08 review guidance): a representative
    pre-existing kind (``directive``) still loads/merges identically — its
    org-vs-org layered-override tolerance must NOT be swept into the new
    asset/template uniqueness hard-fail (the scan is prefix-scoped by
    construction, D-04 revised)."""

    def test_duplicate_directive_id_across_org_packs_still_silently_overrides(
        self,
    ) -> None:
        """Two org packs shipping the same `directive:` id is UNCHANGED
        behavior: first-wins, no `DuplicateURNError` (that hard-fail is
        scoped strictly to `asset:`/`template:` by
        :func:`charter.offering.drg.merge._check_node_urn_unique`'s prefix
        argument)."""
        pack_a = OrgDRGFragment.model_validate(
            {
                "pack_name": "regnology-pack-a",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/regnology-pack-a",
                "layer_index": 1,
                "nodes": [
                    {
                        "id": "referenced-policy",
                        "kind": "directives",
                        "title": "Pack A's Referenced Policy",
                    }
                ],
                "edges": [],
            }
        )
        pack_b = OrgDRGFragment.model_validate(
            {
                "pack_name": "regnology-pack-b",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/regnology-pack-b",
                "layer_index": 2,
                "nodes": [
                    {
                        "id": "referenced-policy",
                        "kind": "directives",
                        "title": "Pack B's Referenced Policy",
                    }
                ],
                "edges": [],
            }
        )

        # Must NOT raise — this is the pre-existing, unchanged behavior.
        merged = merge_three_layers(
            built_in=_built_in_graph(), org_fragments=[pack_a, pack_b], project=None
        )

        directive_node = merged.get_node("directive:referenced-policy")
        assert directive_node is not None
        # First-wins: pack_a's node survives (declared first in org_fragments).
        assert directive_node.label == "Pack A's Referenced Policy"

    def test_builtin_graph_references_the_first_shipped_asset(
        self,
    ) -> None:
        """The real shipped graph carries the built-in ASSET nodes, and the first
        shipped one — the common-docs structural lint — is REFERENCED (non-orphan):
        the four common-docs artifacts that name it in prose point at it with
        `requires` edges. An un-linked asset that everything references is the
        un-navigable state the asset kind exists to fix, so the wiring is asserted,
        not merely the node's presence.

        The asset set grew from one to six with mission rehome-writing-comms-doctrine,
        which shipped the five ``asset:writing-audience-*`` audience descriptors
        (see the composition ledger in
        ``tests/doctrine/drg/migration/test_extractor_projection.py`` entry (15));
        each is edge-incident (non-orphan) by construction — none is a bare node.

        The expected URN set is DERIVED from the shipped
        ``packs/built-in/assets/**/*.asset.yaml`` sidecars (#3234), not frozen: the
        loaded-graph asset URNs must equal the source inventory, so a loader that
        drops a shipped asset reds while a newly-shipped asset is picked up
        automatically. See ``tests/doctrine/_builtin_inventory.py``."""
        built_in = _built_in_graph()
        kinds_present = {node.kind for node in built_in.nodes}
        asset_urns = {
            node.urn for node in built_in.nodes if node.kind == NodeKind.ASSET
        }

        assert asset_urns == builtin_asset_urns()
        assert NodeKind.TEMPLATE in kinds_present
        assert NodeKind.DIRECTIVE in kinds_present

        inbound = built_in.edges_to(
            "asset:common-docs-structural-lint", relation=Relation.REQUIRES
        )
        assert {edge.source for edge in inbound} == {
            "directive:DIRECTIVE_042",
            "styleguide:common-docs",
            "tactic:common-docs-write",  # was common-docs-curation (folded into write)
            "tactic:common-docs-scaffold",
        }
