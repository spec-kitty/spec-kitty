"""Charter facade for the glossary-pack domain model.

This module is the charter-layer proxy for runtime callers that need the
``GlossaryPack`` domain entity. The runtime → charter → charter.offering boundary
(ADR 2026-03-27-1, re-affirmed by mission
``doctrine-public-api-surface-01KZPDSR``) requires runtime modules under
``src/specify_cli/`` to reach charter offering artifacts only through charter facades.

``charter.offering.glossary_packs`` is dispositioned ``FACADE-ONLY`` in the WP01 census
(fronted by a clean charter door but not part of the wheel's public contract),
so ``GlossaryPack`` is re-exported from the ``charter.offering.glossary_packs`` package
surface (not from ``charter.offering.api``).

This file is a **pure re-export** module — no behaviour, no wrappers, no type
aliases. Object identity is preserved (``charter.glossary_packs.GlossaryPack is
charter.offering.glossary_packs.GlossaryPack``), enforced by
``tests/architectural/test_charter_facades_reexport_doctrine.py``.
"""

from charter.offering.glossary_packs import GlossaryPack

__all__ = [
    "GlossaryPack",
]
