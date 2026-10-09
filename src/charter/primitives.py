"""Charter facade for mission primitive execution.

This module is the charter-layer proxy for runtime callers that historically
imported from ``charter.offering.missions`` directly. The runtime → charter →
charter.offering boundary (ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime modules
under ``src/specify_cli/`` to reach charter offering artifacts only through such
charter facades.

This file is a **pure re-export** module — no behaviour, no wrappers, no
type aliases.
"""

from charter.offering.missions import PrimitiveExecutionContext, execute_with_glossary

__all__ = [
    "PrimitiveExecutionContext",
    "execute_with_glossary",
]
