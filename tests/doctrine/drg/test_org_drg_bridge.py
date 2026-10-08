"""org->DRG bridge integrity (WP08, FR-010/FR-011, SC-009).

The bridge between an organisation pack's fragment shape (bare ids + plural
kinds) and the canonical DRG (URNs + :class:`NodeKind`) had five measured
integrity defects, each an instance of the mission's root finding — *the
doctrine layer's failure mode is silence, not error*. Measured on
``remediation/doctrine-silence-guards`` @ ``13464fea7`` before this file
existed:

===  ===================================================  =====================
D    Shape                                                Behaviour before WP08
===  ===================================================  =====================
D1   built-in-source -> pack-target edge                  dropped: ``None``,
                                                          0 warnings,
                                                          0 conflict records
D2   bare target naming a non-directive built-in          re-kinded to
                                                          ``directive:<id>`` —
                                                          a phantom node
D3   URN-shaped target (``agent_profile:ryan``)           raw
                                                          ``pydantic_core``
                                                          ``ValidationError``
D4   ``mission_types`` / ``glossary_packs`` node          raw ``KeyError`` —
                                                          2 of 12 canonical
                                                          plural kinds unmapped
D5   field-projection auto-emitted edge                   dropped: 100% of the
     (URN-shaped **source**)                              legacy projection
                                                          path never landed
===  ===================================================  =====================

Root-cause accounting (corrected — an earlier write-up said "one fix, not
five", which overstates the unification by one):

* **D1, D2, D3, D5 — one root cause, one fix.** The bridge ran two asymmetric
  endpoint policies (a source had to be fragment-local, miss → silent drop; a
  target fell back to ``directive:<id>``, miss → invented kind), and neither
  accepted the URN form the pack's own emitter produces. All four collapse
  into the single ordered precedence in
  ``charter.offering.drg.merge._resolve_edge_endpoint``.
* **D4 — a second root cause, a different mechanism, a different module.** A
  hand-restated *node*-kind map, fixed by deriving it beside the universe it
  inverts (``org_pack_loader._derive_plural_to_singular``). Nothing to do with
  endpoint policy.
* The node-side ``malformed_urn`` return in
  ``_bridge_org_node_to_drg_node`` is a third, smaller fix on the node side.

So: four of five behind one endpoint policy, plus a second root cause on the
node-minting side. The code was always structured as two fixes in two modules;
only the description overreached.

ADR ``2026-07-26-3`` makes this file's fixes a precondition for mission B1:
adding ``Relation.IMPACTS`` to a bridge with a silent-drop path ships a
relation that works for built-ins and silently fails for external packs.

Every test here drives the **real** transport
(:func:`charter.offering.drg.merge.merge_three_layers`) — no reimplementation of the
resolution rules under test.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from charter.offering.drg.merge import OrgDRGConflictError, merge_three_layers
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.org_pack_loader import OrgDRGFragment, load_org_pack
from charter.offering.drg.validator import validate_dangling_references, validate_graph

pytestmark = [pytest.mark.unit, pytest.mark.corpus]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _minter() -> dict[str, str]:
    """The bridge's plural -> singular URN-kind map.

    Imported lazily so this module still *collects* before WP08 lands the
    symbol — a collection error would collapse the whole red map into one
    ``ImportError`` and hide which behaviours are actually broken.
    """
    from charter.offering.drg.org_pack_loader import ORG_PLURAL_TO_SINGULAR_KIND

    return ORG_PLURAL_TO_SINGULAR_KIND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _graph(*nodes: DRGNode, edges: list[DRGEdge] | None = None) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-26T00:00:00Z",
        generated_by="test_org_drg_bridge",
        nodes=list(nodes),
        edges=list(edges or []),
    )


def _fragment(
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    *,
    pack_name: str = "probe-pack",
) -> OrgDRGFragment:
    return OrgDRGFragment.model_validate(
        {
            "pack_name": pack_name,
            "source_kind": "local_path",
            # Inert provenance string — never opened, never written. A shared
            # /tmp literal here would trip the tmp-literal ban (#KWWRW2 FR-002)
            # for a path that is not a real filesystem target, so use a
            # non-shared-temp absolute sentinel.
            "source_ref": f"/nonexistent/org-packs/{pack_name}",
            "layer_index": 1,
            "nodes": nodes,
            "edges": edges,
        }
    )


def _built_in() -> DRGGraph:
    """A small built-in layer carrying one node of three distinct kinds.

    ``caveman-comments`` is deliberately a **styleguide** — the shape the
    in-repo ``tests/architectural/_fixtures/org_packs/example_org`` fixture
    exercises (a bare, non-fragment-local target whose declared kind is not
    ``directive``), and the one D2 mistranslated into
    ``directive:caveman-comments``.
    """
    return _graph(
        DRGNode(urn="directive:builtin-alpha", kind=NodeKind.DIRECTIVE),
        DRGNode(urn="styleguide:caveman-comments", kind=NodeKind.STYLEGUIDE),
        DRGNode(urn="agent_profile:researcher-ryan", kind=NodeKind.AGENT_PROFILE),
    )


def _duplicate_edge_errors(merged: DRGGraph) -> list[str]:
    """The canonical checker's verdict on repeated ``(source, target, relation)``.

    Filtered out of the public :func:`validate_graph` rather than reaching for
    the private per-check helper, so this asserts against the API the rest of
    the codebase uses and cannot false-red when an unrelated check is added.
    """
    return [e for e in validate_graph(merged) if e.startswith("Duplicate edge")]


def _org_edges(merged: DRGGraph, built_in: DRGGraph) -> list[tuple[str, str, str]]:
    """Return the ``(source, target, relation)`` triples the org layer added."""
    before = {(e.source, e.target, str(e.relation)) for e in built_in.edges}
    return [(e.source, e.target, str(e.relation)) for e in merged.edges if (e.source, e.target, str(e.relation)) not in before]


# ---------------------------------------------------------------------------
# D1 — the silent cross-layer drop (FR-010, SC-009, US3 scenario 1)
# ---------------------------------------------------------------------------


class TestUnresolvableEndpointIsNeverSilent:
    def test_builtin_source_to_pack_target_edge_raises_with_a_conflict_record(
        self,
    ) -> None:
        """A source the fragment does not declare must not vanish.

        Before WP08 :func:`bridge_org_edge_to_drg_edge` returned ``None`` for
        any source missing from the fragment-local index and
        :func:`_merge_org_fragment` dropped it — no warning, no conflict
        record, no trace. This is the exact shape ADR 2026-07-26-3 names.
        """
        fragment = _fragment(
            [{"id": "pack-thing", "kind": "directives", "title": "Pack Thing"}],
            [
                {
                    "source": "no-such-artefact-anywhere",
                    "target": "pack-thing",
                    "relation": "requires",
                }
            ],
        )

        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_built_in(), [fragment], None)

        conflict_kinds = {c.kind for c in excinfo.value.conflicts}
        assert "unresolved_edge_endpoint" in conflict_kinds, f"expected an unresolved_edge_endpoint conflict record, got {sorted(conflict_kinds)}"
        offending = [c for c in excinfo.value.conflicts if c.kind == "unresolved_edge_endpoint"]
        assert offending[0].target_id == "no-such-artefact-anywhere", (
            f"the conflict must name the offending endpoint token so the pack author can find it; got {offending[0].target_id!r}"
        )
        assert offending[0].resolution_applied == "hard_fail"
        assert "org:probe-pack" in offending[0].conflicting_layers
        # The edge dict must be recoverable from the record — kind says *why*,
        # target_id says *which token*, org_value says *which edge*.
        assert offending[0].org_value["relation"] == "requires"

    def test_ambiguous_bare_endpoint_is_a_conflict_not_a_coin_flip(self) -> None:
        """A bare id matching two kinds must not resolve to an arbitrary one.

        Before WP08 the bridge answered this by construction: every unresolved
        bare target became ``directive:<id>``, so the directive interpretation
        always silently won.
        """
        built_in = _graph(
            DRGNode(urn="directive:shared-id", kind=NodeKind.DIRECTIVE),
            DRGNode(urn="tactic:shared-id", kind=NodeKind.TACTIC),
        )
        fragment = _fragment(
            [{"id": "pack-thing", "kind": "directives", "title": "Pack Thing"}],
            [
                {
                    "source": "pack-thing",
                    "target": "shared-id",
                    "relation": "requires",
                }
            ],
        )

        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(built_in, [fragment], None)

        ambiguous = [c for c in excinfo.value.conflicts if c.kind == "ambiguous_edge_endpoint"]
        assert ambiguous, f"an id resolvable to two kinds must be reported ambiguous, not silently bound to one; got {[c.kind for c in excinfo.value.conflicts]}"
        assert ambiguous[0].target_id == "shared-id"

    def test_the_conflict_message_names_the_offending_token(self) -> None:
        """``OrgDRGConflictError``'s message must be operator-actionable."""
        fragment = _fragment(
            [{"id": "pack-thing", "kind": "directives"}],
            [
                {
                    "source": "pack-thing",
                    "target": "urn:profile:researcher-ryan",
                    "relation": "specializes_from",
                }
            ],
        )
        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_built_in(), [fragment], None)
        message = str(excinfo.value)
        assert "urn:profile:researcher-ryan" in message
        # ...and the remediation must address the endpoint, not tell the
        # author to "remove the override" of a thing they never overrode.
        assert "Remediation (endpoint)" in message
        assert "Remediation (override)" not in message
        assert "agent_profile:researcher-ryan" in message, "the guidance must show the shape that does resolve"

    def test_every_conflict_class_carries_a_remediation_line(self) -> None:
        """C-009 coverage gate for the remediation table.

        A conflict class with no remediation entry is a slot with no producer:
        the operator gets a class name and no way to act on it.
        """
        import typing

        from charter.offering.drg.merge import _CONFLICT_REMEDIATIONS, OrgDRGConflict

        # ``from __future__ import annotations`` makes __annotations__ strings;
        # resolve them so the gate reads the real Literal members.
        hints = typing.get_type_hints(OrgDRGConflict)
        declared = set(typing.get_args(hints["kind"]))
        assert len(declared) >= 7, (
            f"floor: OrgDRGConflict.kind declares >= 7 classes, saw {declared}"
        )
        assert declared == set(_CONFLICT_REMEDIATIONS), (
            "conflict classes without operator remediation: "
            f"{sorted(declared - set(_CONFLICT_REMEDIATIONS))}; "
            "remediation entries for no conflict class: "
            f"{sorted(set(_CONFLICT_REMEDIATIONS) - declared)}"
        )


