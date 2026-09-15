"""Tests for the doctrine-owned three-layer DRG merge (WP03).

Mission ``org-doctrine-profile-integrity-activation-closure-01KT1TV1`` WP03
relocates ``merge_three_layers`` from ``charter.drg`` into
:mod:`charter.offering.drg.merge` (OQ-2(ii) / C-009) and fixes the org-fragment
silent-drop of unknown relations (FR-003 / contract C0.3).

These tests import the merge **directly from the doctrine layer** (not via the
``charter.drg`` re-export facade) so they double as a guard that the relocated
module is self-contained and free of any charter/specify_cli dependency. The
``tests/architectural/test_layer_rules.py`` suite enforces the import boundary
statically; this file exercises behaviour.

Coverage:

* T011 — behaviour preservation: a representative built-in + org + project
  input produces a node/edge set that matches an independent recomputation of
  the documented merge semantics (golden recomputation, not a smoke test).
* T011/C0.3 — an org-fragment ``specializes_from`` edge resolves into the
  merged graph (WP02 added the enum member); an unknown relation raises.
* T012 — shipped/org/project fragment parity: a valid lineage edge routes into
  the merged graph identically across all three tiers, and an unknown relation
  is rejected (never silently dropped) on every tier.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

from charter.offering.drg.merge import (
    DuplicateURNError,
    OrgDRGConflict,
    OrgDRGConflictError,
    UnknownRelationError,
    _filter_surviving_org_nodes,
    merge_three_layers,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.org_pack_loader import OrgDRGFragment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _graph(
    nodes: list[DRGNode] | None = None,
    edges: list[DRGEdge] | None = None,
    *,
    generated_by: str = "unit-test",
) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by=generated_by,
        nodes=nodes or [],
        edges=edges or [],
    )


def _fragment(
    pack_name: str,
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": pack_name,
            "source_kind": "local_path",
            "source_ref": f"/nonexistent/{pack_name}",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": nodes,
            "edges": edges,
        }
    )


# ---------------------------------------------------------------------------
# T011 — behaviour preservation (golden recomputation)
# ---------------------------------------------------------------------------


class TestBehaviorPreservation:
    """The relocated merge must produce the same node/edge set the pre-WP03
    charter merge produced for a representative three-layer input.

    Rather than snapshotting opaque bytes, this recomputes the expected merged
    graph from the documented semantics (built-in seed → org overlay → project
    overlay, with provenance tags) and asserts an exact set equality on the
    merged URNs / edges and their provenance markers.
    """

    def test_built_in_org_project_merge_matches_recomputation(self) -> None:
        built_in = _graph(
            nodes=[
                DRGNode(urn="directive:shipped-d", kind=NodeKind.DIRECTIVE),
                DRGNode(urn="tactic:shipped-t", kind=NodeKind.TACTIC),
            ],
            edges=[
                DRGEdge(
                    source="tactic:shipped-t",
                    target="directive:shipped-d",
                    relation=Relation.APPLIES,
                ),
            ],
            generated_by="built-in-gen",
        )
        org = _fragment(
            "acme",
            nodes=[
                {"id": "policy", "kind": "directives", "title": "Policy"},
                {"id": "play", "kind": "tactics", "title": "Play"},
            ],
            edges=[
                {"source": "play", "target": "policy", "relation": "requires"},
            ],
        )
        project = _graph(
            nodes=[DRGNode(urn="tactic:proj-t", kind=NodeKind.TACTIC)],
            edges=[
                DRGEdge(
                    source="tactic:proj-t",
                    target="directive:shipped-d",
                    relation=Relation.SUGGESTS,
                ),
            ],
        )

        merged = merge_three_layers(
            built_in=built_in, org_fragments=[org], project=project
        )

        # --- Recompute the expected node-URN → provenance mapping. ---
        expected_node_provenance = {
            "directive:shipped-d": "built-in",
            "tactic:shipped-t": "built-in",
            "directive:policy": "org:acme",
            "tactic:play": "org:acme",
            "tactic:proj-t": "project",
        }
        actual_node_provenance = {
            n.urn: getattr(n, "provenance", None) for n in merged.nodes
        }
        assert actual_node_provenance == expected_node_provenance

        # --- Recompute the expected edge set (source, target, relation, prov). ---
        expected_edges = {
            ("tactic:shipped-t", "directive:shipped-d", Relation.APPLIES, "built-in"),
            ("tactic:play", "directive:policy", Relation.REQUIRES, "org:acme"),
            ("tactic:proj-t", "directive:shipped-d", Relation.SUGGESTS, "project"),
        }
        actual_edges = {
            (e.source, e.target, e.relation, getattr(e, "provenance", None))
            for e in merged.edges
        }
        assert actual_edges == expected_edges

        # Graph header is inherited from the built-in layer (preserved).
        assert merged.schema_version == built_in.schema_version
        assert merged.generated_by == built_in.generated_by

    def test_empty_inputs_round_trip(self) -> None:
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[], project=None
        )
        assert merged.nodes == []
        assert merged.edges == []


# ---------------------------------------------------------------------------
# T011 / C0.3 — specializes_from resolves; unknown relation raises
# ---------------------------------------------------------------------------


class TestSpecializesFromAndUnknownRelation:
    def test_org_specializes_from_edge_appears_in_merged_graph(self) -> None:
        """C0.3: WP02 added ``SPECIALIZES_FROM``; an org-fragment lineage edge
        must now resolve into the merged graph (not be dropped)."""
        org = _fragment(
            "lineage-pack",
            nodes=[
                {"id": "child", "kind": "agent_profiles", "title": "Child"},
                {"id": "parent", "kind": "agent_profiles", "title": "Parent"},
            ],
            edges=[
                {
                    "source": "child",
                    "target": "parent",
                    "relation": "specializes_from",
                },
            ],
        )
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[org], project=None
        )
        lineage_edges = [
            e for e in merged.edges if e.relation is Relation.SPECIALIZES_FROM
        ]
        # cardinality-is-contract: merge must not duplicate the lineage edge when layers re-declare it; the projection collapses duplicates
        assert len(lineage_edges) == 1
        assert {(e.source, e.target) for e in lineage_edges} == {
            ("agent_profile:child", "agent_profile:parent")
        }
        assert lineage_edges[0].source == "agent_profile:child"
        assert lineage_edges[0].target == "agent_profile:parent"
        assert getattr(lineage_edges[0], "provenance", None) == "org:lineage-pack"

    def test_org_unknown_relation_raises_structured_error(self) -> None:
        """C0.3 / FR-003: an unrecognised relation fails closed with a
        structured error that names the relation, the fragment, and the valid
        token set — it is NOT silently dropped."""
        org = _fragment(
            "bad-rel-pack",
            nodes=[
                {"id": "a", "kind": "directives", "title": "A"},
                {"id": "b", "kind": "tactics", "title": "B"},
            ],
            edges=[{"source": "a", "target": "b", "relation": "bogus"}],
        )
        with pytest.raises(UnknownRelationError) as exc_info:
            merge_three_layers(built_in=_graph(), org_fragments=[org], project=None)
        err = exc_info.value
        assert err.relation == "bogus"
        assert "bad-rel-pack" in err.source_marker
        # Valid token set is surfaced for the operator.
        assert "specializes_from" in err.valid_relations
        assert "bogus" in str(err)

    def test_org_refines_relation_is_preserved(self) -> None:
        """#2079: a fragment edge authored ``refines`` survives bridging as
        ``Relation.REFINES`` — it is no longer silently downgraded to the inert
        ``APPLIES`` sink (this inverts the old, wrong contract)."""
        org = _fragment(
            "refines-pack",
            nodes=[
                {"id": "a", "kind": "directives", "title": "A"},
                {"id": "b", "kind": "tactics", "title": "B"},
            ],
            edges=[{"source": "a", "target": "b", "relation": "refines"}],
        )
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[org], project=None
        )
        # cardinality-is-contract: merge yields exactly one edge; projecting only .relation collapses duplicate/extra edges
        assert len(merged.edges) == 1
        assert {e.relation for e in merged.edges} == {Relation.REFINES}
        assert merged.edges[0].relation is Relation.REFINES

    def test_org_extends_relation_maps_to_lineage_not_applies(self) -> None:
        """#2079: ``extends`` (overlay-inheritance language) resolves to the
        lineage relation ``SPECIALIZES_FROM`` — never the inert ``APPLIES`` sink."""
        org = _fragment(
            "extends-pack",
            nodes=[
                {"id": "a", "kind": "directives", "title": "A"},
                {"id": "b", "kind": "tactics", "title": "B"},
            ],
            edges=[{"source": "a", "target": "b", "relation": "extends"}],
        )
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[org], project=None
        )
        # cardinality-is-contract: merge yields exactly one edge; projecting only .relation collapses duplicate/extra edges
        assert len(merged.edges) == 1
        assert {e.relation for e in merged.edges} == {Relation.SPECIALIZES_FROM}
        assert merged.edges[0].relation is Relation.SPECIALIZES_FROM

    @pytest.mark.parametrize("relation", [r.value for r in Relation])
    def test_bridge_preserves_every_canonical_relation_verbatim(
        self, relation: str
    ) -> None:
        """Relation-fidelity guard (#2079): every canonical ``Relation`` authored on
        a fragment edge survives bridging with the SAME relation — no silent relabel.
        Covers ``refines`` / ``overrides`` / ``replaces`` and the full vocabulary."""
        org = _fragment(
            f"fidelity-{relation}",
            nodes=[
                {"id": "a", "kind": "directives", "title": "A"},
                {"id": "b", "kind": "tactics", "title": "B"},
            ],
            edges=[{"source": "a", "target": "b", "relation": relation}],
        )
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[org], project=None
        )
        # cardinality-is-contract: merge yields exactly one edge per mapped relation; the projection collapses a duplicated edge
        assert len(merged.edges) == 1
        assert {e.relation.value for e in merged.edges} == {relation}
        assert merged.edges[0].relation.value == relation

    def test_no_relation_alias_maps_to_the_inert_applies_sink(self) -> None:
        """Dead-sink ban (#2079): no relation alias may map an authored verb onto
        ``Relation.APPLIES`` — no traversal reads ``APPLIES``, so such an alias
        silently turns the authored edge into a no-op. Guards against re-introducing
        the ``refines`` / ``extends`` downgrade."""
        from charter.offering.drg.merge import _RELATION_ALIASES

        offenders = {
            k: v for k, v in _RELATION_ALIASES.items() if v is Relation.APPLIES
        }
        assert not offenders, (
            f"relation alias(es) map to the inert APPLIES sink: {offenders}"
        )

    def test_refines_is_canonical_not_aliased(self) -> None:
        """#2079 precedence pin: REFINES is a canonical ``Relation``, so an authored
        ``refines`` edge resolves via the enum branch of ``_resolve_relation``, NEVER
        the alias table. This is the load-bearing path: without this pin, the
        refines-preservation guard above is shadowed by the enum (an alias-only
        ``refines: APPLIES`` regression would resolve canonically and slip past it).
        Paired with the dead-sink ban, this closes that gap."""
        from charter.offering.drg.merge import _RELATION_ALIASES

        assert "refines" in {r.value for r in Relation}
        assert "refines" not in _RELATION_ALIASES


# ---------------------------------------------------------------------------
# T012 — shipped / org / project parity
# ---------------------------------------------------------------------------


class TestThreeSourceParity:
    """A valid lineage edge routes into the merged graph identically from
    shipped, org, and project sources; an unknown relation is rejected on every
    tier (no silent path on any source)."""

    def _shipped_lineage_graph(self) -> DRGGraph:
        return _graph(
            nodes=[
                DRGNode(urn="agent_profile:child", kind=NodeKind.AGENT_PROFILE),
                DRGNode(urn="agent_profile:parent", kind=NodeKind.AGENT_PROFILE),
            ],
            edges=[
                DRGEdge(
                    source="agent_profile:child",
                    target="agent_profile:parent",
                    relation=Relation.SPECIALIZES_FROM,
                ),
            ],
        )

    def test_shipped_valid_lineage_edge_present(self) -> None:
        merged = merge_three_layers(
            built_in=self._shipped_lineage_graph(),
            org_fragments=[],
            project=None,
        )
        assert any(
            e.relation is Relation.SPECIALIZES_FROM
            and e.source == "agent_profile:child"
            and e.target == "agent_profile:parent"
            for e in merged.edges
        )

    def test_org_valid_lineage_edge_present(self) -> None:
        org = _fragment(
            "p",
            nodes=[
                {"id": "child", "kind": "agent_profiles", "title": "Child"},
                {"id": "parent", "kind": "agent_profiles", "title": "Parent"},
            ],
            edges=[
                {
                    "source": "child",
                    "target": "parent",
                    "relation": "specializes_from",
                }
            ],
        )
        merged = merge_three_layers(
            built_in=_graph(), org_fragments=[org], project=None
        )
        assert any(
            e.relation is Relation.SPECIALIZES_FROM
            and e.source == "agent_profile:child"
            and e.target == "agent_profile:parent"
            for e in merged.edges
        )

    def test_project_valid_lineage_edge_present(self) -> None:
        merged = merge_three_layers(
            built_in=_graph(),
            org_fragments=[],
            project=self._shipped_lineage_graph(),
        )
        assert any(
            e.relation is Relation.SPECIALIZES_FROM
            and e.source == "agent_profile:child"
            and e.target == "agent_profile:parent"
            for e in merged.edges
        )

    def test_shipped_unknown_relation_rejected(self) -> None:
        """The shipped/project tiers reject an unknown relation at DRGEdge
        construction time (Pydantic ValidationError) — the loud path the
        org tier now matches."""
        with pytest.raises(ValidationError):
            DRGEdge(
                source="agent_profile:child",
                target="agent_profile:parent",
                relation="bogus",  # type: ignore[arg-type]
            )

    def test_org_unknown_relation_rejected(self) -> None:
        org = _fragment(
            "p",
            nodes=[
                {"id": "child", "kind": "agent_profiles", "title": "Child"},
                {"id": "parent", "kind": "agent_profiles", "title": "Parent"},
            ],
            edges=[{"source": "child", "target": "parent", "relation": "bogus"}],
        )
        with pytest.raises(UnknownRelationError):
            merge_three_layers(built_in=_graph(), org_fragments=[org], project=None)

    def test_project_unknown_relation_rejected(self) -> None:
        """A project-tier DRGGraph cannot even be constructed with an unknown
        relation, so the unknown-relation path is closed before merge."""
        with pytest.raises(ValidationError):
            _graph(
                nodes=[
                    DRGNode(urn="tactic:x", kind=NodeKind.TACTIC),
                    DRGNode(urn="directive:y", kind=NodeKind.DIRECTIVE),
                ],
                edges=[
                    DRGEdge(
                        source="tactic:x",
                        target="directive:y",
                        relation="bogus",  # type: ignore[arg-type]
                    ),
                ],
            )


# ---------------------------------------------------------------------------
# Invariant regressions preserved through the relocation
# ---------------------------------------------------------------------------


class TestInvariantsPreserved:
    def test_same_kind_org_override_of_shipped_node_succeeds(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A SAME-KIND org override now wins in place: the org node substitutes
        the built-in, a ``node_override``/``org_override`` conflict is recorded,
        a WARNING is emitted, and the merge does NOT raise. (Previously this
        path hard-failed; the override semantics permit it — governance is a
        per-repo TEST, not a merge prohibition.)"""
        built_in = _graph(
            nodes=[
                DRGNode(
                    urn="directive:locked",
                    kind=NodeKind.DIRECTIVE,
                    label="Built-in",
                )
            ]
        )
        org = _fragment(
            "rogue",
            nodes=[{"id": "locked", "kind": "directives", "title": "Override"}],
            edges=[],
        )

        with caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"):
            merged = merge_three_layers(
                built_in=built_in, org_fragments=[org], project=None
            )

        # Org node wins in place (provenance + label substituted).
        node = next(n for n in merged.nodes if n.urn == "directive:locked")
        assert node.provenance == "org:rogue"
        assert node.label == "Override"
        # A WARNING is emitted for operator visibility.
        assert any(
            record.levelno == logging.WARNING
            and "directive:locked" in record.getMessage()
            for record in caplog.records
        )

    def test_same_kind_org_override_records_org_override_conflict(self) -> None:
        """The permitted override is queryable as a non-fatal conflict record
        with ``resolution_applied == 'org_override'``."""
        from charter.offering.drg.merge import (  # noqa: PLC0415 — local-only helper import
            _resolve_builtin_collision,
        )
        from charter.offering.drg.merge import _tag_source  # noqa: PLC0415

        built_in_node = _tag_source(
            DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC), "built-in"
        )
        merged_nodes = {"tactic:shared": built_in_node}
        conflicts: list[OrgDRGConflict] = []
        org_node_model = OrgDRGFragment.model_validate(
            {
                "pack_name": "p",
                "source_kind": "local_path",
                "source_ref": "/nonexistent/p",
                "layer_index": 1,
                "nodes": [{"id": "shared", "kind": "tactics", "title": "T"}],
                "edges": [],
            }
        ).nodes[0]
        org_drg = _tag_source(
            DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC, label="T"),
            "org:p",
        )

        _resolve_builtin_collision(
            "tactic:shared",
            org_node_model,
            org_drg,
            merged_nodes,
            conflicts,
            "org:p",
        )

        # cardinality-is-contract: a single node override records exactly one conflict; the projection collapses duplicate conflict records
        assert len(conflicts) == 1
        assert {(c.kind, c.resolution_applied) for c in conflicts} == {
            ("node_override", "org_override")
        }
        assert conflicts[0].kind == "node_override"
        assert conflicts[0].resolution_applied == "org_override"
        # Substitution happened in place.
        assert merged_nodes["tactic:shared"].provenance == "org:p"

    def test_kind_drift_org_override_hard_fails(self) -> None:
        """A DIFFERENT-KIND collision (kind-drift) STILL hard-fails: an override
        may replace a built-in's content, never its kind.

        :class:`DRGNode` validates ``urn-prefix == kind``, so two *valid*
        DRGNodes can never share a URN with differing kinds — kind-drift is a
        defensive guard against an un-validated built-in node reaching the
        merge. We exercise the guard directly via :func:`_resolve_builtin_collision`
        with a built-in whose kind has been desynced from its URN, asserting the
        merge refuses the substitution rather than corrupting the node's kind.
        """
        from charter.offering.drg.merge import (  # noqa: PLC0415
            _resolve_builtin_collision,
            _tag_source,
        )

        # A built-in node whose reported kind drifts from its URN prefix
        # (model_construct bypasses the urn/kind validator to simulate the
        # un-validated input the guard exists to catch).
        drifted_builtin = DRGNode.model_construct(
            urn="directive:locked", kind=NodeKind.TACTIC, label="built-in"
        )
        merged_nodes: dict[str, DRGNode] = {"directive:locked": drifted_builtin}
        conflicts: list[OrgDRGConflict] = []
        org_drg = _tag_source(
            DRGNode(urn="directive:locked", kind=NodeKind.DIRECTIVE, label="org"),
            "org:rogue",
        )
        org_model = _fragment(
            "rogue",
            nodes=[{"id": "locked", "kind": "directives", "title": "Drift"}],
            edges=[],
        ).nodes[0]

        _resolve_builtin_collision(
            "directive:locked",
            org_model,
            org_drg,
            merged_nodes,
            conflicts,
            "org:rogue",
        )

        assert conflicts[0].resolution_applied == "hard_fail"
        # Substitution did NOT happen — kind-drift is refused.
        assert merged_nodes["directive:locked"] is drifted_builtin

    def test_layer_rule_violation_hard_fails(self) -> None:
        org = _fragment(
            "smuggler",
            nodes=[
                {
                    "id": "x",
                    "kind": "tactics",
                    "title": "X",
                    "body_path": "src/specify_cli/sneaky.py",
                }
            ],
            edges=[],
        )
        with pytest.raises(OrgDRGConflictError) as exc_info:
            merge_three_layers(built_in=_graph(), org_fragments=[org], project=None)
        assert any(
            c.kind == "layer_rule_violation" for c in exc_info.value.conflicts
        )


