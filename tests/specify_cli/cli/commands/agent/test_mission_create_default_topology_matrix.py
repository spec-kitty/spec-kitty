"""Default-topology matrix for ``_resolve_default_topology_phase`` (S7 #7282, ADR 2026-11-06-3).

The phase returns ``(topology, topology_source)``. A create without ``--topology`` is
provisional, stored as ``single_branch`` with ``topology_source: default`` on every
target and whatever ``--pr-bound`` says (the context-derived ``coord`` / ``lanes``
default of #2581 / #2602 and the ``--pr-bound`` reachability fallback are gone). An
explicit ``--topology`` wins (``explicit``); ``--owned-checkout`` implies
``single_branch`` (``owned_checkout``). The phase reads no git state, so this matrix
needs no repository; the real-repository behaviour is pinned in
``test_mission_create_provisional_topology.py``.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.mission_create import _resolve_default_topology_phase
from specify_cli.meta_keys import TopologySource

pytestmark = [pytest.mark.fast]

# Presence-only stand-in for the validated ``OwnedCreateRoot`` fact.
_OWNED_CREATE_ROOT = cast(Any, object())


@pytest.mark.parametrize(
    ("case_id", "explicit", "owned", "expected"),
    [
        ("default", None, None, (MissionTopology.SINGLE_BRANCH, TopologySource.DEFAULT)),
        ("explicit_single_branch", MissionTopology.SINGLE_BRANCH, None, (MissionTopology.SINGLE_BRANCH, TopologySource.EXPLICIT)),
        ("explicit_lanes", MissionTopology.LANES, None, (MissionTopology.LANES, TopologySource.EXPLICIT)),
        ("explicit_coord", MissionTopology.COORD, None, (MissionTopology.COORD, TopologySource.EXPLICIT)),
        ("explicit_lanes_with_coord", MissionTopology.LANES_WITH_COORD, None, (MissionTopology.LANES_WITH_COORD, TopologySource.EXPLICIT)),
        ("owned_checkout_no_topology", None, _OWNED_CREATE_ROOT, (MissionTopology.SINGLE_BRANCH, TopologySource.OWNED_CHECKOUT)),
        ("explicit_wins_over_owned", MissionTopology.LANES_WITH_COORD, _OWNED_CREATE_ROOT, (MissionTopology.LANES_WITH_COORD, TopologySource.EXPLICIT)),
    ],
)
def test_default_topology_matrix(case_id: str, explicit: MissionTopology | None, owned: Any, expected: tuple[MissionTopology, TopologySource]) -> None:
    assert _resolve_default_topology_phase(explicit_topology=explicit, owned_create_root=owned) == expected, case_id