# ---------------------------------------------------------------------------
# D2 — blind re-kinding (FR-010, US3)
# ---------------------------------------------------------------------------


class TestBareTargetsAreResolvedByKindNotInvented:
    def test_bare_target_naming_a_styleguide_does_not_become_a_directive(self) -> None:
        """The in-repo ``example_org`` shape: ``sox-controls --refines--> caveman-comments``.

        ``caveman-comments`` is a styleguide. Before WP08 the bridge minted
        ``directive:caveman-comments`` — a node that exists nowhere in the
        merged graph, producing a dangling edge that every downstream traversal
        silently fails to follow.
        """
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "sox-controls", "kind": "directives", "title": "SOX"}],
            [
                {
                    "source": "sox-controls",
                    "target": "caveman-comments",
                    "relation": "refines",
                }
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [("directive:sox-controls", "styleguide:caveman-comments", "refines")]

    def test_no_merged_edge_endpoint_is_a_phantom_node(self) -> None:
        """Every endpoint the bridge mints must exist in the merged node set."""
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "sox-controls", "kind": "directives"}],
            [
                {
                    "source": "sox-controls",
                    "target": "caveman-comments",
                    "relation": "refines",
                },
                {
                    "source": "sox-controls",
                    "target": "builtin-alpha",
                    "relation": "requires",
                },
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        urns = {n.urn for n in merged.nodes}
        dangling = [(e.source, e.target) for e in merged.edges if e.source not in urns or e.target not in urns]
        assert dangling == [], f"bridge minted phantom endpoints: {dangling}"


# ---------------------------------------------------------------------------
# D3 — URN-shaped endpoints (FR-010, US3 scenario 3)
# ---------------------------------------------------------------------------


class TestUrnShapedEndpoints:
    def test_urn_shaped_target_resolves_verbatim(self) -> None:
        """A fully-qualified target is unambiguous — accept it as authored.

        Before WP08 it was re-kinded to ``directive:agent_profile:researcher-ryan``,
        which fails ``DRGEdge``'s URN regex and escaped as a raw
        ``pydantic_core.ValidationError`` from deep inside the merge.
        """
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "my-analyst", "kind": "agent_profiles", "title": "Analyst"}],
            [
                {
                    "source": "my-analyst",
                    "target": "agent_profile:researcher-ryan",
                    "relation": "specializes_from",
                }
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                "specializes_from",
            )
        ]

    def test_urn_shaped_source_resolves_verbatim(self) -> None:
        """Symmetry: source and target obey one resolution policy, not two.

        The asymmetry (source = fragment-local-only, target = fragment-local
        or invented) is the structural cause of D1 and D5.
        """
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "my-analyst", "kind": "agent_profiles"}],
            [
                {
                    "source": "agent_profile:my-analyst",
                    "target": "agent_profile:researcher-ryan",
                    "relation": "specializes_from",
                }
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                "specializes_from",
            )
        ]

    @pytest.mark.parametrize(
        ("target", "expected_kind"),
        [
            # Illegal character in the id half: URN-shaped, valid kind prefix,
            # unparseable => malformed, not "not found".
            ("agent_profile:has space", "malformed_urn"),
            # A kind prefix that is not a NodeKind member: the author used a
            # vocabulary that does not exist (this is the CLAUDE.md shape).
            ("urn:profile:researcher-ryan", "unresolved_edge_endpoint"),
            ("nosuchkind:whatever", "unresolved_edge_endpoint"),
        ],
    )
    def test_unresolvable_urn_shaped_target_raises_a_typed_pack_error(self, target: str, expected_kind: str) -> None:
        """US3 scenario 3 — a typed pack error, never a raw pydantic error."""
        fragment = _fragment(
            [{"id": "my-analyst", "kind": "agent_profiles"}],
            [
                {
                    "source": "my-analyst",
                    "target": target,
                    "relation": "specializes_from",
                }
            ],
        )

        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_built_in(), [fragment], None)

        matching = [c for c in excinfo.value.conflicts if c.target_id == target]
        assert matching, f"no conflict record named {target!r}"
        assert matching[0].kind == expected_kind

    def test_a_node_id_that_cannot_form_a_urn_is_a_typed_pack_error(self) -> None:
        """The same guarantee on the node side of the bridge.

        ``_OrgDRGNode.id`` is a free-form ``str``, so a pack could always mint
        an unparseable URN. Before WP08 that escaped as a raw
        ``pydantic_core.ValidationError`` from ``_bridge_org_node_to_drg_node``.
        """
        fragment = _fragment([{"id": "has space", "kind": "directives"}], [])

        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_built_in(), [fragment], None)

        assert [c.kind for c in excinfo.value.conflicts] == ["malformed_urn"]
        assert excinfo.value.conflicts[0].target_id == "directive:has space"