class TestProvenanceDeclaredField:
    """FR-013 (D2-revised): ``provenance`` is a declared optional field on the
    DRG models, set via :func:`_tag_source`'s ``model_copy`` — not the former
    ``object.__setattr__`` sidecar."""

    def test_provenance_defaults_to_none(self) -> None:
        node = DRGNode(urn="directive:x", kind=NodeKind.DIRECTIVE)
        edge = DRGEdge(
            source="directive:x",
            target="directive:y",
            relation=Relation.REQUIRES,
        )
        assert node.provenance is None
        assert edge.provenance is None

    def test_tag_source_sets_declared_field_typed_roundtrip(self) -> None:
        from charter.offering.drg.merge import _tag_source

        node = DRGNode(urn="directive:x", kind=NodeKind.DIRECTIVE)
        tagged = _tag_source(node, "built-in")
        # Read the declared field directly (no getattr fallback needed).
        assert tagged.provenance == "built-in"
        # model_copy returns a fresh instance; the original is untouched.
        assert node.provenance is None
        assert tagged is not node
        # Provenance round-trips through model identity (same URN/kind).
        assert tagged.urn == node.urn
        assert tagged.kind == node.kind

    def test_merged_nodes_and_edges_expose_typed_field(self) -> None:
        built_in = _graph(
            nodes=[DRGNode(urn="directive:base", kind=NodeKind.DIRECTIVE)],
            edges=[
                DRGEdge(
                    source="directive:base",
                    target="tactic:t",
                    relation=Relation.SUGGESTS,
                )
            ],
        )
        merged = merge_three_layers(
            built_in=built_in, org_fragments=[], project=None
        )
        assert all(n.provenance == "built-in" for n in merged.nodes)
        assert all(e.provenance == "built-in" for e in merged.edges)


