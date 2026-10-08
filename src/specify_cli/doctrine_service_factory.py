"""Single construction seam for activation-aware doctrine services (FR-010).

This module exposes :func:`build_active_charter_service`, the one
place profile surfaces (``profile list``/``profile show``, ``charter context
--include``) should call to obtain a :class:`charter.activation.resolver.ActiveCharterService`
that already has per-kind charter activation filters applied.

FR-008 unification (charter-sole-door-bypass-closure-01KZ3WAA WP01): this
function is now a **thin re-export** of the single canonical builder,
:func:`charter.activation.active_charter_service_builder.build_active_charter_service`
(C-001 — one factory, constructed by exactly one unified builder). Prior to
this mission, this module and ``charter.activation.active_charter_service_builder`` each held
an independent implementation that silently diverged on two axes
(``active_languages`` computation and ``org_roots`` self-resolution); see the
charter-layer module's docstring for the resolved behaviour. This module is
kept (rather than deleted and every caller repointed at ``charter.*``
directly) because it is the layer-correct home for the public entry point:
``specify_cli.*`` may import ``charter.*``, but the reverse is forbidden
(C-005), so callers already anchored in ``specify_cli.*`` continue to import
from here.

Layer rule (C-005)
------------------
This module lives in ``specify_cli.*`` precisely because it imports from
``charter.*`` — the allowed dependency direction is
``specify_cli → charter → doctrine``.  It must **not** be placed inside
``charter.*`` or ``doctrine.*``, which are forbidden from importing
``specify_cli``.  The activation wrapper itself is **reused** from
``charter.activation.resolver`` (C-003); it is never re-implemented here.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from charter.activation.resolver import ActiveCharterService

__all__ = ["build_active_charter_service"]


def build_active_charter_service(
    repo_root: Path,
) -> ActiveCharterService:
    """Build an activation-filtered doctrine service for ``repo_root``.

    Thin re-export of
    :func:`charter.activation.active_charter_service_builder.build_active_charter_service`
    — see that function's docstring for the full construction contract
    (built-in + project + self-resolved org packs, ``active_languages``
    always computed, wrapped with a :class:`~charter.activation.pack_context.PackContext`
    built from ``.kittify/config.yaml``).

    The returned wrapper applies the three-state ``activated_agent_profiles``
    contract on its ``.agent_profiles`` property (and the equivalent filters
    for the other eight gated properties):

    * key absent from config → all built-in artifacts are available;
    * explicit empty set → nothing of that kind is available;
    * explicit set of IDs → only those IDs are available.

    Parameters
    ----------
    repo_root:
        Repository root containing ``.kittify/config.yaml``.

    Returns
    -------
    charter.activation.resolver.ActiveCharterService
        The activation-aware wrapper around the inner doctrine service.
    """
    from charter.activation.active_charter_service_builder import (
        build_active_charter_service as _canonical_builder,
    )

    return _canonical_builder(repo_root)