# ---------------------------------------------------------------------------
# D4 — plural-kind coverage is derived, not hand-restated (FR-010, C-009)
# ---------------------------------------------------------------------------


class TestPluralKindCoverageIsTotal:
    """The bridge's URN minter is the **fourth** hand-restated DRG writer.

    ``merge._PLURAL_TO_SINGULAR`` restated the org-pack plural universe by
    hand and had drifted 2 kinds behind ``_ORG_DRG_KIND_ALIASES``. WP04 fixed
    the same class in the extractor by deriving from ``NodeKind``; this does
    it for the bridge by deriving from the loader's own alias table.
    """

    def test_every_accepted_org_pack_plural_kind_mints_a_urn(self) -> None:
        """The coverage gate (C-009). Concrete floor: all 12 canonical kinds.

        Drives the real merge per kind, so the gate fails on a *behavioural*
        gap, not merely a missing dict key.

        Only the **typed** refusal is caught and aggregated. An untyped escape
        — the bare ``KeyError`` this map used to raise — propagates and errors
        the test outright, which is the louder and more correct signal: this
        WP exists precisely because untyped failures were leaking out of the
        merge.
        """
        from charter.offering.drg.org_pack_loader import _ORG_DRG_KIND_ALIASES

        accepted = sorted(_ORG_DRG_KIND_ALIASES)
        assert len(accepted) >= 12, "floor: the loader accepts >= 12 input forms"

        failures: dict[str, str] = {}
        for plural in accepted:
            fragment = _fragment([{"id": "probe-node", "kind": plural}], [])
            try:
                merged = merge_three_layers(_graph(), [fragment], None)
            except OrgDRGConflictError as exc:
                failures[plural] = "; ".join(c.kind for c in exc.conflicts)
                continue
            if len(merged.nodes) != 1:
                failures[plural] = f"minted {len(merged.nodes)} nodes"
        assert failures == {}, f"org-pack plural kinds the bridge cannot mint a URN for (hand-restated map drifted behind the loader universe): {failures}"

    def test_the_minter_is_derived_from_the_loader_universe(self) -> None:
        """Totality by construction — the property that keeps the gate honest.

        Equality (not containment) in both directions: a canonical kind
        added to the loader but not the minter fails, and a minter entry that
        no canonical kind resolves to fails too — no dead map entries.
        """
        from charter.offering.drg.org_pack_loader import _ORG_DRG_KIND_ALIASES

        assert set(_minter()) == set(_ORG_DRG_KIND_ALIASES.values())

    def test_every_minted_singular_is_a_real_nodekind(self) -> None:
        """A singular with no ``NodeKind`` member would fail at ``NodeKind(...)``."""
        node_kinds = {k.value for k in NodeKind}
        assert set(_minter().values()) <= node_kinds

    def test_the_coverage_gate_would_catch_a_reintroduced_gap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Self-mutation (standing order 5): prove the gate can fail.

        Delete one kind from the derived minter and assert the merge for that
        kind now fails — i.e. the gate above is load-bearing, not decorative.
        """
        mutated = dict(_minter())
        removed = mutated.pop("mission_types")
        assert removed == "mission_type"
        monkeypatch.setattr("charter.offering.drg.merge.ORG_PLURAL_TO_SINGULAR_KIND", mutated, raising=True)

        fragment = _fragment([{"id": "probe-node", "kind": "mission_types"}], [])
        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_graph(), [fragment], None)
        assert [c.kind for c in excinfo.value.conflicts] == ["kind_mismatch"]

    def test_an_unmappable_plural_kind_is_a_typed_conflict_not_a_keyerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Even the impossible branch fails typed. D4's raw ``KeyError`` is gone."""
        monkeypatch.setattr("charter.offering.drg.merge.ORG_PLURAL_TO_SINGULAR_KIND", {})
        fragment = _fragment([{"id": "probe-node", "kind": "directives"}], [])
        with pytest.raises(OrgDRGConflictError):
            merge_three_layers(_graph(), [fragment], None)


