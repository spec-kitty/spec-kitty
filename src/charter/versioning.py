"""Charter facade for charter-bundle versioning helpers.

This module is the charter-layer proxy for runtime callers that historically
imported from ``charter.offering.versioning`` directly. The runtime → charter →
charter.offering boundary (ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime modules
under ``src/specify_cli/`` to reach charter offering artifacts only through such
charter facades.

This file is a **pure re-export** module — no behaviour, no wrappers, no
type aliases.
"""

from charter.offering.versioning import (
    CURRENT_BUNDLE_SCHEMA_VERSION,
    BundleCompatibilityStatus,
    check_bundle_compatibility,
    get_bundle_schema_version,
    repair_v2_synthesis_manifest_defaults,
    run_migration,
)

__all__ = [
    "BundleCompatibilityStatus",
    "CURRENT_BUNDLE_SCHEMA_VERSION",
    "check_bundle_compatibility",
    "get_bundle_schema_version",
    "repair_v2_synthesis_manifest_defaults",
    "run_migration",
]
