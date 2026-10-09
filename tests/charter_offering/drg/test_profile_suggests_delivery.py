"""ATDD — the profile channel *delivers* the #3063 A–E ``suggests`` topology.

Mission ``doctrine-delivery-activation-01KYQVQK``, WP01 (THE core delivery
vector, plan IC-01). PR #3070 authored the A–E ``suggests`` edges in the DRG,
but the profile-channel walk traversed only ``{requires, specializes_from}`` —
every authored edge was inert. This suite proves the topology is now live.

**Entry point (D10, hard block):** every assertion is made on
``profile_channel_reachable(graph, {agent_profile:…})`` and the profile *render*
path (``_render_profile_sections`` / the new
``render_profile_suggested_doctrine`` renderer / the
``profile_channel_references`` projection). ``charter.offering.drg.query.resolve_context``
(the ACTION channel) is FORBIDDEN as the delivery entry point here — DDD is
already action-reachable there (vacuously green) and ``resolve_context`` seeded
from a profile reaches nothing. It appears in this file ONLY in A6's isolation
guard, asserting the action channel is *unchanged*.

Acceptances map one test (cluster) per letter A0–A6 (contract
``suggests-delivery-walk.md``); the class/method names carry the letter so a
reviewer can map test → acceptance at a glance.
"""

from __future__ import annotations

import pytest

from charter.activation.context_renderers.profile_sections import (
    _PROFILE_SUGGESTS_DELIVERED_KINDS,
    _render_profile_sections,
    render_profile_suggested_doctrine,
)
from charter.activation.progressive_disclosure import (
    STATED_DEFAULT_WHEN,
    partition_delivery,
    profile_channel_references,
)
from charter.offering.agent_profiles import AgentProfile, AgentProfileRepository
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from charter.offering.drg.query import resolve_context
from charter.offering.drg.reachability import profile_channel_reachable
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.doctrine, pytest.mark.fast, pytest.mark.corpus]

# --- URNs under test --------------------------------------------------------
_ARCHITECT = "agent_profile:architect-alphonso"
_PEDRO = "agent_profile:python-pedro"
_DDD = "paradigm:domain-driven-design"
_MOVE_METHOD = "tactic:refactoring-move-method"
_DISCIPLINED_REFACTORING = "directive:DISCIPLINED_REFACTORING"

# The authored Family-B ``when`` on ``DISCIPLINED_REFACTORING -> move-method``
# (``hand_authored_overlay.py``). Family B carries real ``when`` text today,
# independent of WP02's Family-A backfill, so A2 may assert it verbatim.
_MOVE_METHOD_WHEN = (
    "a method uses more of another class's data and behaviour than its own "
    "host's (feature envy)"
)


@pytest.fixture(scope="module")
def graph() -> DRGGraph:
    """The shipped built-in DRG — same seam ``test_reachability.py`` uses."""
    return load_built_in_graph()


@pytest.fixture(scope="module")
def service() -> CharterOfferingService:
    """A CharterOfferingService over the shipped built-in doctrine tree.

    No explicit built-in root: each repository self-resolves the flattened
    built-in tier via ``resolve_pack_root("built-in")`` (packs/built-in/<kind>).
    Post-relocation, ``files("charter.offering")`` points at the emptied src/doctrine
    tree and would load nothing.
    """
    return CharterOfferingService()


def _kind_filtered(reached: frozenset[str]) -> set[str]:
    """The delivered subset of *reached* under the render-layer kind table."""
    return {u for u in reached if u.split(":", 1)[0] in _PROFILE_SUGGESTS_DELIVERED_KINDS}


def _refs_for(graph: DRGGraph, seed: str) -> list[dict[str, str | None]]:
    seeds = {seed}
    reached = profile_channel_reachable(graph, seeds)
    return profile_channel_references(graph, seeds, reached, _kind_filtered(reached))