# ---------------------------------------------------------------------------
# D5 — the field-projection producer whose output never landed
# ---------------------------------------------------------------------------


class TestFieldProjectionEdgesReachTheGraph:
    """``_collect_augmentation_edges`` emits ``<kind>:<id>`` on **both**
    endpoints. The bridge's source lookup was keyed on bare fragment-local ids
    only, so 100% of that producer's output was discarded at the bridge — a
    zero-effect producer, the mission's own defect class one layer up.
    """

    def test_auto_emitted_projection_edge_survives_the_bridge(self, tmp_path: Path) -> None:
        pack = tmp_path / "proj-pack"
        (pack / "drg").mkdir(parents=True)
        (pack / "agent_profiles").mkdir()
        (pack / "drg" / "fragment.yaml").write_text(
            "pack_name: proj-pack\n"
            "source_kind: local_path\n"
            "source_ref: proj-pack\n"
            "layer_index: 1\n"
            "provenance_marker: org\n"
            "nodes:\n"
            "  - id: my-analyst\n"
            "    kind: agent_profiles\n"
            "    title: My Analyst\n"
            "edges: []\n",
            encoding="utf-8",
        )
        (pack / "agent_profiles" / "my-analyst.agent.yaml").write_text("id: my-analyst\nspecializes_from: researcher-ryan\n", encoding="utf-8")

        fragment = load_org_pack("proj-pack", pack, 1)
        assert [(e.source, e.target) for e in fragment.edges] == [("agent_profile:my-analyst", "agent_profile:researcher-ryan")], (
            "precondition: the projection path emits URN-shaped endpoints"
        )

        built_in = _built_in()
        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                "specializes_from",
            )
        ]


# ---------------------------------------------------------------------------
# FR-011 — the documented snippet must produce an edge
# ---------------------------------------------------------------------------


def _claude_md_lineage_snippet() -> dict[str, Any]:
    """Extract the ``specializes_from`` YAML block from ``CLAUDE.md``.

    Reading the doc (rather than restating it) is what makes this test a
    guard: the snippet cannot drift back to an inert shape without going red.
    """
    text = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    heading = "### `specializes_from` DRG Lineage"
    assert heading in text, "the documented lineage section moved or was renamed"
    after = text.split(heading, 1)[1]
    match = re.search(r"```yaml\n(.*?)```", after, re.DOTALL)
    assert match is not None, "no YAML snippet follows the lineage heading"
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and parsed.get("edges"), f"the documented snippet is not an edges: block: {parsed!r}"
    return parsed


class TestDocumentedLineageSnippet:
    def test_the_claude_md_snippet_produces_an_edge(self) -> None:
        """US3 scenario 2 / SC-009 — a reader who follows the doc gets an edge.

        The shipped ``urn:profile:`` shape appears nowhere in the DRG
        vocabulary: ``urn`` is not a ``NodeKind``, so both endpoints failed to
        resolve and the edge was dropped in silence. Documentation that yields
        an inert declaration.
        """
        snippet = _claude_md_lineage_snippet()
        fragment = _fragment(
            [{"id": "my-analyst", "kind": "agent_profiles", "title": "My Analyst"}],
            snippet["edges"],
            pack_name="documented-pack",
        )

        built_in = _built_in()
        merged = merge_three_layers(built_in, [fragment], None)

        emitted = _org_edges(merged, built_in)
        assert emitted == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                Relation.SPECIALIZES_FROM.value,
            )
        ], f"the documented snippet must yield exactly this one edge, got {emitted}"

    def test_the_documented_endpoints_use_a_real_nodekind_prefix(self) -> None:
        """The narrow, fast guard against the exact retired shape."""
        snippet = _claude_md_lineage_snippet()
        kinds = {k.value for k in NodeKind}
        for edge in snippet["edges"]:
            for endpoint in (edge["source"], edge["target"]):
                prefix = endpoint.split(":", 1)[0]
                assert prefix in kinds, f"documented endpoint {endpoint!r} uses prefix {prefix!r}, which is not a NodeKind — the bridge cannot resolve it"


# ---------------------------------------------------------------------------
# One relationship must yield one edge — the dedup has to key on what the
# endpoints RESOLVE to, not on the strings the author happened to type.
# ---------------------------------------------------------------------------


def _overlap_pack(root: Path, *, authored_target: str) -> Path:
    """A pack in the migration-window overlap: one relationship, declared twice.

    ``my-analyst.agent.yaml`` still carries the legacy ``specializes_from:``
    field (the field-projection path emits ``agent_profile:my-analyst
    --specializes_from--> agent_profile:researcher-ryan``) AND the fragment
    hand-authors the same relationship in ``edges:``. This is exactly the
    overlap the loader's dedup was written for.
    """
    pack = root / "overlap-pack"
    (pack / "drg").mkdir(parents=True)
    (pack / "agent_profiles").mkdir()
    (pack / "drg" / "fragment.yaml").write_text(
        "pack_name: overlap-pack\n"
        "source_kind: local_path\n"
        "source_ref: overlap-pack\n"
        "layer_index: 1\n"
        "provenance_marker: org\n"
        "nodes:\n"
        "  - id: my-analyst\n"
        "    kind: agent_profiles\n"
        "    title: My Analyst\n"
        "edges:\n"
        "  - source: my-analyst\n"
        f"    target: {authored_target}\n"
        "    relation: specializes_from\n",
        encoding="utf-8",
    )
    (pack / "agent_profiles" / "my-analyst.agent.yaml").write_text(
        "id: my-analyst\nspecializes_from: researcher-ryan\n", encoding="utf-8"
    )
    return pack


