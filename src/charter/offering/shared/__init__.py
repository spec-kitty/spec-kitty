"""Shared utilities and primitive types for the doctrine package.

Provides cross-cutting concerns used by multiple artifact subpackages:

- :class:`~charter.offering.shared.schema_utils.SchemaUtilities` — cached JSON Schema loading
- :exc:`~charter.offering.shared.exceptions.DoctrineArtifactLoadError` — load failure signal
- :exc:`~charter.offering.shared.exceptions.DoctrineResolutionCycleError` — cycle detection signal

Glossary primitive types (canonical definitions in kernel, re-exported here):

- :class:`~kernel.glossary_types.ConflictType`
- :class:`~kernel.glossary_types.GlossaryScope`
- :class:`~kernel.glossary_types.SenseRef`
- :class:`~kernel.glossary_types.Severity`
- :class:`~kernel.glossary_types.TermSurface`

These five re-exports are the only src/ importers of their
``kernel.glossary_types`` definitions; dropping them is a follow-up decision about
those kernel duplicates (dead-code review 2026-09-30).
"""

from __future__ import annotations

from .exceptions import DoctrineArtifactLoadError, DoctrineResolutionCycleError
from .schema_utils import SchemaUtilities
from kernel.glossary_types import (
    ConflictType,
    GlossaryScope,
    SenseRef,
    Severity,
    TermSurface,
)

__all__ = [
    "ConflictType",
    "DoctrineArtifactLoadError",
    "DoctrineResolutionCycleError",
    "GlossaryScope",
    "SchemaUtilities",
    "SenseRef",
    "Severity",
    "TermSurface",
]
