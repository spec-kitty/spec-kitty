"""Per-channel reachability as asserted named sets (WP08, contract §3 R-1..R-6).

Reachability is a **membership** contract, not a cardinality one: a newly
unreachable activated artefact fails a set-equality naming *itself*, where a
count could only nudge an integer. The two channels are measured by two
different traversals, both **called** from :mod:`charter.offering.drg.reachability` (no
walk is reimplemented here):

* **action channel** — :func:`action_channel_reachable`, which calls
  :func:`charter.offering.drg.query.resolve_context`. Pinned at ``d=1`` (compact, the
  steady state, the stricter measure) and ``d=2`` (bootstrap); the family
  tests below name the members reached at ``d=2`` only (R-2).
* **profile channel** — :func:`profile_channel_reachable`, a distinct
  ``walk_edges`` over ``{requires, specializes_from}``. Seeding profiles into
  ``resolve_context`` instead would measure zero (R-3), a fact this module pins
  directly.

The pinned membership sets are the per-family wiring sets below; the
whole-graph action-unreachable set is asserted live (totality and disjointness)
by the companion guard, never as a frozen literal.

FR-014 (mission ``charter-pack-cutover-01M491G6``, #5323 item 2)
-----------------------------------------------------------------
The activation-store pins of this module were not asserted by any test and
had drifted. They were measured with the canonical helpers against the
``default`` preset (no per-kind activation keys in this repository, so every
built-in artefact is in force: 205 activated node URNs in a 354-node graph)
and deleted, because each one only meant something while the activation store
filtered the built-in set. Re-asserted pins: none. The family sets
(``_COMMON_DOCS_WIRED``, ``_DDD_FAMILY_WIRED``, ``_TESTING_*``,
``_WIRED_THIS_MISSION``) are unchanged and asserted by their own tests; the
ledger comments next to them cite the deleted pins as history. The wiring
ledger lives in ``docs/plans/doctrine/delivery-reachability-wiring-table.md``.

Deleted pins (FR-014)
- ``_ACTION_UNREACHABLE_D1``: activated artefacts the action channel misses at d=1; no
  assertion read it, it drifted (pin 75, measured 72: 3 entered, 6 left), and
  "activated-only" means "every built-in" under the default preset, so the live
  companion-guard partition already covers it.
- ``_ACTION_UNREACHABLE_D2``: same, at d=2; unasserted, drifted (pin 54, measured 52: 2
  entered, 4 left).
- ``_PROFILE_UNREACHABLE``: activated artefacts the profile channel misses; unasserted,
  drifted (pin 56, measured 54: 2 entered, 4 left).
- ``_PROFILE_RESCUES``: ``_ACTION_UNREACHABLE_D2 - _PROFILE_UNREACHABLE``; unasserted,
  drifted (pin 26, measured 25), and its ledger cross-check had already been removed.
- ``_ACTION_D1_D2_SPREAD``: the size of the d=1/d=2 difference of the two sets above;
  unasserted, drifted (pin 23, measured 20); the d=2-only members that matter are pinned
  by the family tests.
- ``_NORMALIZATION_DELTA``: the store-form vs node-form slug swing of the activation
  store (C-009); with no per-kind activation lists there is no store form to normalise,
  so it measures nothing.
- helpers ``_activated``, ``_raw_activated_map``, ``_profile_channel_ledger_text``:
  used only by the deleted pins and their removed tests (with the latter's two section
  constants).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, NodeKind, Relation
from charter.offering.drg.query import resolve_context
from charter.offering.drg.reachability import (
    PROFILE_CHANNEL_RELATIONS,
    action_channel_reachable,
    action_seed_urns,
    agent_profile_seed_urns,
    profile_channel_reachable,
)
from reachability_fixtures.nominal_wiring import (
    ACTION_URN,
    IN_SCOPE_DIRECTIVE,
    NOMINALLY_WIRED,
    PROPERLY_WIRED,
    UNREACHABLE_SOURCE,
    incident_urns,
    nominal_wiring_graph,
)

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

#: Repo root — tests/charter_offering/drg/ is three levels down.
_REPO_ROOT: Path = Path(__file__).resolve().parents[3]

#: ``resolve_context`` depths: compact (stricter) and bootstrap.
_ACTION_D1_DEPTH = 1
_ACTION_D2_DEPTH = 2

#: The common-docs cluster WP09 wires (mission doctrine-delivery-reachability,
#: T050, FR-015). One authored `scope` edge —
#: ``action:documentation/generate --scope--> directive:DIRECTIVE_042`` — makes
#: DIRECTIVE_042 action-reachable, and 042's pre-existing ``requires``/``suggests``
#: edges then deliver the asset, the styleguide and the four common-docs tactics
#: transitively. These six leave BOTH ``_ACTION_UNREACHABLE_D1`` and
#: ``_ACTION_UNREACHABLE_D2`` (NFR-004 ledger row: the two golden membership sets
#: each shrink by exactly these six; the d1<->d2 spread stays 7 because the same
#: members leave both, and ``_PROFILE_UNREACHABLE`` / ``_PROFILE_RESCUES`` are
#: unaffected — the profile channel is unchanged and all six are profile-
#: unreachable too). The edge's source is an ``action`` node, so it satisfies
#: C-007(b)'s second clause without needing its own reachability measured, and
#: 042's ``scope:`` text ("whenever a documentation file ... is created") attests
#: the relationship to ``documentation/generate``'s ``write_docs`` step (C-007a).
#: ``asset:common-docs-structural-lint`` is delivered but not itself activated, so
#: it is proven reachable directly rather than via the activated-set subtraction.
_COMMON_DOCS_WIRED: frozenset[str] = frozenset(
    {
        "directive:DIRECTIVE_042",
        "styleguide:common-docs",
        "tactic:common-docs-find",
        "tactic:common-docs-scaffold",
        "tactic:common-docs-write",
    }
)

#: The delivery target the wired cluster exists to reach (WP10/WP11 ship assets).
_COMMON_DOCS_ASSET = "asset:common-docs-structural-lint"

#: The DDD family #3063 family-A wires (operator interview outcome, C-007(a)
#: satisfied by operator ruling). One authored ``scope`` edge —
#: ``action:software-dev/specify --scope--> paradigm:domain-driven-design`` —
#: makes the DDD paradigm action-reachable, and the paradigm's ten authored
#: ``requires`` edges (to the strategic-design + tactical DDD members whose own
#: text attests DDD membership) then deliver the family transitively. Every
#: member here becomes action-reachable at BOTH depths after the edge lands;
#: ``tactic:strategic-domain-classification`` was already action-reachable
#: (via ``tactic:paula-patterns-architecture-scout-review``), so it is delivered
#: too but leaves neither ``_ACTION_UNREACHABLE`` set. NOTE the specify edge is
#: ``scope`` NOT ``suggests``: measured with the WP08 helper, a ``suggests`` edge
#: whose SOURCE is an action node is inert — ``resolve_context`` walks ``suggests``
#: only FROM scope-resolved artifacts, never from the action node — so only a
#: ``scope`` edge changes action reachability (the WP09 precedent,
#: ``action:documentation/generate --scope--> directive:DIRECTIVE_042``).
#:
#: NFR-004 ledger for this move: ``_ACTION_UNREACHABLE_D1`` and
#: ``_ACTION_UNREACHABLE_D2`` each lose the SAME twelve members —
#: ``paradigm:domain-driven-design``; its two pre-existing ``directive_refs``
#: ``DIRECTIVE_031``/``DIRECTIVE_032`` (delivered once the paradigm is scoped);
#: and the nine newly-required members that were unreachable
#: (``styleguide:aggregate-design-rules`` + the eight DDD tactics minus
#: ``strategic-domain-classification``, which was already reachable). Because the
#: same twelve leave both, the d1<->d2 spread stays 7. ``_PROFILE_UNREACHABLE`` is
#: unchanged (the profile channel is untouched: the three profile edges are
#: ``suggests``, which that channel does not follow, and the DDD paradigm stays
#: profile-unreachable so its new ``requires`` edges deliver nothing there —
#: measured 39->39). ``_PROFILE_RESCUES`` (defined as
#: ``_ACTION_UNREACHABLE_D2 - _PROFILE_UNREACHABLE``) therefore loses the four of
#: its members that just entered the action channel: ``DIRECTIVE_031``,
#: ``DIRECTIVE_032``, ``anti-corruption-layer`` and ``domain-event-capture`` — the
#: action channel now covers them, so they are no longer profile-only rescues.
#: Orphan sets are unaffected (every endpoint was already edge-incident).
_DDD_FAMILY_WIRED: frozenset[str] = frozenset(
    {
        "paradigm:domain-driven-design",
        "tactic:bounded-context-identification",
        "tactic:context-mapping-classification",
        "tactic:context-boundary-inference",
        "tactic:bounded-context-canvas-fill",
        "tactic:aggregate-boundary-design",
        "tactic:entity-value-object-classification",
        "tactic:domain-event-capture",
        "tactic:anti-corruption-layer",
        "tactic:strategic-domain-classification",
        "styleguide:aggregate-design-rules",
    }
)

#: The TESTING / BDD / MUTATION family #3063 family-D delivers (operator interview
#: outcome + ACCEPT-DELIVERY ruling 2026-07-29). Unlike families B/C, family D is
#: reachability-affecting: two hubs are EXISTING action-scoped directives, so their
#: outbound ``suggests`` edges ARE walked and DELIVER at implement/review.
#: ``directive:DIRECTIVE_034`` (test-first) and ``directive:DIRECTIVE_030`` (test-
#: quality gate) are both ``scope``-linked from ``action:software-dev/implement``
#: and ``action:software-dev/review``; ``resolve_context`` step 3 walks ``suggests``
#: from those scope-resolved artifacts.
#:
#: Delivered at BOTH d=1 and d=2 (leave both ``_ACTION_UNREACHABLE`` sets) — five
#: from DIRECTIVE_034 (development-bdd, atdd-adversarial-acceptance,
#: specification-by-example, formalized-constraint-testing, example-mapping-
#: workshop) and two from DIRECTIVE_030 (adversarial-qa-handoff,
#: work-package-completion-validation):
_TESTING_DELIVERED_AT_D1: frozenset[str] = frozenset(
    {
        "tactic:development-bdd",
        "tactic:atdd-adversarial-acceptance",
        "paradigm:specification-by-example",
        "tactic:formalized-constraint-testing",
        "procedure:example-mapping-workshop",
        "tactic:adversarial-qa-handoff",
        "tactic:work-package-completion-validation",
    }
)

#: Delivered at the bootstrap depth d=2 ONLY (leave ``_ACTION_UNREACHABLE_D2`` but
#: NOT ``_ACTION_UNREACHABLE_D1``; they move into the d1<->d2 spread):
#: ``reverse-speccing`` / ``test-to-system-reconstruction`` via the
#: ``paradigm:brownfield-onboarding`` suggests chain, and
#: ``styleguide:mutation-aware-test-design`` via a 2-hop suggests chain out of the
#: action-scoped DIRECTIVE_030.
_TESTING_DELIVERED_AT_D2_ONLY: frozenset[str] = frozenset(
    {
        "tactic:reverse-speccing",
        "tactic:test-to-system-reconstruction",
        "styleguide:mutation-aware-test-design",
    }
)

#: Every artefact family-D makes action-reachable (the union). The BDD + test-
#: quality members action-reachable at implement/review — the acceptance target of
#: the ACCEPT-DELIVERY ruling. The mutation hub (a NEW non-scoped directive) and the
#: DIRECTIVE_041 fan-out stay UNREACHABLE (their members remain in the deferred set);
#: the profile->hub and event-storming edges are ``suggests`` on the profile channel
#: and inert. ``_PROFILE_UNREACHABLE`` is unchanged (153); ``_PROFILE_RESCUES``
#: 4 -> 2 because development-bdd and reverse-speccing entered the action channel.
_TESTING_BDD_MUTATION_WIRED: frozenset[str] = (
    _TESTING_DELIVERED_AT_D1 | _TESTING_DELIVERED_AT_D2_ONLY
)

#: #3063 family-E (ANALYSIS / TERMINOLOGY / REASONS-CANVAS family) is INERT --
#: it moves NO reachability pin (measured with the WP08 helper, not assumed). Its
#: nine overlay ``suggests`` edges all originate at either
#: ``agent_profile:architect-alphonso`` (the profile channel walks {requires,
#: specializes_from} only, so profile--suggests-->X is never followed) or an
#: action-UNREACHABLE tactic/toolguide (``terminology-extraction-mapping``,
#: ``contextive``, ``terminology-guard`` are all pinned in
#: ``_ACTION_UNREACHABLE_D1``/``D2`` below, and ``resolve_context`` walks
#: ``suggests`` only FROM scope-resolved artifacts). The two reinforcement edges
#: point INTO the already-action-reachable DDD / brownfield paradigms, which does
#: not make their source reachable. So ``_ACTION_UNREACHABLE_D1``/``D2``,
#: ``_PROFILE_UNREACHABLE`` and ``_PROFILE_RESCUES`` are all UNCHANGED by family E
#: (composition-only: +9 ``suggests`` edges, 0 new artefacts). The delivery-
#: reachability DEFERRED set stays at 50 -- no artefact leaves it. See
#: ``docs/plans/doctrine/delivery-reachability-wiring-table.md`` (Family E).

@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    return load_built_in_graph()


@pytest.mark.doctrine
class TestActionChannelReachability:
    """The action channel is measured by CALLING ``resolve_context`` (R-1)."""

    def test_action_helper_calls_resolve_context_not_a_reimplemented_walk(
        self, graph: DRGGraph
    ) -> None:
        """Union over action seeds equals the per-seed ``resolve_context`` union.

        If the helper reimplemented the walk, this equality against a direct
        ``resolve_context`` union would be the first thing to drift.
        """
        seeds = action_seed_urns(graph)
        assert seeds, "the shipped graph must carry action nodes to seed from"
        direct: set[str] = set()
        for seed in seeds:
            direct |= resolve_context(graph, seed, depth=_ACTION_D1_DEPTH).artifact_urns
        assert action_channel_reachable(graph, seeds, _ACTION_D1_DEPTH) == frozenset(direct)




    def test_common_docs_cluster_and_asset_are_action_reachable(self, graph: DRGGraph) -> None:
        """FR-015 / WP09 acceptance (spec User Story 4, scenario 3): every wired
        artefact is action-reachable AFTER landing, not merely edge-incident.

        The whole common-docs cluster was a strongly-connected island no action
        scoped — measured unreachable at d=1 and d=2 before WP09. The single
        authored ``scope`` edge from ``documentation/generate`` to DIRECTIVE_042
        must make all six activated members AND the delivered asset reachable at
        BOTH depths. Measured by CALLING the WP08 helper (R-1); if any member
        were only edge-incident to an unreachable source (the PR #3007 failure),
        it would be absent from this set and this test would name it.
        """
        for depth in (_ACTION_D1_DEPTH, _ACTION_D2_DEPTH):
            reachable = action_channel_reachable(graph, action_seed_urns(graph), depth)
            missing = sorted((_COMMON_DOCS_WIRED | {_COMMON_DOCS_ASSET}) - reachable)
            assert not missing, (
                f"wired common-docs artefacts still unreachable at d={depth} "
                f"(wired to an unreachable source, or the scope edge is absent): "
                f"{missing}"
            )

    def test_ddd_family_is_action_reachable_at_specify_grain(
        self, graph: DRGGraph
    ) -> None:
        """#3063 family-A acceptance (operator interview outcome): the specify
        grain must reach the DDD paradigm and its strategic-design family.

        The whole DDD family was a set of activated artefacts no action scoped —
        measured unreachable at d=1 and d=2 before this edge. The single authored
        ``scope`` edge from ``software-dev/specify`` to
        ``paradigm:domain-driven-design`` makes the paradigm action-reachable, and
        its authored ``requires`` edges deliver the members transitively. Measured
        by CALLING the WP08 helper (R-1); if any member were only edge-incident to
        an unreachable source (the PR #3007 failure), it would be absent here and
        this test would name it. Red before the edge lands, green after.
        """
        for depth in (_ACTION_D1_DEPTH, _ACTION_D2_DEPTH):
            reachable = action_channel_reachable(graph, action_seed_urns(graph), depth)
            missing = sorted(_DDD_FAMILY_WIRED - reachable)
            assert not missing, (
                f"DDD family still unreachable at d={depth} "
                f"(paradigm not scoped by an action, or a member is wired only to "
                f"an unreachable source): {missing}"
            )

    def test_testing_bdd_family_is_action_reachable_at_implement_review(
        self, graph: DRGGraph
    ) -> None:
        """#3063 family-D acceptance (operator ACCEPT-DELIVERY ruling): the BDD +
        test-quality members must be action-reachable at implement/review.

        Unlike families B/C, family D delivers, because ``directive:DIRECTIVE_034``
        (test-first) and ``directive:DIRECTIVE_030`` (test-quality gate) are already
        ``scope``-linked from ``action:software-dev/implement`` and
        ``action:software-dev/review``. ``resolve_context`` step 3 walks
        ``suggests`` from those scope-resolved artifacts, so the authored
        ``suggests`` edges deliver their targets. Measured by CALLING the WP08
        helper (R-1): the seven core members must be reachable at BOTH the compact
        (d=1) and bootstrap (d=2) depths; the three brownfield/2-hop members are
        reached at the bootstrap depth only. Red before the edges land, green after.
        """
        r_d1 = action_channel_reachable(graph, action_seed_urns(graph), _ACTION_D1_DEPTH)
        missing_d1 = sorted(_TESTING_DELIVERED_AT_D1 - r_d1)
        assert not missing_d1, (
            "BDD + test-quality members still unreachable at d=1 "
            f"(a hub is not action-scoped, or an edge is absent): {missing_d1}"
        )

        r_d2 = action_channel_reachable(graph, action_seed_urns(graph), _ACTION_D2_DEPTH)
        missing_d2 = sorted(_TESTING_BDD_MUTATION_WIRED - r_d2)
        assert not missing_d2, (
            "family-D delivered members still unreachable at d=2: "
            f"{missing_d2}"
        )
        # The DIRECTIVE_041 fan-out is INERT by design: its members stay
        # unreachable. Guards against a future edit that accidentally makes
        # that family eager.
        #
        # ``tactic:mutation-testing-workflow`` WAS inert here too (the mutation
        # hub was a non-scoped directive with no inbound edge), but mission
        # drg-reachability-metric-wiring-01KZS5VR (WP01, #3009 point 3) wires
        # ``directive:DIRECTIVE_030 --suggests--> USE_MUTATION_TESTING_TO_
        # VALIDATE_TEST_QUALITY`` (DIRECTIVE_030 IS action-scoped at
        # implement/review), which cascades the mutation hub's own pre-existing
        # ``suggests`` edges into d=2 action reach. That is this mission's
        # intended delivery (see ``_WIRED_THIS_MISSION``), not a regression —
        # the assertion below now pins the opposite of the old one.
        assert "tactic:mutation-testing-workflow" in r_d2
        # Quad-A is delivered at the bootstrap depth because testing-principles
        # names it by id (the inline copy was trimmed); it is not a d=1 member.
        assert "styleguide:quadruple-a-test-format" in r_d2
        assert "styleguide:quadruple-a-test-format" not in r_d1


@pytest.mark.doctrine
class TestProfileChannelReachability:
    """The profile channel is a SEPARATE ``walk_edges`` traversal (R-3)."""

    def test_profile_relations_are_requires_and_specializes_from(self) -> None:
        """The channel follows lineage + hard-dependency + soft-recommendation
        edges — and crucially NOT ``scope``, the relation ``resolve_context``
        seeds on. That absence is why the two channels cannot be folded (R-3).

        ``suggests`` joins the set in mission
        ``doctrine-delivery-activation-01KYQVQK`` (WP01/FR-001): the profile
        channel now delivers the #3063 A–E families that were authored inert.
        """
        assert {r.value for r in PROFILE_CHANNEL_RELATIONS} == {
            "requires",
            "specializes_from",
            "suggests",
        }
        assert Relation.SCOPE not in PROFILE_CHANNEL_RELATIONS

    def test_resolve_context_from_a_profile_reaches_nothing(self, graph: DRGGraph) -> None:
        """The reason the profile channel is not a ``resolve_context`` seed set.

        ``resolve_context`` step 1 walks ``scope`` only, and profiles carry zero
        outbound ``scope``, so seeding a profile into it returns 0 artefacts at
        every depth — folding the channels would silently measure nothing.
        """
        for seed in agent_profile_seed_urns(graph):
            for depth in (_ACTION_D1_DEPTH, _ACTION_D2_DEPTH):
                assert resolve_context(graph, seed, depth=depth).artifact_urns == frozenset()

    def test_profile_channel_is_fail_closed_on_empty_configuration(
        self, graph: DRGGraph
    ) -> None:
        """``profile: str | None`` — an unconfigured caller reaches NOTHING, not
        the whole graph (R-3b: it must not repeat the fail-open shape FR-018
        retires)."""
        assert profile_channel_reachable(graph, frozenset()) == frozenset()




@pytest.mark.doctrine
class TestSixEdgesReachabilityWiring:
    """T003 (WP01, mission drg-reachability-metric-wiring-01KZS5VR, #3009 point 3).

    Behavioral, red-first reach assertions for the six curated edges
    (``_CURATED_ARTIFACT_EDGES``, ``src/charter/offering/drg/migration/extractor.py``) —
    each proves a reachability TRANSITION via the canonical helpers, not a
    frozenset-literal edit (the real ATDD artifact per the contract's
    anti-requirements: set-equality alone does not force these edges to exist).
    """

    def test_disciplined_refactoring_is_action_reachable_via_refactoring_procedure(
        self, graph: DRGGraph
    ) -> None:
        """Edge 1: ``procedure:refactoring --suggests--> DISCIPLINED_REFACTORING``.

        Was action-unreachable before this mission (see
        ``_ACTION_UNREACHABLE_D1``/``D2``'s WP01 note); the already action-scoped
        refactoring procedure now suggests it.
        """
        reach = action_channel_reachable(graph, action_seed_urns(graph), _ACTION_D2_DEPTH)
        assert "directive:DISCIPLINED_REFACTORING" in reach

    def test_reconcile_change_scope_tensions_is_action_reachable_via_024_and_025(
        self, graph: DRGGraph
    ) -> None:
        """Edges 2/3: ``DIRECTIVE_024``/``DIRECTIVE_025 --suggests--> RECONCILE``.

        RECONCILE leaves ``_ACTIVATED_BUT_ORPHANED`` (incidence,
        ``test_extractor_projection.py``) AND both ``_ACTION_UNREACHABLE_D1``/
        ``D2`` (reachability, this module) — it is reachable at BOTH depths
        because 024 and 025 are themselves d1-reachable.
        """
        for depth in (_ACTION_D1_DEPTH, _ACTION_D2_DEPTH):
            reach = action_channel_reachable(graph, action_seed_urns(graph), depth)
            assert "directive:RECONCILE_CHANGE_SCOPE_TENSIONS" in reach

    def test_use_mutation_testing_is_action_reachable_via_directive_030(
        self, graph: DRGGraph
    ) -> None:
        """Edge 4: ``DIRECTIVE_030 --suggests--> USE_MUTATION_TESTING_...``.

        Was action-unreachable before this mission; the already action-scoped
        test-quality-gate directive now suggests it, cascading the mutation
        tactic/toolguide family into action context at the bootstrap depth.
        """
        reach = action_channel_reachable(graph, action_seed_urns(graph), _ACTION_D2_DEPTH)
        assert "directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY" in reach

    def test_spike_timebox_policy_is_profile_reachable_via_researcher_robbie(
        self, graph: DRGGraph
    ) -> None:
        """``agent_profile:researcher-robbie --requires--> spike-timebox-policy``,
        data-driven from robbie's ``operating-procedures`` field (M3: the former
        curated hand-pin was retired once the field became a first-class edge
        source — the edge persists, now derived)."""
        reach = profile_channel_reachable(graph, agent_profile_seed_urns(graph))
        assert "procedure:spike-timebox-policy" in reach

    def test_glossary_maintenance_workflow_is_profile_reachable_via_lexical_larry(
        self, graph: DRGGraph
    ) -> None:
        """Edge 6a: ``agent_profile:lexical-larry --suggests--> glossary-
        maintenance-workflow`` (larry FEEDS the workflow; ``suggests``, not
        ``requires`` — carla owns acceptance). ``suggests`` is in
        ``PROFILE_CHANNEL_RELATIONS``, so it still confers reachability."""
        reach = profile_channel_reachable(graph, agent_profile_seed_urns(graph))
        assert "procedure:glossary-maintenance-workflow" in reach

    def test_meeting_minutes_pipeline_is_profile_reachable_via_minutes_mahad(
        self, graph: DRGGraph
    ) -> None:
        """Edge 6b: ``agent_profile:minutes-mahad --requires--> meeting-
        minutes-pipeline`` — mahad's own text: "the primary agent for" it."""
        reach = profile_channel_reachable(graph, agent_profile_seed_urns(graph))
        assert "procedure:meeting-minutes-pipeline" in reach

    def test_removing_the_disciplined_refactoring_edge_reintroduces_unreachability(
        self, graph: DRGGraph
    ) -> None:
        """SC-001 delete-edge negative control (Renata F3).

        Removing edge 1 from a COPY of the shipped graph must revert
        ``directive:DISCIPLINED_REFACTORING`` to action-unreachable — proof the
        helper genuinely traverses the live edge set rather than reading a
        cached/pinned answer. ``DISCIPLINED_REFACTORING``'s only other inbound
        edges are profile-channel ``suggests`` edges from implementer profiles
        (family-B overlay), which do not confer ACTION reachability, so this
        edge is its sole action-channel entry point (a clean single-edge
        dependency, unlike RECONCILE which has two independent suggests
        sources).
        """
        trimmed_edges = [
            e
            for e in graph.edges
            if not (
                e.source == "procedure:refactoring"
                and e.target == "directive:DISCIPLINED_REFACTORING"
                and e.relation is Relation.SUGGESTS
            )
        ]
        assert len(trimmed_edges) == len(graph.edges) - 1, "expected to remove exactly one edge"
        trimmed_graph = graph.model_copy(update={"edges": trimmed_edges})
        reach = action_channel_reachable(
            trimmed_graph, action_seed_urns(trimmed_graph), _ACTION_D2_DEPTH
        )
        assert "directive:DISCIPLINED_REFACTORING" not in reach
        # The companion guard (T006) must independently name it too: its
        # ``measured`` set is exactly ``activatable-kind and not action-reachable``,
        # so the deleted edge must resurface the URN there as well.
        measured, _dead, _profile_delivered = _shipped_reachability_partition(trimmed_graph)
        assert "directive:DISCIPLINED_REFACTORING" in measured


#: The wiring table whose companion-metric ledger section the cross-check below reads.
_WIRING_TABLE_PATH: Path = (
    _REPO_ROOT / "docs" / "plans" / "doctrine" / "delivery-reachability-wiring-table.md"
)
# ---------------------------------------------------------------------------
# T006 (WP01, mission drg-reachability-metric-wiring-01KZS5VR, #3009 point 3):
# the action-only whole-graph reachability companion guard.
# ---------------------------------------------------------------------------

#: Kinds that are unreachable BY DESIGN (edgeless-by-construction / resolved by
#: URN presence, not traversal), so their members must never inflate the
#: companion metric. See contract Alphonso Axis-1 (``anti_pattern`` exclusion
#: rationale) and data-model.md.
_BY_DESIGN_UNREACHABLE_KINDS: frozenset[NodeKind] = frozenset(
    {
        NodeKind.MISSION_STEP_CONTRACT,
        NodeKind.ASSET,
        NodeKind.ANTI_PATTERN,
        NodeKind.TEMPLATE,
        NodeKind.MISSION_TYPE,
        NodeKind.GLOSSARY_PACK,
    }
)


def _shipped_reachability_partition(
    graph: DRGGraph,
) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Compute ``(measured, dead, profile_delivered)`` per the companion-guard
    contract (``contracts/reachability-companion-guard.md``).

    Lives IN the test module, not ``src/`` (Renata F7 — the dead-symbol arch
    gate would flag a ``src/`` helper with no non-test caller). Calls the
    canonical ``action_channel_reachable``/``profile_channel_reachable``
    helpers only — no reimplemented traversal (R-1/C-001).
    """
    action_seeds = action_seed_urns(graph)
    profile_seeds = agent_profile_seed_urns(graph)
    action_reach = action_channel_reachable(graph, action_seeds, _ACTION_D2_DEPTH)
    profile_reach = profile_channel_reachable(graph, profile_seeds)
    kind_of = {n.urn: n.kind for n in graph.nodes}
    measured = {
        n.urn
        for n in graph.nodes
        if n.urn not in action_reach and kind_of[n.urn] not in _BY_DESIGN_UNREACHABLE_KINDS
    } - action_seeds - profile_seeds
    dead = frozenset(u for u in measured if u not in profile_reach)
    profile_delivered = frozenset(measured - dead)
    return frozenset(measured), dead, profile_delivered


#: NOTE (softened per the operator's PR #3342 landing decision, consistent
#: with mission ``assertive-test-suite-sanitation-01KZME3P``'s "test plausible
#: graph behavior, not exact ever-growing membership"): the exact-membership
#: pins that used to live here (``_DEAD_DOCTRINE_SHIPPED``,
#: ``_PROFILE_DELIVERED_SHIPPED``, ``_ACTION_UNREACHABLE_SHIPPED``) were
#: dropped. The companion metric is now asserted by
#: ``TestReachabilityCompanionGuard.test_partition_is_total_and_disjoint``
#: (live totality + disjointness of the measured action-unreachable set) and
#: the fixed anti-gaming gate below (every ``_WIRED_THIS_MISSION`` member is
#: independently proven action-reachable and ledger-named).

#: The thirteen URNs THIS mission makes action-reachable: the anti-null-delta
#: forcing pin (Debbie Item 1). This pin is asserted action-reachable
#: independently below (``TestActionUnreachableShippedLedgerCoverage``),
#: which reds if the edges are not genuinely authored.
_WIRED_THIS_MISSION: frozenset[str] = frozenset(
    {
        "directive:DISCIPLINED_REFACTORING",
        "directive:RECONCILE_CHANGE_SCOPE_TENSIONS",
        "directive:USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY",
        "tactic:mutation-testing-workflow",
        "tactic:refactoring-encapsulate-record",
        "tactic:refactoring-encapsulate-variable",
        "tactic:refactoring-extract-first-order-concept",
        "tactic:refactoring-move-field",
        "tactic:refactoring-move-method",
        "tactic:refactoring-state-pattern-for-behavior",
        "tactic:refactoring-strangler-fig",
        "toolguide:python-mutation-tools",
        "toolguide:typescript-mutation-tools",
    }
)


@pytest.mark.doctrine
class TestReachabilityCompanionGuard:
    """T006: the #3009-point-3 action-only whole-graph companion guard.

    Softened per the operator's landing decision on PR #3342 (consistent with
    mission ``assertive-test-suite-sanitation-01KZME3P``'s "test plausible
    graph behavior, not exact ever-growing membership"): this class asserts
    the live action-unreachable measured set is total and disjoint across its
    dead/profile-delivered partition, NOT an exact-membership pin against a
    frozen literal. The fixed anti-gaming gate
    (``TestActionUnreachableShippedLedgerCoverage``) still forces every
    ``_WIRED_THIS_MISSION`` member to be genuinely action-reachable and
    ledger-named.
    """

    def test_partition_is_total_and_disjoint(self, graph: DRGGraph) -> None:
        """Debbie #1 totality: the two subsets must exactly cover the measured
        action-unreachable set with no overlap, so the "which members are
        genuinely dead" claim cannot silently drift from the partition."""
        measured, dead, profile_delivered = _shipped_reachability_partition(graph)
        assert dead | profile_delivered == measured
        assert not (dead & profile_delivered)

    def test_by_design_kind_is_excluded_even_though_unreachable(self, graph: DRGGraph) -> None:
        """Renata F4: proves the ``_BY_DESIGN_UNREACHABLE_KINDS`` filter branch,
        not just the happy path. A ``mission_step_contract`` node ships with
        ``edges: []`` by construction (resolved by presence, never traversal),
        so it is genuinely unreachable from either channel — yet it must be
        ABSENT from ``measured`` because its kind is excluded by design."""
        sample = next(n.urn for n in graph.nodes if n.kind is NodeKind.MISSION_STEP_CONTRACT)
        action_reach = action_channel_reachable(
            graph, action_seed_urns(graph), _ACTION_D2_DEPTH
        )
        assert sample not in action_reach, "fixture assumption: the sample must be unreachable"
        measured, _dead, _profile_delivered = _shipped_reachability_partition(graph)
        assert sample not in measured

    def test_measured_calls_canonical_helpers_not_a_reimplemented_walk(
        self, graph: DRGGraph
    ) -> None:
        """R-1: the partition helper must be a thin composition of the
        canonical helpers, not an independent walk that could drift."""
        action_reach = action_channel_reachable(
            graph, action_seed_urns(graph), _ACTION_D2_DEPTH
        )
        measured, _dead, _profile_delivered = _shipped_reachability_partition(graph)
        for urn in measured:
            assert urn not in action_reach


#: The companion-metric ledger section (mission-scoped, at the end of the
#: wiring-table doc). Section-scoped (not a whole-document scan) so a forgotten
#: row genuinely fails rather than passing on an incidental mention elsewhere.
_COMPANION_LEDGER_SECTION_START = (
    "## Composition ledger (NFR-002/NFR-004) — reachability companion metric "
    "(mission `drg-reachability-metric-wiring-01KZS5VR`, WP01, #3009 point 3)"
)


def _companion_ledger_text() -> str:
    """The reachability companion-metric ledger section, as raw markdown.

    This section is the LAST one in the document (T007), so it runs to EOF —
    unlike the profile-channel ledger's start/end pair.
    """
    text = _WIRING_TABLE_PATH.read_text(encoding="utf-8")
    start = text.find(_COMPANION_LEDGER_SECTION_START)
    assert start != -1, (
        "reachability companion-metric ledger header not found in "
        f"{_WIRING_TABLE_PATH} — the T007 ledger section is missing"
    )
    return text[start:]


@pytest.mark.doctrine
class TestActionUnreachableShippedLedgerCoverage:
    """T007 mechanical cross-check (analog to ``TestProfileRescuesHaveLedgerCoverage``).

    Un-gameable as an ENSEMBLE, not in isolation (contract anti-requirements):
    the live action-unreachable measured set alone does not force the six
    edges to exist — an implementer could otherwise claim delivery with
    nothing genuinely wired. This class is the anti-null-delta forcing
    mechanism (Debbie Item 1): it asserts every ``_WIRED_THIS_MISSION``
    member is BOTH genuinely action-reachable AND named in a wiring-table
    row, so the action-side delta is CI-gated, not merely review-gated.
    """

    def test_wired_this_mission_members_are_action_reachable(self, graph: DRGGraph) -> None:
        measured, _dead, _profile_delivered = _shipped_reachability_partition(graph)
        still_unreachable = sorted(_WIRED_THIS_MISSION & measured)
        assert not still_unreachable, (
            "these _WIRED_THIS_MISSION members are still in the live "
            "action-unreachable measured set -- the wiring did not take "
            f"effect: {still_unreachable}"
        )

    def test_action_unreachable_shipped_members_have_ledger_coverage(self) -> None:
        ledger = _companion_ledger_text()
        missing = sorted(m for m in _WIRED_THIS_MISSION if f"`{m}`" not in ledger)
        assert not missing, (
            "Every _WIRED_THIS_MISSION member (a live action-unreachable "
            "measured-set departure) must be named (backtick-quoted) in the "
            f"reachability companion-metric ledger section of "
            f"{_WIRING_TABLE_PATH.name}. "
            "Missing ledger rows for:\n" + "\n".join(f"    - {m}" for m in missing)
        )

    def test_cross_check_is_not_vacuous(self) -> None:
        """Guards against the ledger text going empty/unparseable and the
        membership check silently passing over nothing (D18 vacuity risk)."""
        ledger = _companion_ledger_text()
        fabricated = "tactic:__definitely-not-wired-this-mission__"
        assert f"`{fabricated}`" not in ledger
        pretend = frozenset({fabricated})
        missing = sorted(m for m in pretend if f"`{m}`" not in ledger)
        assert missing == [fabricated]


@pytest.mark.doctrine
class TestNominalWiringIsCaughtT047:
    """Wiring an artefact to an unreachable source does not make it reachable.

    This is the WP's reason to exist: an *incidence* check (PR #3007's method)
    reports the nominally-wired artefact fixed; the *reachability* check reports
    it unreachable.
    """

    def test_incidence_calls_the_nominal_wiring_fixed(self) -> None:
        """The wrong method, demonstrated. Both the unreachable source and the
        nominally-wired target are incident to an edge, so incidence de-orphans
        them — the exact false 'fixed' verdict this WP exists to refuse."""
        incident = incident_urns(nominal_wiring_graph())
        assert NOMINALLY_WIRED in incident
        assert UNREACHABLE_SOURCE in incident

    def test_reachability_reports_the_nominal_wiring_unreachable(self) -> None:
        graph = nominal_wiring_graph()
        reachable = action_channel_reachable(graph, [ACTION_URN], _ACTION_D2_DEPTH)
        # The trap: inbound edge from an unreachable source confers no reach.
        assert NOMINALLY_WIRED not in reachable
        assert UNREACHABLE_SOURCE not in reachable

    def test_positive_control_wiring_to_a_reachable_source_does_reach(self) -> None:
        """Guards against a helper that simply refuses every ``requires`` target:
        a directive the action scopes DOES carry reach to what it requires."""
        graph = nominal_wiring_graph()
        reachable = action_channel_reachable(graph, [ACTION_URN], _ACTION_D2_DEPTH)
        assert IN_SCOPE_DIRECTIVE in reachable
        assert PROPERLY_WIRED in reachable