def _lineage_overlap_pack(
    root: Path,
    name: str,
    *,
    project_field: bool,
    authored_reason: str | None,
    declare_node: bool,
) -> Path:
    """One side of the ``my-analyst --specializes_from--> researcher-ryan`` overlap.

    *project_field* writes the legacy ``specializes_from:`` artifact field, so
    the loader's projection path mints the edge with machine provenance.
    *authored_reason* hand-authors the same relationship in ``edges:``, with
    the operator's own rationale attached. Composing the two across packs lets
    a test choose which side survives the collapse.

    *declare_node* puts ``my-analyst`` in ``nodes:``. Exactly one pack needs
    it: without a node anywhere the endpoint dangles and the merge warns about
    that instead, which would mask the silence under test.
    """
    pack = root / name
    (pack / "drg").mkdir(parents=True)
    (pack / "agent_profiles").mkdir()
    nodes = (
        "nodes:\n  - id: my-analyst\n    kind: agent_profiles\n    title: My Analyst\n"
        if declare_node
        else "nodes: []\n"
    )
    if authored_reason is None:
        edges = "edges: []\n"
    else:
        edges = (
            "edges:\n"
            "  - source: agent_profile:my-analyst\n"
            "    target: agent_profile:researcher-ryan\n"
            "    relation: specializes_from\n"
            f"    reason: {authored_reason!r}\n"
        )
    (pack / "drg" / "fragment.yaml").write_text(
        f"pack_name: {name}\n"
        "source_kind: local_path\n"
        f"source_ref: {name}\n"
        "layer_index: 1\n"
        "provenance_marker: org\n" + nodes + edges,
        encoding="utf-8",
    )
    if project_field:
        (pack / "agent_profiles" / "my-analyst.agent.yaml").write_text(
            "id: my-analyst\nspecializes_from: researcher-ryan\n", encoding="utf-8"
        )
    return pack


