"""Charter facade for template-catalog types (FR-006, FR-007).

This module is the charter-layer proxy for runtime callers that need
``discover_templates``, ``TemplateRef``, and ``TierRoot`` from
``charter.offering.template_catalog``. The runtime → charter → charter.offering boundary
(ADR 2026-03-27-1, tightened by mission
``charter-mediated-doctrine-selection-01KRTZCA``) requires runtime modules
under ``src/specify_cli/`` to reach charter offering artifacts only through charter
facades.

This file is a **pure re-export** module — no behaviour, no wrappers, no
type aliases. Identity is preserved (``charter.template_catalog.TemplateRef is
charter.offering.template_catalog.TemplateRef``).

Mirrors the pattern of :mod:`charter.profiles` and :mod:`charter.resolution`.
"""

from charter.offering.template_catalog import (
    TemplateRef,
    TierRoot,
    discover_templates,
    resolve_template_by_id,
)

__all__ = [
    "discover_templates",
    "resolve_template_by_id",
    "TemplateRef",
    "TierRoot",
]
