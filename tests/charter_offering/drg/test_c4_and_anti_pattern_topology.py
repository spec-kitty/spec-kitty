"""ATDD — WP02 companion topology: C4 template delivery + refactoring anti-patterns.

Mission ``doctrine-delivery-activation-01KYQVQK``, WP02 (T011). Two independent
companion deliverables, proved on the correct tier for each (D13/D14):

* **C4 template delivery (delivery-tier).** The architect reaches the three
  ``template:c4-*-mermaid-template`` nodes through the PROFILE channel
  (``profile_channel_reachable``), which walks ``suggests`` only because WP01
  added ``Relation.SUGGESTS`` to ``PROFILE_CHANNEL_RELATIONS``. The delivery
  path is ``agent_profile:architect-alphonso --suggests-->
  directive:USE_C4_MODEL_TECHNIQUES --suggests--> tactic:c4-zoom-in-
  architecture-documentation --suggests--> template:c4-*`` (the tactic's own
  step ``references:`` mint the last hop). Reverting WP01's ``suggests`` addition
  to the profile channel makes this assertion fail — that is the D13 dependency
  the review gate checks for. The ``action:documentation/design --instantiates-->
  template:c4-*`` edges T007 authored are TOPOLOGY completion, asserted here as a
  pure ``edges``-membership check; they are NOT the delivery vector (no channel
  walks ``instantiates``).

* **Refactoring anti-patterns (validation-tier).** Each of the seven anti_pattern
  nodes T008/T009 authored is the target of at least one ``rejects`` edge (the
  ``_validate_anti_pattern_nodes_are_rejected`` invariant), the graph validator
  is green over the extended corpus, and — critically — the anti_pattern nodes
  are NEVER delivered: not profile-channel-reachable and not action-channel-
  reachable. A regression that made an anti_pattern deliverable would silently
  violate D14/C-004's non-activatable-kind guarantee.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.reachability import (
    action_channel_reachable,
    action_seed_urns,
    agent_profile_seed_urns,
    profile_channel_reachable,
)
from charter.offering.drg.validator import validate_graph

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

_ARCHITECT = "agent_profile:architect-alphonso"
_DESIGN_ACTION = "action:documentation/design"

_C4_TEMPLATES = (
    "template:c4-context-mermaid-template",
    "template:c4-container-mermaid-template",
    "template:c4-component-mermaid-template",
)

#: The seven anti_pattern nodes T008 authored, paired with the refactoring tactic
#: that rejects each (T009). Order is (tactic, anti_pattern).
_REFACTORING_REJECTS: tuple[tuple[str, str], ...] = (
    ("tactic:refactoring-encapsulate-record", "anti_pattern:unencapsulated-record"),
    ("tactic:refactoring-encapsulate-variable", "anti_pattern:global-data"),
    ("tactic:refactoring-extract-first-order-concept", "anti_pattern:implicit-concept"),
    ("tactic:refactoring-move-field", "anti_pattern:misplaced-field"),
    ("tactic:refactoring-move-method", "anti_pattern:feature-envy"),
    (
        "tactic:refactoring-state-pattern-for-behavior",
        "anti_pattern:repeated-switches-on-state",
    ),
    ("tactic:refactoring-strangler-fig", "anti_pattern:big-bang-rewrite"),
)

_NEW_ANTI_PATTERNS = tuple(ap for _, ap in _REFACTORING_REJECTS)


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    """The shipped built-in DRG — same seam the other doctrine suites use."""
    return load_built_in_graph()


class TestC4TemplateDelivery:
    """C4 templates are DELIVERED to the architect via the profile channel (D13)."""

    def test_architect_reaches_all_three_c4_templates_via_profile_channel(
        self, graph: DRGGraph
    ) -> None:
        """The delivery-tier proof (depends on WP01's ``suggests`` walk).

        Seeded from a SINGLE profile so the result is the doctrine the architect
        specifically reaches, not the whole activated universe. If WP01's
        addition of ``Relation.SUGGESTS`` to ``PROFILE_CHANNEL_RELATIONS`` were
        reverted, the two-hop ``suggests`` chain to the C4 tactic breaks and this
        assertion fails — exactly the D13 dependency.
        """
        reached = profile_channel_reachable(graph, {_ARCHITECT})
        missing = [t for t in _C4_TEMPLATES if t not in reached]
        assert not missing, (
            f"architect-alphonso does not reach {missing} through the profile "
            "channel — WP01's suggests-walk (or the C4 suggests chain) regressed"
        )

    def test_design_action_instantiates_each_c4_template(self, graph: DRGGraph) -> None:
        """T007 topology completion — pure ``instantiates`` edge membership.

        No WP01 dependency: this is the topology this WP authored, not delivery.
        """
        instantiates = {
            (e.source, e.target)
            for e in graph.edges
            if e.relation is Relation.INSTANTIATES
        }
        for template in _C4_TEMPLATES:
            assert (_DESIGN_ACTION, template) in instantiates, (
                f"missing instantiates edge {_DESIGN_ACTION} -> {template}"
            )

    def test_instantiates_is_not_the_delivery_vector(self, graph: DRGGraph) -> None:
        """Guards the D13 narrative: ``instantiates`` is walked by no channel.

        The C4 templates are delivered by the tactic's ``suggests`` edges, not the
        T007 ``instantiates`` edges. Proof: the ``action:documentation/design``
        action does not itself reach the C4 templates through the action channel
        via the instantiates edges (resolve_context does not walk instantiates),
        so their profile-channel delivery cannot be an artefact of T007.
        """
        action_reach = action_channel_reachable(graph, {_DESIGN_ACTION}, depth=2)
        for template in _C4_TEMPLATES:
            assert template not in action_reach, (
                f"{template} became action-reachable from {_DESIGN_ACTION}; the "
                "instantiates edge must not be a delivery vector (D13)"
            )


class TestRefactoringAntiPatternValidation:
    """Anti_pattern REJECTS topology is complete and validation-tier only (D14)."""

    def test_graph_validator_is_green_over_extended_corpus(
        self, graph: DRGGraph
    ) -> None:
        """No orphan / mistargeted-rejects errors for the 13-node corpus."""
        errors = validate_graph(graph)
        assert errors == [], f"validator reported errors: {errors}"

    @pytest.mark.parametrize(("tactic", "anti_pattern"), _REFACTORING_REJECTS)
    def test_each_anti_pattern_is_a_rejects_target(
        self, graph: DRGGraph, tactic: str, anti_pattern: str
    ) -> None:
        """Mirrors ``_validate_anti_pattern_nodes_are_rejected``: >=1 inbound rejects."""
        inbound = graph.edges_to(anti_pattern, relation=Relation.REJECTS)
        assert inbound, f"{anti_pattern} has no inbound rejects edge"
        assert any(e.source == tactic for e in inbound), (
            f"{anti_pattern} is not rejected by its authoring tactic {tactic}"
        )

    def test_anti_patterns_are_never_delivered(self, graph: DRGGraph) -> None:
        """D14/C-004: anti_pattern is a non-activatable kind — reached by no channel.

        Asserted against BOTH channels seeded from the full activated universe, so
        a regression that wired an anti_pattern into any delivery path is caught
        regardless of which channel introduced it.
        """
        profile_reach = profile_channel_reachable(graph, agent_profile_seed_urns(graph))
        action_reach = action_channel_reachable(
            graph, action_seed_urns(graph), depth=2
        )
        for anti_pattern in _NEW_ANTI_PATTERNS:
            assert anti_pattern not in profile_reach, (
                f"{anti_pattern} is profile-channel-reachable — anti_patterns must "
                "stay validation-tier only (D14)"
            )
            assert anti_pattern not in action_reach, (
                f"{anti_pattern} is action-channel-reachable — anti_patterns must "
                "stay validation-tier only (D14)"
            )