# ---------------------------------------------------------------------------
# Governance-as-test: the per-repo replaceable-builtins allowlist
# ---------------------------------------------------------------------------


class TestReplaceableBuiltinsPolicy:
    """The merge PERMITS a same-kind override; a per-repo allowlist GOVERNS
    whether the override is sanctioned. The loader fails closed."""

    def _write_policy(self, root: Path, body: str) -> None:
        policy_dir = root / ".kittify" / "doctrine"
        policy_dir.mkdir(parents=True, exist_ok=True)
        (policy_dir / "replaceable-builtins.yaml").write_text(
            body, encoding="utf-8"
        )

    def test_absent_file_forbids_every_override(self, tmp_path: Path) -> None:
        from charter.offering.drg.override_policy import load_replaceable_builtins

        policy = load_replaceable_builtins(tmp_path)
        assert policy.entries == ()
        assert policy.is_allowed("directive:anything") is False
        assert policy.reason_for("directive:anything") is None

    def test_unlisted_urn_forbidden_listed_allowed(self, tmp_path: Path) -> None:
        from charter.offering.drg.override_policy import load_replaceable_builtins

        self._write_policy(
            tmp_path,
            "replaceable_builtins:\n"
            "  - urn: directive:risk-appetite\n"
            "    reason: Our org sets a different risk posture.\n",
        )
        policy = load_replaceable_builtins(tmp_path)
        assert policy.is_allowed("directive:risk-appetite") is True
        assert policy.reason_for("directive:risk-appetite") == (
            "Our org sets a different risk posture."
        )
        # A non-listed URN is fail-closed forbidden.
        assert policy.is_allowed("directive:mission-scope") is False

    def test_directive_override_requires_reason(self, tmp_path: Path) -> None:
        """A built-in *directive* override additionally requires a non-empty
        reason — the governance predicate the architectural test enforces."""
        from charter.offering.drg.override_policy import load_replaceable_builtins

        self._write_policy(
            tmp_path,
            "replaceable_builtins:\n  - urn: directive:no-reason\n",
        )
        policy = load_replaceable_builtins(tmp_path)
        assert policy.is_allowed("directive:no-reason") is True
        # The reason is empty -> a directive override would FAIL the per-repo
        # governance test even though the URN is listed.
        assert policy.reason_for("directive:no-reason") == ""

    @pytest.mark.parametrize(
        "body",
        [
            "replaceable_builtins: not-a-list\n",  # entries not a list
            "- just-a-bare-list\n",  # top-level not a mapping
            "replaceable_builtins:\n  - not-a-mapping\n",  # entry not a mapping
            "replaceable_builtins:\n  - urn: ''\n",  # empty urn
            "replaceable_builtins:\n  - {urn: directive:x, reason: 7}\n",  # reason
            "key: [unclosed\n",  # YAML parse error
        ],
    )
    def test_malformed_policy_fails_closed_loud(
        self, tmp_path: Path, body: str
    ) -> None:
        from charter.offering.drg.override_policy import (
            OverridePolicyError,
            load_replaceable_builtins,
        )

        self._write_policy(tmp_path, body)
        with pytest.raises(OverridePolicyError):
            load_replaceable_builtins(tmp_path)

    def test_empty_file_is_empty_policy(self, tmp_path: Path) -> None:
        from charter.offering.drg.override_policy import load_replaceable_builtins

        self._write_policy(tmp_path, "")
        policy = load_replaceable_builtins(tmp_path)
        assert policy.entries == ()

    def test_null_entries_and_null_reason_normalise_to_empty(
        self, tmp_path: Path
    ) -> None:
        """A ``null`` ``replaceable_builtins`` value and a ``null`` reason both
        normalise to empty (fail-closed-friendly, not an error)."""
        from charter.offering.drg.override_policy import load_replaceable_builtins

        self._write_policy(tmp_path, "replaceable_builtins:\n")
        assert load_replaceable_builtins(tmp_path).entries == ()

        self._write_policy(
            tmp_path,
            "replaceable_builtins:\n  - urn: tactic:x\n    reason: ~\n",
        )
        policy = load_replaceable_builtins(tmp_path)
        assert policy.reason_for("tactic:x") == ""