class TestOneRelationshipYieldsOneEdge:
    """``load_org_pack``'s dedup keys on the RAW, pre-resolution endpoint
    strings. Once endpoint canonicalisation moved downstream of it, the bare and
    the qualified spelling of one relationship became two dedup keys that
    resolve to one triple — so the merged graph carries the edge twice.

    The loader structurally cannot fix this on its own: resolving a bare id that
    the fragment does not declare requires the BUILT-IN layer (rule 3 of
    :func:`_resolve_edge_endpoint`), which the loader never sees. Edge identity
    therefore belongs to the merge, after resolution — one authority, not a
    partial one at load time that looks complete.
    """

    @pytest.mark.parametrize(
        ("authored_target", "why"),
        [
            # The natural authoring shape, and the reviewer's repro: bare in
            # the fragment, qualified from the projection. Only resolvable
            # against the built-in layer -> undecidable at load time.
            ("researcher-ryan", "bare vs qualified spelling of one endpoint"),
            # Both spellings identical: decidable at load time too, so this
            # must stay collapsed no matter which layer owns the dedup.
            ("agent_profile:researcher-ryan", "byte-identical restatement"),
        ],
    )
    def test_the_migration_window_overlap_yields_one_edge(
        self, tmp_path: Path, authored_target: str, why: str
    ) -> None:
        fragment = load_org_pack(
            "overlap-pack", _overlap_pack(tmp_path, authored_target=authored_target), 1
        )

        built_in = _built_in()
        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                "specializes_from",
            )
        ], f"one relationship must yield one edge ({why})"
        assert _duplicate_edge_errors(merged) == []

    def test_two_packs_declaring_the_same_relationship_yield_one_edge(self) -> None:
        """Edge identity is the ``(source, target, relation)`` triple.

        The DRG validator already calls a repeated triple an error, so two packs
        that happen to declare the same relationship must collapse (first pack
        keeps provenance, mirroring org-vs-org node precedence) rather than
        produce a graph that fails its own integrity check.
        """
        def _pack(name: str) -> OrgDRGFragment:
            return _fragment(
                [{"id": "shared-node", "kind": "directives"}],
                [
                    {
                        "source": "shared-node",
                        "target": "directive:builtin-alpha",
                        "relation": "requires",
                    }
                ],
                pack_name=name,
            )

        built_in = _built_in()
        merged = merge_three_layers(built_in, [_pack("first"), _pack("second")], None)

        assert _org_edges(merged, built_in) == [
            ("directive:shared-node", "directive:builtin-alpha", "requires")
        ]
        assert _duplicate_edge_errors(merged) == []
        contributed = [e for e in merged.edges if str(e.provenance).startswith("org:")]
        assert [e.provenance for e in contributed] == ["org:first"], (
            "the first declaring pack keeps provenance, as it does for nodes"
        )

    def test_a_discarded_distinct_rationale_is_not_lost_in_silence(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Collapsing two AUTHORED rationales into one is information loss.

        The collapse itself is correct — one relationship, one edge — but the
        loser's ``reason:`` never reaches the graph, and before this the
        operator was never told. Two governance authors documenting the same
        relationship for different stated reasons, one silently discarded, is
        precisely the defect class this mission exists to close; the docstring's
        old defence (org-vs-org *node* collisions are equally silent) argues the
        node path is also wrong, not that this one is right.
        """
        def _pack(name: str, reason: str) -> OrgDRGFragment:
            return _fragment(
                [{"id": "shared-node", "kind": "directives"}],
                [
                    {
                        "source": "shared-node",
                        "target": "directive:builtin-alpha",
                        "relation": "requires",
                        "reason": reason,
                    }
                ],
                pack_name=name,
            )

        built_in = _built_in()
        with caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"):
            merged = merge_three_layers(
                built_in,
                [_pack("first", "SOX 404 evidence"), _pack("second", "GDPR Art. 30")],
                None,
            )

        assert _org_edges(merged, built_in) == [
            ("directive:shared-node", "directive:builtin-alpha", "requires")
        ], "the collapse itself is still correct"
        assert "GDPR Art. 30" in caplog.text, (
            f"the discarded rationale must be named; got {caplog.text!r}"
        )
        assert "org:second" in caplog.text, (
            f"the warning must name the pack whose reason was dropped; got {caplog.text!r}"
        )

    def test_one_pack_disagreeing_with_itself_is_named_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A pack can restate its own edge, and then there is only one pack.

        The cross-pack wording ("already contributed by ...", "reconcile the
        two packs") printed the same marker twice and sent the operator
        looking for a second pack that does not exist. The finding is real
        either way — one fragment, one relationship, two rationales, one
        survivor — so the message has to fit the shape it found.
        """
        fragment = _fragment(
            [{"id": "shared-node", "kind": "directives"}],
            [
                {
                    "source": "shared-node",
                    "target": "directive:builtin-alpha",
                    "relation": "requires",
                    "reason": reason,
                }
                for reason in ("SOX 404 evidence", "GDPR Art. 30")
            ],
            pack_name="solo",
        )

        built_in = _built_in()
        with caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"):
            merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            ("directive:shared-node", "directive:builtin-alpha", "requires")
        ]
        assert "GDPR Art. 30" in caplog.text, (
            f"the discarded rationale must be named; got {caplog.text!r}"
        )
        assert "already contributed by" not in caplog.text, (
            f"there is no second contributor to name; got {caplog.text!r}"
        )
        assert "two packs" not in caplog.text, (
            f"one pack must not be described as two; got {caplog.text!r}"
        )

    @pytest.mark.parametrize(
        ("first_reason", "second_reason", "why"),
        [
            (
                "SOX 404 evidence",
                "SOX 404 evidence",
                "identical rationales — nothing is lost by keeping one",
            ),
            (
                "SOX 404 evidence",
                None,
                "the restatement documented nothing, so nothing was discarded",
            ),
            (
                None,
                None,
                "the plain restatement: the sanctioned bare/qualified authoring shape",
            ),
        ],
    )
    def test_a_plain_restatement_collapses_without_a_warning(
        self,
        caplog: pytest.LogCaptureFixture,
        first_reason: str | None,
        second_reason: str | None,
        why: str,
    ) -> None:
        """The warning must discriminate, not fire on every dedup.

        Restating one relationship is *routine* and correct: a field projection
        and an explicit declaration, or a bare and a qualified spelling, are
        both sanctioned authoring shapes that collapse on every healthy merge.
        A warning that fired on those would be noise on correct packs — a gate
        that flags everything. Only a genuinely discarded rationale is loud.
        """
        def _pack(name: str, reason: str | None) -> OrgDRGFragment:
            edge: dict[str, str] = {
                "source": "shared-node",
                "target": "directive:builtin-alpha",
                "relation": "requires",
            }
            if reason is not None:
                edge["reason"] = reason
            return _fragment(
                [{"id": "shared-node", "kind": "directives"}],
                [edge],
                pack_name=name,
            )

        built_in = _built_in()
        with caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"):
            merged = merge_three_layers(
                built_in,
                [_pack("first", first_reason), _pack("second", second_reason)],
                None,
            )

        assert _org_edges(merged, built_in) == [
            ("directive:shared-node", "directive:builtin-alpha", "requires")
        ]
        assert "discard" not in caplog.text.lower(), (
            f"no rationale was lost ({why}); got {caplog.text!r}"
        )

    @pytest.mark.parametrize(
        ("packs", "why"),
        [
            (
                # The reviewer's exact repro: ONE pack, in the sanctioned
                # migration-window shape. The legacy field projects the edge;
                # the fragment declares the same relationship explicitly and
                # documents why. Fragment edges are collected first, so the
                # machine-minted projection is the one that gets discarded.
                [("acme-proj", True, "SOX 404 evidence")],
                "a machine-minted projection reason is not an author's words",
            ),
            (
                # The same overlap split across two packs so the ORDER flips:
                # the projection lands first and survives, the hand-authored
                # reason is the one discarded. Still quiet — the survivor
                # documented nothing, so there is no rationale to reconcile
                # it against (the mirror of the one-side-silent case above).
                [("acme-legacy", True, None), ("acme-authored", False, "SOX 404 evidence")],
                "a projection surviving an authored reason is still not two authors disagreeing",
            ),
        ],
    )
    def test_a_generated_projection_reason_never_warns(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        packs: list[tuple[str, bool, str | None]],
        why: str,
    ) -> None:
        """A field projection colliding with an authored edge is HEALTHY.

        ``org_pack_loader._projection_edges_for_file`` stamps every projection
        edge with machine-generated provenance. Reading "has a reason" as "an
        author wrote a reason" therefore made the warning fire on the exact
        transitional shape the loader's retained projection path exists to
        support — a documented ``enhances:``/``specializes_from:`` field plus
        the explicit fragment edge that will replace it.

        Nothing an author wrote is lost here: the machine's boilerplate is not
        a rationale, and the remedy the warning proposes (mint a second
        relationship) is the opposite of the right one (delete the legacy
        field). A warning that fires on healthy merges is worse than the
        silence it replaces, so this shape must stay quiet.
        """
        fragments = [
            load_org_pack(
                name,
                _lineage_overlap_pack(
                    tmp_path,
                    name,
                    project_field=project_field,
                    authored_reason=authored_reason,
                    declare_node=index == 0,
                ),
                index + 1,
            )
            for index, (name, project_field, authored_reason) in enumerate(packs)
        ]

        built_in = _built_in()
        with caplog.at_level(logging.WARNING, logger="charter.offering.drg.merge"):
            merged = merge_three_layers(built_in, fragments, None)

        assert _org_edges(merged, built_in) == [
            (
                "agent_profile:my-analyst",
                "agent_profile:researcher-ryan",
                "specializes_from",
            )
        ], "the collapse itself is still correct"
        assert caplog.records == [], (
            f"a healthy migration-window pack must merge in silence ({why}); "
            f"got {caplog.text!r}"
        )

    def test_distinct_relationships_are_not_collapsed(self) -> None:
        """The dedup must key on the whole triple, not a prefix of it."""
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "mine", "kind": "directives"}],
            [
                {
                    "source": "mine",
                    "target": "directive:builtin-alpha",
                    "relation": "requires",
                },
                {
                    "source": "mine",
                    "target": "directive:builtin-alpha",
                    "relation": "suggests",
                },
                {
                    "source": "mine",
                    "target": "styleguide:caveman-comments",
                    "relation": "requires",
                },
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        assert sorted(_org_edges(merged, built_in)) == [
            ("directive:mine", "directive:builtin-alpha", "requires"),
            ("directive:mine", "directive:builtin-alpha", "suggests"),
            ("directive:mine", "styleguide:caveman-comments", "requires"),
        ]


# ---------------------------------------------------------------------------
# The deferral has to be collected — a qualified endpoint is only accepted
# verbatim because a LATER layer may still supply the node, and nothing was
# re-checking once every layer was in.
# ---------------------------------------------------------------------------


class TestQualifiedEndpointsAreCheckedOnceEveryLayerIsIn:
    """:func:`_resolve_edge_endpoint` accepts a fully-qualified endpoint without
    proving it exists, on the stated grounds that existence "belongs to the DRG
    validator, not the URN minter". The reasoning is right and the deferral is
    sound — but the control it defers to has to actually run somewhere, and it
    did not: no production caller of :func:`merge_three_layers`
    (``_doctrine_collect``, ``charter.lint``, ``_profile_health_render``,
    ``charter._status_collectors``) called
    :func:`charter.offering.drg.validator.validate_graph` or ``assert_valid``. Measured
    consequence: a one-character typo in a qualified endpoint merged clean.

    ``merge_three_layers`` assembles all three layers, so by the time it
    returns there IS no later layer — it is the first point at which existence
    is knowable and the last point that still knows which pack authored the
    token. The re-check therefore lands here, and reports through the bridge's
    own :class:`OrgDRGConflict` vocabulary rather than a second error channel.
    """

    def test_a_typo_in_a_qualified_endpoint_does_not_land_unwarned(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The measured hole: ``builtin-alpha`` mistyped as ``builtin-alfa``.

        Before this fix the merge returned a graph carrying
        ``directive:mine --requires--> directive:builtin-alfa`` — an endpoint
        naming nothing, which every downstream traversal silently fails to
        follow — and said nothing at all.

        The merge WARNs rather than refusing: it cannot distinguish this typo
        from a legitimate reference into a sibling pack the caller did not load
        (``charter lint`` merges org fragments against an EMPTY built-in graph
        on purpose). Escalation to an error belongs to the caller that holds a
        complete graph — see the ``doctor charter-packs`` coverage.
        """
        fragment = _fragment(
            [{"id": "mine", "kind": "directives"}],
            [
                {
                    "source": "mine",
                    "target": "directive:builtin-alfa",
                    "relation": "requires",
                }
            ],
        )

        with caplog.at_level("WARNING", logger="charter.offering.drg.merge"):
            merge_three_layers(_built_in(), [fragment], None)

        warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("directive:builtin-alfa" in w for w in warnings), (
            "a qualified endpoint that binds to nothing must name the offending "
            f"token so the pack author can find it; got {warnings}"
        )
        assert any("org:probe-pack" in w for w in warnings), (
            "...and must name the pack to go fix"
        )

    def test_a_resolvable_endpoint_produces_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The warning must discriminate, or operators learn to ignore it."""
        fragment = _fragment(
            [{"id": "sox-controls", "kind": "directives"}],
            [
                {
                    "source": "sox-controls",
                    "target": "agent_profile:researcher-ryan",
                    "relation": "requires",
                },
                {
                    "source": "sox-controls",
                    "target": "caveman-comments",
                    "relation": "refines",
                },
            ],
        )

        with caplog.at_level("WARNING", logger="charter.offering.drg.merge"):
            merged = merge_three_layers(_built_in(), [fragment], None)

        assert [r.getMessage() for r in caplog.records if r.levelname == "WARNING"] == []
        assert validate_dangling_references(merged) == []

    def test_the_named_compensating_control_is_reachable_and_agrees(self) -> None:
        """Executable form of the docstring's claim.

        The bridge defers existence to :mod:`charter.offering.drg.validator`. That
        deferral only means anything if the check is (a) reachable as a public
        canonical function rather than a private helper each caller must
        re-implement, and (b) in agreement with what the merge warned about.
        """
        built_in = _built_in()
        fragment = _fragment(
            [{"id": "mine", "kind": "directives"}],
            [
                {
                    "source": "mine",
                    "target": "directive:builtin-alfa",
                    "relation": "requires",
                }
            ],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        errors = validate_dangling_references(merged)
        assert len(errors) == 1, errors
        assert "Dangling target" in errors[0]
        assert "directive:builtin-alfa" in errors[0]

    def test_the_shipped_built_in_graph_is_a_clean_baseline(self) -> None:
        """The post-assembly check is only affordable because the shipped graph
        is already clean — measured, not assumed."""
        from charter.drg import load_built_in_graph
        from charter.offering.drg.validator import validate_graph

        built_in = load_built_in_graph()
        assert validate_graph(merge_three_layers(built_in, [], None)) == []

    def test_a_cross_pack_reference_is_warned_but_not_refused(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Why the merge reports instead of refusing.

        The in-repo ``example_org`` fixture demonstrates the sanctioned
        cross-pack authoring shape: a fully-qualified reference to a node
        shipped by a *sibling* pack. Refusing every unbindable qualified
        endpoint would make that documented pattern un-loadable whenever the
        sibling pack is not configured — and would break ``charter lint``,
        which merges org fragments against an EMPTY built-in graph by design.
        The edge survives; the operator is told.
        """
        fragment = _fragment(
            [{"id": "sox-controls", "kind": "directives"}],
            [
                {
                    "source": "sox-controls",
                    "target": "styleguide:from-a-pack-i-did-not-configure",
                    "relation": "refines",
                }
            ],
        )

        built_in = _built_in()
        with caplog.at_level("WARNING", logger="charter.offering.drg.merge"):
            merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [
            (
                "directive:sox-controls",
                "styleguide:from-a-pack-i-did-not-configure",
                "refines",
            )
        ]
        assert any(
            "from-a-pack-i-did-not-configure" in r.getMessage()
            for r in caplog.records
        )

    def test_a_qualified_endpoint_may_still_name_a_later_layers_node(self) -> None:
        """The deferral must survive — this is WHY mint-time existence is wrong.

        An org pack legitimately references a node the PROJECT layer supplies.
        The project layer is merged after the org layer, so this only resolves
        post-assembly. A check that ran at mint time would reject it.
        """
        project = _graph(DRGNode(urn="directive:from-project", kind=NodeKind.DIRECTIVE))
        fragment = _fragment(
            [{"id": "mine", "kind": "directives"}],
            [
                {
                    "source": "mine",
                    "target": "directive:from-project",
                    "relation": "requires",
                }
            ],
        )

        built_in = _built_in()
        merged = merge_three_layers(built_in, [fragment], project)

        assert (
            "directive:mine",
            "directive:from-project",
            "requires",
        ) in _org_edges(merged, built_in)

    def test_the_post_assembly_check_would_catch_a_reintroduced_hole(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Self-mutation (standing order 5): prove the check is load-bearing.

        Neuter the post-assembly detector and assert the typo goes back to
        landing in silence — i.e. the warning above comes from this check, not
        from something incidental elsewhere in the merge.
        """
        import charter.offering.drg.merge as merge_mod

        monkeypatch.setattr(
            merge_mod,
            "_dangling_org_endpoints",
            lambda contributions, merged_nodes: [],
            raising=True,
        )

        fragment = _fragment(
            [{"id": "mine", "kind": "directives"}],
            [
                {
                    "source": "mine",
                    "target": "directive:builtin-alfa",
                    "relation": "requires",
                }
            ],
        )
        built_in = _built_in()
        with caplog.at_level("WARNING", logger="charter.offering.drg.merge"):
            merged = merge_three_layers(built_in, [fragment], None)

        assert ("directive:mine", "directive:builtin-alfa", "requires") in _org_edges(
            merged, built_in
        )
        assert [r.getMessage() for r in caplog.records if r.levelname == "WARNING"] == [], (
            "the mutation must restore the silence, otherwise the check is decorative"
        )


# ---------------------------------------------------------------------------
# Regression floor for the resolution policy itself
# ---------------------------------------------------------------------------


class TestResolutionPrecedence:
    def test_bare_resolution_does_not_depend_on_pack_declaration_order(
        self,
    ) -> None:
        """Rule 3 reads the built-in layer only, never the running merge.

        If a bare id could bind to an *earlier fragment's* node, whether a
        pack's edge resolved would depend on the operator's
        ``charter_packs.org.packs`` ordering — an order-dependent graph is a
        silent-difference generator of the same family this mission closes.
        Both orderings must produce the same verdict.
        """
        provider = _fragment(
            [{"id": "provided", "kind": "directives"}],
            [],
            pack_name="provider-pack",
        )
        consumer = _fragment(
            [{"id": "consumer-node", "kind": "directives"}],
            [
                {
                    "source": "consumer-node",
                    "target": "provided",
                    "relation": "requires",
                }
            ],
            pack_name="consumer-pack",
        )

        verdicts = []
        for order in ([provider, consumer], [consumer, provider]):
            with pytest.raises(OrgDRGConflictError) as excinfo:
                merge_three_layers(_graph(), order, None)
            verdicts.append([c.kind for c in excinfo.value.conflicts])

        assert verdicts[0] == verdicts[1] == ["unresolved_edge_endpoint"], (
            "a cross-pack bare reference must be refused identically in both "
            f"declaration orders; got {verdicts}"
        )

    def test_fragment_local_id_wins_over_a_same_named_builtin(self) -> None:
        """A pack's own node is the nearest scope for a bare id it declared."""
        built_in = _graph(DRGNode(urn="tactic:shared", kind=NodeKind.TACTIC))
        fragment = _fragment(
            [
                {"id": "shared", "kind": "directives"},
                {"id": "other", "kind": "directives"},
            ],
            [{"source": "other", "target": "shared", "relation": "requires"}],
        )

        merged = merge_three_layers(built_in, [fragment], None)

        assert _org_edges(merged, built_in) == [("directive:other", "directive:shared", "requires")]

    def test_every_unresolvable_endpoint_is_reported_not_just_the_first(
        self,
    ) -> None:
        """Re-anchored by the WP08 fold — this was the weakest of the 20 reds.

        It used to call ``bridge_org_edge_to_drg_edge`` positionally and went
        red with ``TypeError: takes 3 positional arguments but 4 were given``.
        That is an ARITY red, not a behaviour red: it pinned a private helper's
        signature, so it would have false-flagged any refactor of that seam
        while proving nothing an operator can observe.

        Re-pointed at the contract that actually matters and was NOT covered:
        conflict reporting is per-endpoint, so a pack with several bad tokens
        is told about all of them in one pass. Failing on the first would make
        fixing a pack an N-round guessing game — a slower shape of the same
        "you are not told what is wrong" problem this WP exists to close.
        """
        fragment = _fragment(
            [{"id": "a", "kind": "directives"}],
            [
                {"source": "a", "target": "ghost-one", "relation": "requires"},
                {"source": "ghost-two", "target": "a", "relation": "requires"},
                {"source": "a", "target": "nosuchkind:ghost-three", "relation": "requires"},
            ],
        )

        with pytest.raises(OrgDRGConflictError) as excinfo:
            merge_three_layers(_built_in(), [fragment], None)

        assert sorted(c.target_id for c in excinfo.value.conflicts) == [
            "ghost-one",
            "ghost-two",
            "nosuchkind:ghost-three",
        ]
        message = str(excinfo.value)
        for token in ("ghost-one", "ghost-two", "nosuchkind:ghost-three"):
            assert token in message, f"{token!r} missing from the operator message"