# ---------------------------------------------------------------------------
# A1 — Family A: architect reaches DDD; render surfaces its ``when``
# ---------------------------------------------------------------------------
class TestA1FamilyAParadigmDelivered:
    def test_architect_channel_reaches_ddd(self, graph: DRGGraph) -> None:
        reached = profile_channel_reachable(graph, {_ARCHITECT})
        assert _DDD in reached

    def test_render_surfaces_ddd_with_a_when(self, service: CharterOfferingService) -> None:
        profile = AgentProfileRepository().resolve_profile("architect-alphonso")
        block = _render_profile_sections(profile, service)
        assert "domain-driven-design" in block
        # A ``when`` string is present for the delivered paradigm (the authored
        # one once WP02 lands, or STATED_DEFAULT_WHEN until then). Assert
        # presence + a rendered fetch (link) stanza, not the exact literal, so
        # WP01 is not over-coupled to WP02's landing order.
        assert "spec-kitty charter context --include paradigm:domain-driven-design" in block

    def test_projection_carries_a_nonempty_when_for_ddd(self, graph: DRGGraph) -> None:
        refs = _refs_for(graph, _ARCHITECT)
        ddd = [r for r in refs if r["id"] == "domain-driven-design"]
        assert ddd, "DDD must be projected as a delivered reference"
        assert ddd[0]["when"], "delivered paradigm must carry a non-empty when"


# ---------------------------------------------------------------------------
# A2 — Family B: implementer reaches the refactoring tactics with authored when
# ---------------------------------------------------------------------------
class TestA2FamilyBTacticsDelivered:
    def test_pedro_channel_reaches_move_method(self, graph: DRGGraph) -> None:
        reached = profile_channel_reachable(graph, {_PEDRO})
        assert _MOVE_METHOD in reached
        assert _DISCIPLINED_REFACTORING in reached

    def test_projection_carries_authored_when_verbatim(self, graph: DRGGraph) -> None:
        refs = _refs_for(graph, _PEDRO)
        move = [r for r in refs if r["id"] == "refactoring-move-method"]
        assert move, "the refactoring tactic must be delivered"
        assert move[0]["relation"] == "suggests"
        assert move[0]["when"] == _MOVE_METHOD_WHEN

    def test_render_surfaces_the_refactoring_tactic(self, service: CharterOfferingService) -> None:
        profile = AgentProfileRepository().resolve_profile("python-pedro")
        block = _render_profile_sections(profile, service)
        assert "refactoring-move-method" in block
        assert "feature envy" in block


# ---------------------------------------------------------------------------
# A3 — a ``suggests`` edge with no authored ``when`` surfaces STATED_DEFAULT_WHEN
# ---------------------------------------------------------------------------
class TestA3DefaultWhen:
    def test_when_less_family_a_edge_surfaces_the_default(self, graph: DRGGraph) -> None:
        # RE-TARGETED by WP02 (mission doctrine-delivery-activation-01KYQVQK,
        # T006), executing the WP01 ">>> WP02 NOTE <<<" that anticipated this:
        # WP01 asserted STATED_DEFAULT_WHEN on the (then ``when``-less) first-hop
        # ``agent_profile:architect-alphonso -> paradigm:domain-driven-design``
        # edge; T006 backfilled that edge's ``when``, so the assertion is now
        # aimed at the STATED_DEFAULT_WHEN substitution PATH itself rather than
        # that one edge. The architect still reaches ~36 delivered ``when``-less
        # ``suggests`` edges (measured), so the substitution path stays provable
        # without coupling to any single edge a future #3063 backfill might touch.
        refs = _refs_for(graph, _ARCHITECT)
        # DDD is no longer the fixture — it now carries an authored ``when`` (T006).
        ddd = [r for r in refs if r["id"] == "domain-driven-design"]
        assert ddd and ddd[0]["when"] and ddd[0]["when"] != STATED_DEFAULT_WHEN, (
            "T006 must have given architect->DDD an authored, non-default when"
        )
        defaulted = [
            r
            for r in refs
            if r["relation"] == "suggests" and r["when"] == STATED_DEFAULT_WHEN
        ]
        assert defaulted, (
            "no delivered when-less suggests edge surfaced STATED_DEFAULT_WHEN — "
            "the default-when substitution path regressed"
        )


