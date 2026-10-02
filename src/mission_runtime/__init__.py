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
``OwnedCheckout`` is on the root because the ``runtime`` and ``specify_cli``
layers both consume it as the validated ownership fact (ADR
2026-06-07-1; WP03 of owned-checkout-lifecycle-authority-01M3M2ZB amends it).

See ADR ``docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md``.
"""

from __future__ import annotations

from typing import Any

from mission_runtime.context import (
    CommitTarget,
    MissionContext,
    MissionExecutionContext,
    MissionTopology,
    TopologyManifestMismatch,
    assert_topology_matches_manifest,
    classify_topology,
    is_single_branch,
    routes_through_coordination,
    unstamped_runtime_topology,
)
from mission_runtime.artifacts import (
    MissionArtifactKind,
    TopologySurface,
    _MISSION_FILE_KIND_BY_BASENAME,
    is_primary_artifact_kind,
    kind_for_mission_file,
    kind_is_coordination_residue,
)

# owned-checkout-lifecycle-authority WP12 (FR-025): the one claim-commit authority
# every review path shares; on the package root because MR-1/MR-2 forbid
# submodule imports from outside the package.
from mission_runtime.claim_commit import ClaimCommitUnresolved, claim_commit_for_wp
from mission_runtime.checkout_identity import (
    CheckoutIdentityError,
    enforce_checkout_identity,
)
from mission_runtime.identity import handle_names_mission, mid8_from_slug, resolve_mid8
from mission_runtime.resolution import (
    ActionContextError,
    IssueMatrixRefReadError,
    PlacementSeam,
    coord_read_dir_for,
    declared_read_surface,
    mission_context_for,
    placement_seam,
    resolve_action_context,
    resolve_artifact_surface,
    resolve_create_time_write_target,
    resolve_placement_only,
    resolve_single_branch_write_ref,
    resolve_topology,
    single_branch_write_ref,
)

# owned-checkout-lifecycle-authority WP01 (FR-001/C-003): the validated ownership
# fact that every owned read/write consumes, exported here because runtime and
# specify_cli layers may only import it from the package root (MR-1/MR-2).
from mission_runtime.owned_checkout import (
    OwnedCheckout,
    OwnedRefusalCode,
)
from mission_runtime.issue_matrix_partition import resolve_issue_matrix_partition
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

# coord-artifact-single-home-01M3V4BE WP03 (FR-003a/FR-004): the write-location
# accessor's value objects. MR-1/MR-2 forbid submodule imports, so both live on
# the package root -- ``specify_cli.coordination.coord_seed`` (and WP04's
# ``PlacementSeam.write_dir``) import them from here only.
from mission_runtime.write_location import (
    Establishment,
    SeedReport,
    WriteLocation,
)

__all__ = [
    "ActionContextError",
    "CheckoutIdentityError",
    "ClaimCommitUnresolved",
    "CommitTarget",
    # coord-artifact-single-home-01M3V4BE WP03: the write-location accessor's
    # ``Establishment`` outcome enum (``write_location.py``).
    "Establishment",
    # #5222 (F2): promoted onto the package root so review/doctor consumers of
    # ``read_issue_matrix_ref_content`` (via ``resolve_issue_matrix_partition``)
    # can catch it by type instead of a bare ``Exception`` -- it was reachable
    # only via the import-forbidden ``mission_runtime.resolution`` submodule
    # before (MR-1/MR-2).
    "IssueMatrixRefReadError",
    "MissionArtifactKind",
    "MissionContext",
    "MissionExecutionContext",
    "MissionResolver",
    "MissionTopology",
    "OwnedCheckout",
    "OwnedRefusalCode",
    "PlacementSeam",
    "ReadDegradeStrategy",
    "ReadDirDecision",
    # coord-artifact-single-home-01M3V4BE WP03: the seed-operation result value
    # object (``write_location.py``) -- referenced by ``WriteLocation.seed``.
    "SeedReport",
    "TopologyManifestMismatch",
    "TopologySurface",
    # coord-artifact-single-home-01M3V4BE WP03: the write-location accessor's
    # result value object (``write_location.py``) -- the public face of
    # ``establish_coord_write_location`` / the future ``PlacementSeam.write_dir``.
    "WriteLocation",
    # coord-read-fail-closed landing (#5001): the basename->kind classifier map
    # itself, re-exported so ``specify_cli.coordination.surface_resolver`` can
    # invert it (kind -> basenames) without reaching into the
    # ``mission_runtime.artifacts`` submodule directly (MR-1/MR-2).
    "_MISSION_FILE_KIND_BY_BASENAME",
    "assert_coord_write_materialized",
    "assert_topology_matches_manifest",
    # owned-checkout-lifecycle-authority WP07 review cycle 2 MEDIUM: the ONE
    # canonical "does this legacy bare root name the same checkout as this
    # validated fact" predicate -- see its own docstring in owned_checkout.py.
    "claim_commit_for_wp",
    "classify_topology",
    "coord_read_dir_for",
    "declared_read_surface",
    "enforce_checkout_identity",
    "handle_names_mission",
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
    # issue-matrix-partition-integrity (#5171/#4943): the single two-partition
    # split every issue-matrix gate consumes.
    "resolve_issue_matrix_partition",
    "resolve_mid8",
    "resolve_placement_only",
    "resolve_read_dir_or_degrade",
    "resolve_single_branch_write_ref",
    "resolve_topology",
    "resolve_write_target_or_degrade",
    "routes_through_coordination",
    "single_branch_write_ref",
    "unstamped_runtime_topology",
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
