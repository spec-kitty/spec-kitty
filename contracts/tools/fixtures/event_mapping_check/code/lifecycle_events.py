"""A stand-in for the runtime's lifecycle event module; it is never imported."""

MISSION_CREATED = "MissionCreated"
PLAN_STARTED = "PlanStarted"
WP_CREATED = "WPCreated"
MISSION_REOPENED = "MissionReopened"

LIFECYCLE_EVENT_TYPES = frozenset({MISSION_CREATED, PLAN_STARTED, WP_CREATED, MISSION_REOPENED})