# ---------------------------------------------------------------------------
# A4 — a diamond (requires AND suggests) delivers once, eager (requires wins)
# ---------------------------------------------------------------------------
class TestA4DiamondRequiresPrecedence:
    @staticmethod
    def _diamond_graph() -> DRGGraph:
        """A synthetic diamond: ``diamond-tac`` is reachable from the profile via
        a direct ``requires`` edge AND via a ``suggests`` chain through
        ``bridge-dir``. Requires precedence must collapse it to eager delivery.
        """
        return DRGGraph(
            schema_version="1.0",
            generated_at="1970-01-01T00:00:00Z",
            generated_by="test_profile_suggests_delivery:_diamond_graph",
            nodes=[
                DRGNode(urn="agent_profile:test-diamond", kind=NodeKind.AGENT_PROFILE),
                DRGNode(urn="tactic:diamond-tac", kind=NodeKind.TACTIC),
                DRGNode(urn="directive:bridge-dir", kind=NodeKind.DIRECTIVE),
            ],
            edges=[
                DRGEdge(
                    source="agent_profile:test-diamond",
                    target="tactic:diamond-tac",
                    relation=Relation.REQUIRES,
                ),
                DRGEdge(
                    source="agent_profile:test-diamond",
                    target="directive:bridge-dir",
                    relation=Relation.SUGGESTS,
                    when="restructuring the bridge",
                ),
                DRGEdge(
                    source="directive:bridge-dir",
                    target="tactic:diamond-tac",
                    relation=Relation.SUGGESTS,
                    when="the bridge pulls the tactic",
                ),
            ],
        )

    def test_partition_puts_the_diamond_in_the_eager_set(self) -> None:
        graph = self._diamond_graph()
        seeds = {"agent_profile:test-diamond"}
        reached = profile_channel_reachable(graph, seeds)
        delivered = _kind_filtered(reached)
        inline, link = partition_delivery(graph, seeds, delivered)
        assert "tactic:diamond-tac" in inline
        assert "tactic:diamond-tac" not in link

    def test_diamond_is_not_delivered_as_a_suggests_link(self) -> None:
        graph = self._diamond_graph()
        seeds = {"agent_profile:test-diamond"}
        reached = profile_channel_reachable(graph, seeds)
        refs = profile_channel_references(graph, seeds, reached, _kind_filtered(reached))
        diamond_refs = [r for r in refs if r["id"] == "diamond-tac"]
        assert diamond_refs == [], "requires precedence: the diamond delivers eager, not linked"
        # The bridge itself (suggests-only) still delivers as a link — the
        # channel is not simply dropping everything.
        assert any(r["id"] == "bridge-dir" for r in refs)


# ---------------------------------------------------------------------------
# A5 — suggested artefacts are references (links), never inlined bodies
# ---------------------------------------------------------------------------
class TestA5LinksNotBodies:
    def test_suggested_artefact_renders_as_a_fetch_link(self, service: CharterOfferingService) -> None:
        profile = AgentProfileRepository().resolve_profile("python-pedro")
        lines = render_profile_suggested_doctrine(profile, service)
        block = "\n".join(lines)
        # The canonical fetch/link marker is present …
        assert "Run: spec-kitty charter context --include" in block
        assert "tactic:refactoring-move-method" in block
        # … and the tactic's full inline body (its stepwise applicability prose)
        # is NOT dumped inline — a link names + defers, it never inlines (NFR-003).
        tactic = service.tactics.get("refactoring-move-method")
        steps = getattr(tactic, "steps", None)
        assert steps, "fixture sanity: the tactic has an inline body to withhold"
        first_step = getattr(steps[0], "description", None) or getattr(steps[0], "title", "")
        assert str(first_step) not in block


# ---------------------------------------------------------------------------
# A6 — the action channel (resolve_context) is unchanged by this WP (isolation)
# ---------------------------------------------------------------------------
class TestA6ActionChannelIsolation:
    def test_resolve_context_from_a_profile_still_reaches_nothing(self, graph: DRGGraph) -> None:
        """Widening the PROFILE channel must not leak into the ACTION channel.

        ``resolve_context`` step 1 walks ``scope`` only, and profiles carry zero
        outbound ``scope`` — so seeding a profile still reaches nothing. If the
        WP01 change had (wrongly) touched ``resolve_context``/``query.py`` this
        would break.
        """
        for seed in (_ARCHITECT, _PEDRO):
            for depth in (1, 2):
                assert resolve_context(graph, seed, depth=depth).artifact_urns == frozenset()

    def test_action_channel_still_delivers_ddd_via_scope(self, graph: DRGGraph) -> None:
        """DDD stays action-reachable via the specify ``scope`` edge — the action
        channel is a separate, intact walk (the profile channel now ALSO reaches
        DDD, from a different seed, which is the whole point of two channels)."""
        reached = resolve_context(graph, "action:software-dev/specify", depth=2).artifact_urns
        assert _DDD in reached


