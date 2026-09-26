"""Charter facade for built-in doctrine pack path resolution.

This module is the charter-layer proxy for runtime callers that resolve the
built-in doctrine pack root / per-kind directory. The runtime → charter →
doctrine boundary (ADR 2026-03-27-1, re-affirmed by mission
``doctrine-public-api-surface-01KZPDSR``) requires runtime modules under
``src/specify_cli/`` to reach doctrine artifacts only through charter facades.

``charter.offering.pack_paths`` is dispositioned ``FACADE-ONLY`` in the WP01 census
(fronted by a clean charter door but not part of the wheel's public contract).
The reached resolution functions and their typed ``PackRootNotFound`` failure
are re-exported here (from ``charter.offering.pack_paths``, not ``charter.offering.api``).

This file is a **pure re-export** module — no behaviour, no wrappers, no type
aliases. Object identity is preserved (``charter.pack_paths.built_in_root is
charter.offering.pack_paths.built_in_root``), enforced by
``tests/architectural/test_charter_facades_reexport_doctrine.py``.
"""

from charter.offering.pack_paths import PackRootNotFound, built_in_dir, built_in_root

__all__ = [
    "PackRootNotFound",
    "built_in_dir",
    "built_in_root",
]
