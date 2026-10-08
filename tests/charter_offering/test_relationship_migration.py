"""WP07 — zero-loss relationship migration (FR-001/003/004/029, NFR-007).

Built-in doctrine relationships that used to be authored as artifact *fields*
(``specializes-from`` / ``enhances`` / ``overrides``) are migrated into typed
DRG ``specializes_from`` / ``enhances`` / ``overrides`` **edges** in the shipped
per-kind DRG fragments (``src/charter/offering/<kind>.graph.yaml``, sharded by
edge source kind). The migration must be *zero-loss*: every
field-authored relationship discovered in the built-in artifacts has exactly one
corresponding edge in the merged DRG.

The expected baseline is **discovered**, never hardcoded (the WP prompt's
explicit risk note): the test greps the shipped artifact YAML for the
relationship fields and compares that set against the merged-DRG edge set.

The fixtures under ``fixtures/relationship_packs/`` exercise the canonical
fragment-edge authoring form (lineage + augment-all-kinds) plus the deprecated
field form (``legacy-field-pack``, the WP06 rejection target).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.merge import merge_three_layers
from charter.offering.drg.models import Relation
from charter.offering.drg.org_pack_loader import OrgDRGFragment, load_org_pack

# The relationship fields whose values were migrated into DRG edges, mapped to
# the canonical relation each projects to. Derived directly from the migration
# contract (occurrence_map.yaml serialized_keys); the field spellings include
# the hyphenated agent-profile alias.
_FIELD_TO_RELATION: dict[str, Relation] = {
    "specializes-from": Relation.SPECIALIZES_FROM,
    "specializes_from": Relation.SPECIALIZES_FROM,
    "enhances": Relation.ENHANCES,
    "overrides": Relation.OVERRIDES,
}

#: Built-in artifact directories whose YAML may carry relationship fields, and
#: the DRG node-kind prefix each maps to. Discovered set, not assumed counts.
_BUILT_IN_KIND_DIRS: dict[str, str] = {
    "agent_profiles": "agent_profile",
    "tactics": "tactic",
    "styleguides": "styleguide",
    "paradigms": "paradigm",
    "procedures": "procedure",
}


def _doctrine_root() -> Path:
    return Path(str(files("charter.offering")))


def _artifact_id(data: dict) -> str | None:
    """Return the artifact's stable id under any of the accepted key spellings."""
    for key in ("profile-id", "profile_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _discover_field_authored_relations() -> set[tuple[str, str, Relation]]:
    """Grep built-in artifact YAML for relationship fields.

    Returns the set of ``(source_urn, target_urn, relation)`` triples the
    built-in doctrine declares via the *field* form. This is the zero-loss
    baseline: each entry MUST have exactly one merged DRG edge.
    """
    yaml = YAML(typ="safe")
    root = _doctrine_root()
    found: set[tuple[str, str, Relation]] = set()

    for plural, urn_kind in _BUILT_IN_KIND_DIRS.items():
        kind_dir = root / plural / "built-in"
        if not kind_dir.is_dir():
            continue
        for yaml_file in kind_dir.rglob("*.yaml"):
            try:
                data = yaml.load(yaml_file)
            except Exception:  # noqa: BLE001 — malformed files are not our concern here
                continue
            if not isinstance(data, dict):
                continue
            art_id = _artifact_id(data)
            if not art_id:
                continue
            for field_name, relation in _FIELD_TO_RELATION.items():
                target = data.get(field_name)
                if isinstance(target, str) and target:
                    found.add(
                        (
                            f"{urn_kind}:{art_id}",
                            f"{urn_kind}:{target}",
                            relation,
                        )
                    )
    return found


def _merged_relationship_edges() -> set[tuple[str, str, Relation]]:
    """Materialise the shipped DRG and return its relationship edge triples."""
    built_in = load_built_in_graph()
    merged = merge_three_layers(built_in=built_in, org_fragments=[], project=None)
    relations = set(_FIELD_TO_RELATION.values())
    return {
        (e.source, e.target, e.relation)
        for e in merged.edges
        if e.relation in relations
    }


# ---------------------------------------------------------------------------
# T029 / T031 — zero-loss migration
# ---------------------------------------------------------------------------


class TestZeroLossMigration:
    def test_built_in_relationships_authored_in_drg(self) -> None:
        """Sanity: the shipped DRG actually declares relationship edges, so the
        downstream assertions are non-vacuous.

        Post-cutover (WP06 FR-028) lineage/augmentation is no longer authored as
        profile *fields* — the legacy field set is empty by design — so the guard
        now verifies the migration *result*: the merged shipped DRG carries the
        relationship edges (e.g. the four ``specializes_from`` profile-lineage
        edges authored directly in ``graph.yaml``)."""
        assert not _discover_field_authored_relations(), (
            "Found field-authored relationships in built-in doctrine; the WP06 "
            "hard cutover requires lineage/augmentation to be DRG edges only."
        )
        merged = _merged_relationship_edges()
        assert merged, (
            "No relationship edges in the shipped DRG; lineage authoring is "
            "vacuous. Check graph.yaml / the extractor curated edges."
        )

    def test_every_field_relationship_has_exactly_one_merged_edge(self) -> None:
        """NFR-007: each field-authored relationship maps to exactly one merged
        DRG edge — no loss, no duplication."""
        baseline = _discover_field_authored_relations()
        merged_edges = _merged_relationship_edges()

        missing = baseline - merged_edges
        assert not missing, (
            "Zero-loss violation — these field-authored relationships have no "
            f"corresponding merged DRG edge: {sorted(map(str, missing))}"
        )

    def test_no_duplicate_relationship_edges_in_merged_graph(self) -> None:
        """Each migrated relationship appears at most once (identity, not count
        inflation). Asserts the merged edge multiset has no duplicate triple."""
        built_in = load_built_in_graph()
        merged = merge_three_layers(
            built_in=built_in, org_fragments=[], project=None
        )
        relations = set(_FIELD_TO_RELATION.values())
        triples = [
            (e.source, e.target, e.relation)
            for e in merged.edges
            if e.relation in relations
        ]
        assert len(triples) == len(set(triples)), (
            "Duplicate relationship edges in merged graph: "
            f"{sorted(str(t) for t in triples if triples.count(t) > 1)}"
        )


# ---------------------------------------------------------------------------
# NFR-005 — shipped graph loads with zero diagnostics
# ---------------------------------------------------------------------------


class TestShippedGraphLoadsClean:
    def test_graph_yaml_validates(self) -> None:
        graph = load_built_in_graph()
        assert graph.nodes, "shipped graph has no nodes"
        assert graph.edges, "shipped graph has no edges"

    def test_merge_of_shipped_graph_is_lossless_and_clean(self) -> None:
        built_in = load_built_in_graph()
        merged = merge_three_layers(
            built_in=built_in, org_fragments=[], project=None
        )
        # Every built-in edge survives the (no-op) merge.
        assert len(merged.edges) == len(built_in.edges)


# ---------------------------------------------------------------------------
# T030 — relationship-pack fixtures
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures" / "relationship_packs"


class TestRelationshipPackFixtures:
    def test_lineage_pack_loads_and_emits_lineage_edge(self) -> None:
        """Scenario 1: a profile-to-profile specializes_from edge loads cleanly
        and survives the merge as a SPECIALIZES_FROM edge."""
        fragment = load_org_pack("lineage-pack", _FIXTURES / "lineage-pack", 1)
        assert isinstance(fragment, OrgDRGFragment)
        from tests.charter_offering._relationship_graph import empty_built_in  # noqa: PLC0415

        merged = merge_three_layers(
            built_in=empty_built_in(), org_fragments=[fragment], project=None
        )
        assert any(
            e.relation is Relation.SPECIALIZES_FROM
            and e.source == "agent_profile:specialist-implementer"
            and e.target == "agent_profile:base-implementer"
            for e in merged.edges
        )

    def test_augment_all_kinds_pack_authors_edges_across_topology_kinds(self) -> None:
        """Scenario 10 (authoring parity): enhances/overrides edges author across
        directive, toolguide, mission-step-contract, and mission-type at the
        DRG-fragment level. This is the property WP07 owns — the fragment is the
        single authoring surface for augmentation on every topology-bearing kind.
        """
        fragment = load_org_pack(
            "augment-all-kinds-pack", _FIXTURES / "augment-all-kinds-pack", 1
        )
        # The org_pack_loader aliases ``mission_step_contracts`` -> ``mission_steps``.
        node_kinds = {n.kind for n in fragment.nodes}
        assert node_kinds == {
            "directives",
            "toolguides",
            "mission_steps",
            "mission_types",
        }
        edge_relations = {(e.source, e.relation) for e in fragment.edges}
        assert ("org-directive", "enhances") in edge_relations
        assert ("org-toolguide", "enhances") in edge_relations
        assert ("org-step-contract", "overrides") in edge_relations
        assert ("org-mission-type", "overrides") in edge_relations

    def test_augment_pack_merges_for_bridge_supported_kinds(self) -> None:
        """The merge bridge in ``charter.offering.drg.merge`` mints URNs for the kinds it
        knows (directive, toolguide, mission-step-contract). ``mission_types`` is
        admitted by the loader (FR-032) but the merge plural->singular bridge does
        not yet map it — that bridge extension is owned by the DRG merge/parity
        WPs, not WP07. We therefore merge the bridge-supported subset here and
        leave the mission-type edge as a fragment-level authoring assertion above.
        """
        from tests.charter_offering._relationship_graph import empty_built_in  # noqa: PLC0415

        fragment = load_org_pack(
            "augment-all-kinds-pack", _FIXTURES / "augment-all-kinds-pack", 1
        )
        bridge_supported = OrgDRGFragment.model_validate(
            {
                "pack_name": fragment.pack_name,
                "source_kind": fragment.source_kind,
                "source_ref": fragment.source_ref,
                "layer_index": fragment.layer_index,
                "provenance_marker": fragment.provenance_marker,
                "nodes": [
                    n.model_dump()
                    for n in fragment.nodes
                    if n.kind != "mission_types"
                ],
                "edges": [
                    e.model_dump()
                    for e in fragment.edges
                    if e.source != "org-mission-type"
                ],
            }
        )
        merged = merge_three_layers(
            built_in=empty_built_in(), org_fragments=[bridge_supported], project=None
        )
        augment = {
            (e.source, e.relation)
            for e in merged.edges
            if e.relation in (Relation.ENHANCES, Relation.OVERRIDES)
        }
        assert ("directive:org-directive", Relation.ENHANCES) in augment
        assert ("toolguide:org-toolguide", Relation.ENHANCES) in augment
        assert (
            "mission_step_contract:org-step-contract",
            Relation.OVERRIDES,
        ) in augment

    def test_legacy_field_pack_artifact_still_uses_field_form(self) -> None:
        """The negative fixture's profile artifact must still carry the
        deprecated `specializes-from:` FIELD (the WP06 rejection target). If this
        ever flips to an edge, WP06's rejection test loses its subject."""
        yaml = YAML(typ="safe")
        artifact = (
            _FIXTURES
            / "legacy-field-pack"
            / "profiles"
            / "legacy-specialist.agent.yaml"
        )
        data = yaml.load(artifact)
        assert data.get("specializes-from") == "legacy-base", (
            "legacy-field-pack artifact must retain the deprecated field form "
            "so WP06's rejection test has a concrete target"
        )

    def test_legacy_field_pack_fragment_loads(self) -> None:
        """The pack's fragment itself is edge-only and loads cleanly — the
        rejection in WP06 is keyed on the artifact field, not the fragment."""
        fragment = load_org_pack(
            "legacy-field-pack", _FIXTURES / "legacy-field-pack", 1
        )
        assert isinstance(fragment, OrgDRGFragment)
        assert fragment.edges == []


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