def test_synthetic_profile_with_no_suggests_reach_renders_empty(
    service: CharterOfferingService,
) -> None:
    """Fail-closed: a profile whose channel reaches no deliverable suggests
    doctrine contributes no section (no fail-open whole-graph fallback)."""
    profile = AgentProfile.model_validate(
        {
            "profile-id": "synthetic-empty",
            "name": "Synthetic Empty",
            "roles": ["implementer"],
            "purpose": "test fixture",
            "specialization": {"primary-focus": "testing"},
        }
    )
    assert render_profile_suggested_doctrine(profile, service) == []


# ---------------------------------------------------------------------------
# Defensive-degrade branches: a service/repo that cannot answer the profile
# channel query must never crash the renderer, and a kind whose delivered
# set is empty (or whose delivered id has no projectable reference) must be
# skipped rather than emitting an empty/garbage section.
# ---------------------------------------------------------------------------


def _minimal_profile(profile_id: str) -> AgentProfile:
    return AgentProfile.model_validate(
        {
            "profile-id": profile_id,
            "name": profile_id,
            "roles": ["implementer"],
            "purpose": "test fixture",
            "specialization": {"primary-focus": "testing"},
        }
    )


def test_service_without_agent_profiles_repo_renders_nothing() -> None:
    """A ``service`` missing the ``agent_profiles`` repo degrades to no section.

    ``getattr(service, "agent_profiles", None)`` is the guard -- a service
    object that never wired the profile repository (e.g. a partial/legacy
    ``CharterOfferingService``-like object) must not raise; the profile channel is
    simply unavailable, so the renderer contributes nothing.
    """

    class _ServiceWithoutAgentProfiles:
        """No ``agent_profiles`` attribute -- mirrors an under-wired service."""

    profile = _minimal_profile("synthetic-no-repo")
    assert render_profile_suggested_doctrine(profile, _ServiceWithoutAgentProfiles()) == []


def test_channel_lookup_exception_renders_nothing() -> None:
    """A ``profile_channel_reached`` that raises degrades to no section, not a crash.

    Mirrors :func:`render_profile_procedures`'s existing best-effort catch --
    the profile channel is advisory context, never a hard dependency the
    resolver can be broken by.
    """

    class _RaisingAgentProfiles:
        def profile_channel_reached(self, profile_id: str) -> frozenset[str]:
            raise RuntimeError(f"channel lookup exploded for {profile_id!r}")

    class _ServiceWithRaisingAgentProfiles:
        agent_profiles = _RaisingAgentProfiles()

    profile = _minimal_profile("synthetic-raising-channel")
    assert (
        render_profile_suggested_doctrine(profile, _ServiceWithRaisingAgentProfiles())
        == []
    )


def test_delivered_kind_with_no_projectable_reference_is_skipped() -> None:
    """A delivered id with no inbound graph edge is skipped, not KeyError'd.

    ``reached`` is normally derived from a real graph walk, so every delivered
    artefact has an inbound edge from within ``reached ∪ seeds`` by
    construction (see :func:`~charter.activation.progressive_disclosure.profile_channel_references`).
    This fixture decouples the two on purpose -- the fake channel reports a
    tactic as reached even though the (edgeless) graph carries no path to it
    -- to exercise two per-kind guards in the same pass: every non-tactic kind
    in the render loop sees an empty ``delivered_ids`` for this profile
    (continue), and the tactic kind sees a non-empty ``delivered_ids`` whose
    projected reference set is nonetheless empty (continue) -- so the section
    is silently omitted rather than rendered as an empty/garbage header.
    """
    orphan_graph = DRGGraph(
        schema_version="1.0",
        generated_at="1970-01-01T00:00:00Z",
        generated_by="test_profile_suggests_delivery:orphan_graph",
        nodes=[
            DRGNode(urn="agent_profile:test-orphan", kind=NodeKind.AGENT_PROFILE),
            DRGNode(urn="tactic:orphan-tac", kind=NodeKind.TACTIC),
        ],
        edges=[],  # deliberately no edges -- orphan-tac is unreachable via any path
    )

    class _OrphanReachRepo:
        drg = orphan_graph

        def profile_channel_reached(self, profile_id: str) -> frozenset[str]:
            return frozenset({"tactic:orphan-tac"})

    class _ServiceWithOrphanReach:
        agent_profiles = _OrphanReachRepo()

    profile = _minimal_profile("test-orphan")
    assert render_profile_suggested_doctrine(profile, _ServiceWithOrphanReach()) == []