# ---------------------------------------------------------------------------
# WP03 T013 — global asset:/template: URN-uniqueness scan (FR-002/007/008)
# ---------------------------------------------------------------------------


class TestGlobalURNUniquenessScan:
    """D-04 (revised): a single post-merge, order-independent, prefix-scoped
    scan over the fully-assembled built-in/org/project node set hard-fails on
    any duplicate ``asset:`` or ``template:`` URN — replacing the org-vs-org
    silent first-wins for these two kinds and additionally covering the
    built-in-vs-org and project-vs-any collision surfaces. The other 9 kinds'
    layered-override tolerance (org-vs-org first-wins, built-in-vs-org
    override, project-vs-any override) is untouched by construction."""

    def test_two_org_packs_shipping_duplicate_asset_id_hard_fails(self) -> None:
        """(a) Two org packs each declare ``asset:logo`` — an org-vs-org
        collision that the old code silently resolved as first-wins now
        hard-fails with the structured ``duplicate_asset_id`` code."""
        pack_one = _fragment(
            "pack-one",
            nodes=[{"id": "logo", "kind": "assets", "title": "Logo"}],
            edges=[],
        )
        pack_two = _fragment(
            "pack-two",
            nodes=[{"id": "logo", "kind": "assets", "title": "Logo Again"}],
            edges=[],
        )
        with pytest.raises(DuplicateURNError) as exc_info:
            merge_three_layers(
                built_in=_graph(), org_fragments=[pack_one, pack_two], project=None
            )
        err = exc_info.value
        assert err.code == "duplicate_asset_id"
        assert err.urn == "asset:logo"
        assert err.count == 2
        assert "duplicate_asset_id" in str(err)

    def test_builtin_and_org_duplicate_template_id_hard_fails_cross_layer(
        self,
    ) -> None:
        """(b) A built-in ``template:x`` and an org-declared ``template:x``
        collide across layers. Same-kind built-in-vs-org collisions are
        normally a PERMITTED override (``_resolve_builtin_collision``); the
        new global scan overrides that tolerance specifically for TEMPLATE
        (and ASSET) and hard-fails with ``duplicate_template_id``."""
        built_in = _graph(
            nodes=[DRGNode(urn="template:x", kind=NodeKind.TEMPLATE, label="Shipped")]
        )
        org = _fragment(
            "acme",
            nodes=[{"id": "x", "kind": "templates", "title": "Org"}],
            edges=[],
        )
        with pytest.raises(DuplicateURNError) as exc_info:
            merge_three_layers(built_in=built_in, org_fragments=[org], project=None)
        err = exc_info.value
        assert err.code == "duplicate_template_id"
        assert err.urn == "template:x"
        assert err.count == 2

    def test_single_owner_asset_and_template_merge_cleanly(self) -> None:
        """(c) One asset and one template, each declared exactly once across
        the three layers, merge without error and land in the output graph."""
        built_in = _graph(
            nodes=[DRGNode(urn="template:shipped-tpl", kind=NodeKind.TEMPLATE)]
        )
        org = _fragment(
            "acme",
            nodes=[{"id": "logo", "kind": "assets", "title": "Logo"}],
            edges=[],
        )
        merged = merge_three_layers(
            built_in=built_in, org_fragments=[org], project=None
        )
        urns = {n.urn for n in merged.nodes}
        assert "template:shipped-tpl" in urns
        assert "asset:logo" in urns

    def test_different_kind_same_id_override_still_tolerated_not_hard_failed(
        self,
    ) -> None:
        """(d) REGRESSION: the new global scan is scoped strictly to
        ``asset:``/``template:`` prefixes. An org ``directive:x`` overriding a
        built-in ``directive:x`` (same URN, same kind, neither asset nor
        template) is UNCHANGED — still a permitted, non-fatal override, never
        routed through :class:`DuplicateURNError`."""
        built_in = _graph(
            nodes=[
                DRGNode(urn="directive:x", kind=NodeKind.DIRECTIVE, label="Built-in")
            ]
        )
        org = _fragment(
            "acme",
            nodes=[{"id": "x", "kind": "directives", "title": "Override"}],
            edges=[],
        )
        merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=None)
        node = next(n for n in merged.nodes if n.urn == "directive:x")
        assert node.provenance == "org:acme"
        assert node.label == "Override"

    def test_asset_duplicate_scan_ignores_other_kind_prefixes(self) -> None:
        """The scan is prefix-scoped: a duplicate ``tactic:`` URN (a 9-kind
        collision, resolved by the existing override machinery) must never be
        mistaken for an asset/template duplicate."""
        built_in = _graph(
            nodes=[DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC, label="Base")]
        )
        org = _fragment(
            "acme",
            nodes=[{"id": "shared", "kind": "tactics", "title": "Override"}],
            edges=[],
        )
        # Does not raise DuplicateURNError — the override machinery handles it.
        merged = merge_three_layers(built_in=built_in, org_fragments=[org], project=None)
        assert any(n.urn == "tactic:shared" for n in merged.nodes)


