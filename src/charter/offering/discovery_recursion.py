"""Single authority for org/project overlay recursion (C-001, C-006).

Both the loader (:mod:`charter.offering.base`, :mod:`charter.offering.agent_profiles.repository`)
and the charter-activation resolver (:mod:`charter.activation.kind_vocabulary`) read this
seam so recursion cannot silently diverge per kind — the structural root cause of
the org/project under-loading defects (#3490, #3426).

Recursion is **unconditional** (C-001): org/project overlay discovery is
recursive for every kind, matching the built-in tier's ``rglob``. This module is
the single derivation/parity surface, **not** a per-kind toggle — no kind is ever
configured non-recursive. The per-kind function signature exists so the resolver
(which already carries a per-kind ``ArtifactKind`` in scope) and the loader call
it uniformly, and so the parity/totality gate can falsify a reintroduced
divergence per kind.

Layering (C-006): this module lives in ``charter.offering`` and imports only
:mod:`charter.offering.artifact_kinds` (itself zero-dependency). ``charter`` imports
*down* into it; it never imports ``charter`` or ``specify_cli``.

Kind-specificity (C-002) is the caller's concern: callers scan with the kind's
own glob (``ArtifactKind.glob_pattern``, e.g. ``*.tactic.yaml``), so a recursive
walk never captures ``.provenance/*.yaml`` sidecars or ``.md`` files.
"""

from __future__ import annotations

from charter.offering.artifact_kinds import ArtifactKind

__all__ = [
    "overlay_scan_is_recursive",
]

#: The kinds whose org/project overlay discovery is recursive. Derived as the
#: whole :class:`~charter.offering.artifact_kinds.ArtifactKind` universe (C-001:
#: unconditional), never hand-listed. The public seam is
#: :func:`overlay_scan_is_recursive`, which binds both loader and resolver
#: recursion to this set; the frozenset itself is a module-level derivation
#: surface asserted by the parity gate (``tests/charter_offering/test_discovery_recursion.py``)
#: but consumed by no other ``src/`` module, so it is deliberately **not** in
#: ``__all__`` — exporting an unimported symbol would trip the dead-symbol gate.
RECURSIVE_OVERLAY_KINDS: frozenset[ArtifactKind] = frozenset(ArtifactKind)


def overlay_scan_is_recursive(kind: ArtifactKind | None) -> bool:
    """Return whether org/project overlay discovery recurses for *kind*.

    ``True`` for every kind (C-001). The single authority both the loader and
    the charter-activation resolver consult, so the two cannot disagree per
    kind by construction (FR-002).

    *kind* is ``None`` when a caller cannot map its scan to a canonical
    :class:`ArtifactKind` — e.g. a :class:`~charter.offering.base.BaseArtifactRepository`
    subclass (or test stub) whose glob is not one of the canonical
    ``ArtifactKind.glob_pattern`` values. Such a scan still recurses: the policy
    is uniform (C-001), so an unmapped scan gets the same unconditional
    recursion rather than a silent non-recursive fallback.
    """
    if kind is None:
        return True
    return kind in RECURSIVE_OVERLAY_KINDS
