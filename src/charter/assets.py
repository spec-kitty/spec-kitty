"""Charter facade for the charter offering's asset-resolution surface.

This module is the charter-layer proxy for runtime callers that need the asset
repository, its sidecar manifest model, and the typed (fail-closed) error
hierarchy. The runtime → charter → charter.offering boundary (ADR 2026-03-27-1,
re-affirmed by mission ``doctrine-public-api-surface-01KZPDSR``) requires runtime
modules under ``src/specify_cli/`` to reach charter offering artifacts only through
charter facades.

These symbols are dispositioned ``PUBLIC`` in the WP01 census
(``charter.offering.assets.repository`` / ``charter.offering.assets.models``), so they are
re-exported from the curated public surface ``charter.offering.api`` (not the origin
submodules directly). This gives the PUBLIC wheel symbols a live in-repo caller —
the from-``charter.offering.api`` wiring the no-dead-symbol gate and the strict T007
live-caller assertion depend on. Object identity is unchanged:
``charter.assets.AssetRepository is charter.offering.api.AssetRepository is
charter.offering.assets.repository.AssetRepository``.

This file is a **pure re-export** module — no behaviour, no wrappers, no type
aliases. Enforced by
``tests/architectural/test_charter_facades_reexport_offering.py``.
"""

from charter.offering.api import (
    AssetManifest,
    AssetNotFoundError,
    AssetPathEscapeError,
    AssetRepository,
    AssetResolutionError,
)

__all__ = [
    "AssetManifest",
    "AssetNotFoundError",
    "AssetPathEscapeError",
    "AssetRepository",
    "AssetResolutionError",
]
