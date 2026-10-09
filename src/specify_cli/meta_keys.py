"""Persisted meta.json keys written outside the mission metadata TypedDicts."""

COORDINATION_BRANCH_KEY = "coordination_branch"
TOPOLOGY_KEY = "topology"
FLATTENED_KEY = "flattened"
PR_BOUND_KEY = "pr_bound"
MISSION_ID_KEY = "mission_id"
MISSION_NUMBER_KEY = "mission_number"

COORDINATION_KEYS: frozenset[str] = frozenset({COORDINATION_BRANCH_KEY, TOPOLOGY_KEY, FLATTENED_KEY, PR_BOUND_KEY})
IDENTITY_KEYS: frozenset[str] = frozenset({MISSION_ID_KEY, MISSION_NUMBER_KEY})
