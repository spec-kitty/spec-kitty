"""Charter facade for agent profile types.

This module is the charter-layer proxy for runtime callers that historically
imported from ``charter.offering.agent_profiles`` directly. The runtime → charter →
charter.offering boundary (ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime modules
under ``src/specify_cli/`` to reach charter offering artifacts only through such
charter facades.

This file is a **pure re-export** module — no behaviour, no wrappers, no
type aliases. Identity is preserved (``charter.profiles.AgentProfile is
charter.offering.agent_profiles.profile.AgentProfile``).
"""

from charter.offering.agent_profiles.capabilities import DEFAULT_ROLE_CAPABILITIES
from charter.offering.agent_profiles.diagnostics import SkippedProfile
from charter.offering.agent_profiles.profile import AgentProfile, Role
from charter.offering.agent_profiles.repository import AgentProfileRepository

__all__ = [
    "AgentProfile",
    "AgentProfileRepository",
    "DEFAULT_ROLE_CAPABILITIES",
    "Role",
    "SkippedProfile",
]
