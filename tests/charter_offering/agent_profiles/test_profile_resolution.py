"""WP12 (T066/T068/T070) — the profile channel resolves *procedures*.

The authoritative surface for the profile-channel delivery decision is
:meth:`AgentProfileRepository.profile_channel_procedure_ids`. It answers the
doctrine question "which procedures does a loaded profile deliver?" by *calling*
WP08's :func:`charter.offering.drg.reachability.profile_channel_reachable` — the
``walk_edges({requires, specializes_from})`` traversal — and filtering the reached
set to procedure-kind artefacts.

The channel is deliberately **not** ``resolve_context``: ``agent_profile`` nodes
carry zero outbound ``scope`` edges, so a ``resolve_context`` seed measures zero at
any depth (R-3). These tests pin both the positive delivery (the PR #3007 exemplar
``procedure:onboard-external-agent-to-pack`` reaches ``doctrine-daphne``) and the
distinction from ``resolve_context``.
"""

from __future__ import annotations

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.query import resolve_context
from charter.offering.drg.reachability import profile_channel_reachable

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


_DAPHNE = "doctrine-daphne"
_EXEMPLAR = "onboard-external-agent-to-pack"


def test_daphne_channel_delivers_exemplar_procedure() -> None:
    """T068: the requires-edge-reached exemplar procedure is delivered."""
    repo = AgentProfileRepository()
    ids = repo.profile_channel_procedure_ids(_DAPHNE)
    assert _EXEMPLAR in ids


def test_channel_is_walk_edges_not_resolve_context() -> None:
    """R-3: the channel is a walk_edges traversal, not a resolve_context seed.

    ``resolve_context`` from the profile seed returns zero artefacts (profiles
    have no outbound ``scope``), while the profile channel reaches the exemplar.
    Folding the channel into ``resolve_context`` would silently measure nothing.
    """
    repo = AgentProfileRepository()
    graph = repo._drg
    seed = f"agent_profile:{_DAPHNE}"

    # resolve_context measures zero from a profile seed at any depth.
    assert resolve_context(graph, seed, depth=2).artifact_urns == frozenset()

    # The walk_edges channel reaches the exemplar procedure URN.
    reached = profile_channel_reachable(graph, {seed})
    assert f"procedure:{_EXEMPLAR}" in reached

    # And the repository method surfaces exactly that via the channel.
    assert _EXEMPLAR in repo.profile_channel_procedure_ids(_DAPHNE)


def test_unknown_profile_channel_is_fail_closed() -> None:
    """T069: an unknown/absent profile reaches nothing (no fail-open)."""
    repo = AgentProfileRepository()
    assert repo.profile_channel_procedure_ids("no-such-profile") == []