# ---------------------------------------------------------------------------
# WP03 T011 — _filter_surviving_org_nodes (extracted from _merge_org_fragment
# to keep its cognitive complexity within the ruff C901 limit)
# ---------------------------------------------------------------------------


class TestFilterSurvivingOrgNodes:
    """Direct unit tests for the layer-rule filtering helper (C-001/FR-005)."""

    def test_all_nodes_survive_when_none_violate_layer_rule(self) -> None:
        fragment = _fragment(
            "acme",
            nodes=[
                {"id": "policy", "kind": "directives", "title": "Policy"},
                {"id": "play", "kind": "tactics", "title": "Play"},
            ],
            edges=[],
        )
        conflicts: list[OrgDRGConflict] = []

        surviving = _filter_surviving_org_nodes(fragment, conflicts, "org:acme")

        assert [n.id for n in surviving] == ["policy", "play"]
        assert conflicts == []

    def test_violating_node_is_excluded_and_recorded_as_hard_fail(self) -> None:
        fragment = _fragment(
            "acme",
            nodes=[
                {"id": "policy", "kind": "directives", "title": "Policy"},
                {
                    "id": "smuggled",
                    "kind": "directives",
                    "title": "Reaches into specify_cli.core",
                },
            ],
            edges=[],
        )
        conflicts: list[OrgDRGConflict] = []

        surviving = _filter_surviving_org_nodes(fragment, conflicts, "org:acme")

        assert [n.id for n in surviving] == ["policy"]
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.kind == "layer_rule_violation"
        assert conflict.target_id == "smuggled"
        assert conflict.conflicting_layers == ["org:acme"]
        assert conflict.resolution_applied == "hard_fail"

    def test_empty_fragment_yields_no_survivors_and_no_conflicts(self) -> None:
        fragment = _fragment("acme", nodes=[], edges=[])

        surviving = _filter_surviving_org_nodes(fragment, [], "org:acme")

        assert surviving == []
