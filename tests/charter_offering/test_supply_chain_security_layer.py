"""Action-context wiring: plan/implement/review resolve the supply-chain
security-layer artifacts through the real DRG walk (WP05, T016).

Mission ``supply-chain-security-checks-layer-01KZBFBS``. WP02 already pins the
*raw* action-index membership (``tests/charter_offering/missions/test_action_indexes.py``
asserts ``"051-supply-chain-install-safety"``/``"supply-chain-install-safety"``
appear in the parsed ``index.yaml`` lists). This module is deliberately a
different, deeper binding class: it proves the artifacts are reachable through
:func:`charter.offering.drg.query.resolve_context` -- the single canonical action-context
walk the runtime actually uses (see ``doctrine/drg/reachability.py``) -- and
that the reachability is a *direct scope edge*, not incidental transitive
reachability through an unrelated ``suggests``/``requires`` chain.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.query import resolve_context

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_DIRECTIVE_URN = "directive:DIRECTIVE_051"
_TACTIC_URN = "tactic:supply-chain-install-safety"
_SOFTWARE_DEV_ACTIONS = ("plan", "implement", "review")


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    return load_built_in_graph()


class TestResolvedContextIncludesSecurityLayer:
    """``resolve_context`` surfaces the directive/tactic for every wired action."""

    @pytest.mark.parametrize("action", _SOFTWARE_DEV_ACTIONS)
    def test_resolved_context_includes_directive_and_tactic(
        self, graph: DRGGraph, action: str
    ) -> None:
        urn = f"action:software-dev/{action}"
        ctx = resolve_context(graph, urn, depth=1)

        assert _DIRECTIVE_URN in ctx.artifact_urns, (
            f"{action}: resolved context missing {_DIRECTIVE_URN}; "
            f"got {sorted(ctx.artifact_urns)}"
        )
        assert _TACTIC_URN in ctx.artifact_urns, (
            f"{action}: resolved context missing {_TACTIC_URN}; "
            f"got {sorted(ctx.artifact_urns)}"
        )

    @pytest.mark.parametrize("action", _SOFTWARE_DEV_ACTIONS)
    def test_context_resolution_is_stable_across_depths(
        self, graph: DRGGraph, action: str
    ) -> None:
        """The security layer is directly scoped, so it must already be
        present at the compact (d=1) depth -- not something that only
        appears once ``suggests`` traversal is widened to d=2. A regression
        that wired the directive/tactic in via a ``suggests`` edge several
        hops away would pass a d=2-only check but fail this one.
        """
        urn = f"action:software-dev/{action}"
        ctx_d1 = resolve_context(graph, urn, depth=1)
        ctx_d2 = resolve_context(graph, urn, depth=2)

        assert _DIRECTIVE_URN in ctx_d1.artifact_urns
        assert _TACTIC_URN in ctx_d1.artifact_urns
        # Widening suggests-depth must not make the artifacts disappear.
        assert _DIRECTIVE_URN in ctx_d2.artifact_urns
        assert _TACTIC_URN in ctx_d2.artifact_urns


class TestWiringIsDirectScopeNotIncidentalReachability:
    """The directive/tactic must be directly ``scope``-edged from the action
    node itself, not merely reachable through some other artifact's
    ``suggests``/``requires`` edges.
    """

    @pytest.mark.parametrize("action", _SOFTWARE_DEV_ACTIONS)
    def test_action_has_direct_scope_edge_to_directive_and_tactic(
        self, graph: DRGGraph, action: str
    ) -> None:
        urn = f"action:software-dev/{action}"
        scoped_targets = {edge.target for edge in graph.edges_from(urn, Relation.SCOPE)}

        assert _DIRECTIVE_URN in scoped_targets, (
            f"{action}: no direct scope edge to {_DIRECTIVE_URN}; "
            f"scoped targets were {sorted(scoped_targets)}"
        )
        assert _TACTIC_URN in scoped_targets, (
            f"{action}: no direct scope edge to {_TACTIC_URN}; "
            f"scoped targets were {sorted(scoped_targets)}"
        )
