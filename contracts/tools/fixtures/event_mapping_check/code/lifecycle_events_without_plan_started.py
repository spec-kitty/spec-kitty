"""A stand-in for the runtime's lifecycle event module that lacks a type the contract forwards; it is never imported."""

MISSION_CREATED = "MissionCreated"
WP_CREATED = "WPCreated"

LIFECYCLE_EVENT_TYPES = frozenset({MISSION_CREATED, WP_CREATED})
