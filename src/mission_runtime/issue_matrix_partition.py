"""Shared ISSUE_MATRIX two-partition split helper (IC-shared, WP02).

Mission ``issue-matrix-partition-integrity-01M3H10A`` (FR-005, NFR-001, C-001).

Factors the ``(primary_discovery_dir, coord_matrix_source)`` resolution into
ONE helper so review (WP03) and merge (WP04) consumers call the SAME split
instead of re-authoring it three times (MINOR-6). ``status.doctor.
check_issue_matrix`` is the reference shape this generalizes.

Dispatch (thin composition of the seam -- NOT a second resolution authority,
C-001):

1. ``primary_discovery_dir`` -- the PRIMARY-partition mission dir, resolved
   via :func:`~mission_runtime.resolution.resolve_artifact_surface` for a
   PRIMARY-partition kind (declared-PRIMARY for every topology, AH-1).
2. On a coord-less topology (``SINGLE_BRANCH`` / ``LANES``), the matrix ALSO
   resolves to PRIMARY -- branch-flat parity (contract guarantee #2):
   ``coord_matrix_source`` is ``primary_discovery_dir`` itself, byte-for-byte
   identical to today. No coord probe is attempted.
3. On a coord-routing topology, try the MATERIALIZED coord dir via
   :func:`~mission_runtime.resolution.coord_read_dir_for`. When it resolves,
   that ``Path`` IS ``coord_matrix_source``.
4. When step 3 returns ``None`` (the coordination worktree is unmaterialized
   or has been consolidated away -- there is no on-disk dir to read), dispatch
   to WP01's standalone ref-content read
   (:func:`~mission_runtime.resolution.read_issue_matrix_ref_content`) and
   return its ``str`` content as ``coord_matrix_source``. The ``None`` is
   NEVER allowed to fall back to ``primary_discovery_dir`` -- that silent
   substitution is the #5171 residue bug this helper exists to close.

``coord_matrix_source`` is therefore always either a ``Path`` (materialized
dir, or the coord-less parity case) or a ``str`` (post-consolidation ref
content) -- never ``None``. Callers dispatch on ``isinstance(..., str)`` to
pick the content-source arm of a reader (:mod:`specify_cli.tasks.
issue_matrix_migration`, :mod:`specify_cli.cli.commands.review._issue_matrix`)
instead of its dir-based fast path.
"""

from __future__ import annotations

from pathlib import Path

from mission_runtime.artifacts import MissionArtifactKind
from mission_runtime.context import routes_through_coordination
from mission_runtime.mission_resolver_port import MissionResolver
from mission_runtime.resolution import (
    coord_read_dir_for,
    read_issue_matrix_ref_content,
    resolve_artifact_surface,
    resolve_topology,
)

__all__ = ["resolve_issue_matrix_partition"]


def resolve_issue_matrix_partition(
    repo_root: Path,
    mission_slug: str,
    *,
    resolver: MissionResolver | None = None,
) -> tuple[Path, Path | str]:
    """Resolve the ``(primary_discovery_dir, coord_matrix_source)`` split.

    Args:
        repo_root: Repository root (may be a worktree; canonicalized
            internally by the delegated resolvers, so the result is
            CWD-invariant).
        mission_slug: The mission directory name / slug (any canonicalizable
            handle).
        resolver: Optional :class:`MissionResolver` threaded through the
            delegated resolvers. ``None`` preserves historical behaviour.

    Returns:
        A ``(primary_discovery_dir, coord_matrix_source)`` pair. Reference
        discovery (gating issue numbers, etc.) always reads
        ``primary_discovery_dir``; matrix verdicts read
        ``coord_matrix_source`` (see module docstring for the dispatch
        rule).

    Raises:
        ActionContextError: When ``mission_slug`` cannot be resolved at all
            (propagated from the delegated resolvers -- no silent
            fallback), or when a PUBLISHED mission's consolidated content is
            not present on the current checkout.
        IssueMatrixRefReadError: When the post-consolidation ref-content read
            (step 4 above) fails closed -- a deleted ref, a content-probe
            error, or empty authored content (see
            :func:`~mission_runtime.resolution.read_issue_matrix_ref_content`).
    """
    primary_discovery_dir = resolve_artifact_surface(
        repo_root,
        mission_slug,
        MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    ).path

    topology = resolve_topology(repo_root, mission_slug, resolver=resolver)
    if not routes_through_coordination(topology):
        return primary_discovery_dir, primary_discovery_dir

    coord_dir = coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX)
    if coord_dir is not None:
        return primary_discovery_dir, coord_dir

    content: str = read_issue_matrix_ref_content(repo_root, mission_slug, resolver=resolver)
    return primary_discovery_dir, content
