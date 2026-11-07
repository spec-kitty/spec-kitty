"""Persisted meta.json keys written outside the mission metadata TypedDicts."""

from enum import StrEnum

COORDINATION_BRANCH_KEY = "coordination_branch"
TOPOLOGY_KEY = "topology"
FLATTENED_KEY = "flattened"
PR_BOUND_KEY = "pr_bound"
MISSION_ID_KEY = "mission_id"
MISSION_NUMBER_KEY = "mission_number"

#: How the stored ``topology`` was chosen (ADR 2026-11-06-3 Decision 4). Absent means a
#: legacy Mission, and a legacy Mission counts as settled (FR-057).
TOPOLOGY_SOURCE_KEY = "topology_source"
#: ``false`` only while a ``topology_source: default`` Mission is provisional; settlement
#: at the first ``finalize-tasks`` sets it ``true``. Written only for default creates.
TOPOLOGY_SETTLED_KEY = "topology_settled"
#: The write-once settlement record ``{rule, wp_count, code_lane_count, from, to, ...}``.
TOPOLOGY_DECISION_KEY = "topology_decision"
#: The branch the write checkout was on before a default create switched it onto the
#: Mission topic branch; settlement to ``lanes_with_coord`` moves the checkout back to it.
CREATE_RETURN_BRANCH_KEY = "create_return_branch"

COORDINATION_KEYS: frozenset[str] = frozenset({COORDINATION_BRANCH_KEY, TOPOLOGY_KEY, FLATTENED_KEY, PR_BOUND_KEY})
IDENTITY_KEYS: frozenset[str] = frozenset({MISSION_ID_KEY, MISSION_NUMBER_KEY})


class TopologySource(StrEnum):
    """The stored values of :data:`TOPOLOGY_SOURCE_KEY`."""

    EXPLICIT = "explicit"
    OWNED_CHECKOUT = "owned_checkout"
    DEFAULT = "default"


#: The ONE ``--topology`` help text, shared by ``agent mission create``, ``specify`` and
#: ``orchestrator-api specify`` (FR-059).
TOPOLOGY_HELP = (
    "Mission shape: single_branch | lanes | coord | lanes_with_coord. "
    "Default (no --topology): create mints one Mission topic branch "
    "(kitty/mission-<slug>-<mid8>) and checks it out, on any target, with no lanes, "
    "worktrees or coordination branch; the first finalize-tasks then settles the "
    "shape by size: single_branch for at most 2 work packages or at most 1 code lane, "
    "else lanes_with_coord with the topic branch as the coordination branch. "
    "lanes and coord are produced only by an explicit --topology. An explicit value "
    "always wins and is settled at create (--owned-checkout implies single_branch)."
)
