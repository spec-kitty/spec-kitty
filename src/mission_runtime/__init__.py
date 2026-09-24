"""``mission_runtime`` — the canonical execution-state surface.

This umbrella package is the single, screaming home for execution-state
resolution: given a mission (and optional work package), it produces a fully
resolved, CWD-invariant :class:`MissionExecutionContext`. Consumers import **only** from
this package root; internal submodules (``context``, ``resolution``) are
import-forbidden from outside the package and enforced by
``tests/architectural/test_mission_runtime_surface.py`` (FR-005).

The public API is expressed over context objects, never over path fragments —
callers receive a resolved context and never reconstruct the mission-spec
directory from ``main_repo_root`` + the specs dir name + ``mission_slug``
themselves (FR-009).

WP02 stood up the package empty-but-registered (lean ``__all__`` over stub
symbols + layer-guard registration); WP03 relocated the hardened resolver here
and removed the old ``specify_cli.core.execution_context`` module outright (all
callers were migrated to this package root). A few historical command-oriented
names remain as compatibility attributes for first-party callers, but they are
not part of the public ``__all__`` surface.

The root surface is exactly what ``src/`` consumers outside the package import
(pinned by ``tests/architectural/test_mission_runtime_surface.py``). The
value-object internals -- the context fragments, ``MissionArtifactContext``,
``MissionArtifactHome`` / ``artifact_home_for``, and the ``ResolvedSurface`` /
``SurfaceLocations`` / ``translate_surface`` translation trio -- were demoted
off the root in mission dead-port-disposition-01M1TZVN (FR-014): nothing
outside the package imported them, so tests reach them from their defining
submodule instead of widening the public surface for test convenience.

See ADR ``docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md``.
"""
from __future__ import annotations

from typing import Any

from mission_runtime.context import (
    CommitTarget,
    MissionContext,
    MissionExecutionContext,
    MissionTopology,
    classify_topology,
    is_single_branch,
    routes_through_coordination,
)
from mission_runtime.artifacts import (
    MissionArtifactKind,
    TopologySurface,
    _MISSION_FILE_KIND_BY_BASENAME,
    is_primary_artifact_kind,
    kind_for_mission_file,
    kind_is_coordination_residue,
)
from mission_runtime.checkout_identity import (
    CheckoutIdentityError,
    enforce_checkout_identity,
)
from mission_runtime.identity import mid8_from_slug, resolve_mid8
from mission_runtime.resolution import (
    ActionContextError,
    PlacementSeam,
    coord_read_dir_for,
    declared_read_surface,
    mission_context_for,
    placement_seam,
    resolve_action_context,
    resolve_artifact_surface,
    resolve_create_time_write_target,
    resolve_placement_only,
    resolve_topology,
)
from mission_runtime.mission_resolver_port import MissionResolver
from mission_runtime.read_dir_degrade import (
    ReadDegradeStrategy,
    ReadDirDecision,
    resolve_read_dir_or_degrade,
)
from mission_runtime.write_target_degrade import (
    assert_coord_write_materialized,
    resolve_write_target_or_degrade,
)

__all__ = [
    "ActionContextError",
    "CheckoutIdentityError",
    "CommitTarget",
    "MissionArtifactKind",
    "MissionContext",
    "MissionExecutionContext",
    "MissionResolver",
    "MissionTopology",
    "PlacementSeam",
    "ReadDegradeStrategy",
    "ReadDirDecision",
    "TopologySurface",
    # coord-read-fail-closed landing (#5001): the basename->kind classifier map
    # itself, re-exported so ``specify_cli.coordination.surface_resolver`` can
    # invert it (kind -> basenames) without reaching into the
    # ``mission_runtime.artifacts`` submodule directly (MR-1/MR-2).
    "_MISSION_FILE_KIND_BY_BASENAME",
    "assert_coord_write_materialized",
    "classify_topology",
    "coord_read_dir_for",
    "declared_read_surface",
    "enforce_checkout_identity",
    "is_primary_artifact_kind",
    # owned-ssot-3862 item A: the SINGLE enum-based single_branch predicate the
    # owned-placement arms and the owned checkout preflight dispose against.
    "is_single_branch",
    "kind_for_mission_file",
    "kind_is_coordination_residue",
    "mid8_from_slug",
    "mission_context_for",
    "placement_seam",
    "resolve_action_context",
    "resolve_artifact_surface",
    "resolve_create_time_write_target",
    "resolve_mid8",
    "resolve_placement_only",
    "resolve_read_dir_or_degrade",
    "resolve_topology",
    "resolve_write_target_or_degrade",
    "routes_through_coordination",
]

_COMPAT_ATTRS = frozenset(
    {
        "ActionName",
        "ACTION_NAMES",
        "_resolve_mission_slug",
    }
)


def __getattr__(name: str) -> Any:
    """Resolve historical first-party names without widening ``__all__``."""
    if name not in _COMPAT_ATTRS:
        raise AttributeError(name)
    from mission_runtime import resolution

    return getattr(resolution, name)
