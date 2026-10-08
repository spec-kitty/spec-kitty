"""Legacy-mission resolution helpers for the bookkeeping transaction.

Extracted from ``transaction.py`` (WP08 campsite split, NFR-007) so the
coordination-branch write chokepoint lands in a smaller module. The move is
behaviour-free; ``transaction.py`` re-exports every public name below so
existing ``from specify_cli.coordination.transaction import _is_legacy_mission``
(and friends) imports keep resolving to these same functions.

Missions created before the coordination-branch topology landed do not carry
``coordination_branch`` in their ``meta.json``.  For those, the bookkeeping
write target is the operator's current LANE worktree + its checked-out branch.
Every other invariant of the transaction (pre-flight policy gate, lock, surgical
truncate rollback, outbound deferral) applies uniformly.  Only ``worktree_root``
and ``destination_ref`` differ.

Spec source: FR-017, FR-027, SC-11, C-001, C-005 (WP08 T035–T036).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.coordination.transaction_errors import (
    BookkeepingError,
    BookkeepingLegacyResolutionFailed,
)
from specify_cli.lanes.branch_naming import (
    coord_mission_dir_name as _seam_coord_mission_dir_name,
)
from specify_cli.mission_metadata import load_meta
from specify_cli.status.mission_write import transaction_lock_key as _seam_transaction_lock_key

logger = logging.getLogger(__name__)


def _mission_specs_dir_name(mission_slug: str, mid8: str) -> str:
    """Return the kitty-specs sub-directory name for this mission.

    Delegates to the seam's VERBATIM coordination primitive
    (``lanes.branch_naming.coord_mission_dir_name``, FR-010) so there is exactly
    ONE algorithm for the coordination ``<slug>-<mid8>`` grammar, reconstructed
    byte-identical to the prior hand-rolled body. This transaction path consumes
    ``meta.json.mission_slug`` VERBATIM (including any legacy ``NNN-`` prefix); the
    seam primitive does NOT strip it, so the kitty-specs dir matches the on-disk
    coord target (#1589). The canonical, NNN-stripping ``mission_dir_name`` is NOT
    used here.
    """
    return _seam_coord_mission_dir_name(mission_slug, mid8=mid8)


def _transaction_lock_key(repo_root: Path, mission_slug: str, mid8: str) -> str:
    """Return the Mission write-lock key the bookkeeping transaction takes.

    ``status.mission_write.transaction_lock_key``: the routing decision of
    ``mission_lock_key``, so the transaction and every door resolve one lock file
    (plan A1). Never the trailing-dash ``<slug>-`` that :func:`_mission_specs_dir_name`
    keeps for path composition (plan A3).
    """
    return _seam_transaction_lock_key(repo_root, mission_slug, mid8)


def _checkout_mission_dir(surface_root: Path, mission_slug: str, mid8: str) -> Path:
    """Return ``<surface_root>/kitty-specs/<slug>-<mid8>`` for a NON-coordination checkout.

    Only for the checkouts a transaction anchors on without a coordination
    write location: the legacy LANE worktree (C-008) and the primary checkout
    (the coordination-less and ``commit_to_primary_target`` arms). The
    coordination arm NEVER composes through this helper -- it carries the
    ``WriteLocation.path`` that ``write_dir`` already returned (FR-014).
    """
    mission_dir: Path = surface_root / KITTY_SPECS_DIR / _mission_specs_dir_name(mission_slug, mid8)
    return mission_dir


def _validate_safe_segment(name: str, value: str) -> str:
    """Return a single safe path segment or raise a bookkeeping error.

    Delegates to the canonical ``assert_safe_path_segment`` (FR-001 / WP01) and
    re-raises any ``ValueError`` as a ``BookkeepingError`` to preserve the call-site
    contract (C-001: migrate, don't wrap — no parallel mechanism).
    """
    try:
        return assert_safe_path_segment(value)
    except ValueError as exc:
        raise BookkeepingError(f"{name} is not a safe path segment: {exc}") from exc


def _load_mission_meta(
    repo_root: Path,
    mission_slug: str,
    mid8: str,
) -> dict[str, Any] | None:
    """Read this mission's ``meta.json`` from its kitty-specs dir, tolerantly.

    WP08 T042 micro-cleanup: the three legacy predicates below each computed the
    same ``kitty-specs/<slug>-<mid8>/`` feature dir and issued the same
    ``load_meta(..., on_malformed="none")`` read. Folding that redundant read into
    ONE helper is behaviour-preserving — every caller still resolves the identical
    path and the identical malformed-tolerant contract, so a malformed
    ``meta.json`` is treated as new-topology rather than repaired here.
    """
    return load_meta(_checkout_mission_dir(repo_root, mission_slug, mid8), on_malformed="none")


def _is_legacy_mission(repo_root: Path, mission_slug: str, mid8: str) -> bool:
    """Return ``True`` when ``meta.json`` exists and lacks ``coordination_branch``.

    Detection rule (per WP08 reviewer guidance):

    * ``meta.json`` is **present** but does not carry the
      ``coordination_branch`` key → legacy mission.
    * ``meta.json`` is **absent** → treat as new-topology mission.  This
      is the case for synthetic test fixtures and very early mission
      lifecycle states; defaulting to new-topology preserves the
      existing test surface and matches the contract that any
      well-formed post-WP03 mission has its meta written before the
      first ``acquire()``.
    * A missing/manually deleted coord branch does **not** make a
      mission legacy — FR-018 idempotency re-creates it.  Only the
      ``meta.json`` field is consulted.
    """
    # A malformed meta.json is not our problem to repair here; if a caller
    # hits this they will surface it through other validators. Treat as
    # new-topology so we do not silently route legacy.
    data = _load_mission_meta(repo_root, mission_slug, mid8)
    if data is None:
        return False
    return not data.get("coordination_branch")


def _coordination_branch_from_meta(
    repo_root: Path,
    mission_slug: str,
    mid8: str,
) -> str | None:
    """Return explicit ``coordination_branch`` from meta.json, if trustworthy."""
    data = _load_mission_meta(repo_root, mission_slug, mid8)
    if data is None:
        return None
    raw_branch = data.get("coordination_branch")
    if not isinstance(raw_branch, str):
        return None
    branch = raw_branch.strip()
    return branch or None


def _warrants_legacy_warning(repo_root: Path, mission_slug: str, mid8: str) -> bool:
    """Return ``True`` when the once-per-mission legacy-topology warning
    should fire (#2351).

    Deliberately SEPARATE from :func:`_is_legacy_mission` (C-005): that
    predicate keys on ``coordination_branch`` absence alone and continues to
    drive worktree routing (below) and write-contract selection unchanged.
    This classifier additionally reads the stored ``MissionTopology`` (via
    the non-deriving :func:`stored_topology_from_meta`, C-001) and the
    ``flattened`` provenance flag, so a mission whose coordination-less shape
    was **chosen at creation** (``single_branch``/``lanes``) or that is
    ``flattened`` does not draw a warning meant for genuinely pre-SSOT
    missions (FR-001..FR-004).

    Warn iff ``coordination_branch`` is falsy AND the stored topology is
    ``None`` (absent or malformed — the reader's fail-closed default, so an
    unrecognised value warns rather than silently passing) AND the mission
    is not ``flattened``.
    """
    meta = _load_mission_meta(repo_root, mission_slug, mid8)
    if meta is None:
        return False
    # belt-and-suspenders: call site sits inside `if legacy_mode:` (which requires
    # no coordination_branch), but guard is kept for future direct callers.
    if meta.get("coordination_branch"):
        return False
    if meta.get("flattened"):
        return False
    from specify_cli.missions._read_path_resolver import stored_topology_from_meta

    return stored_topology_from_meta(meta) is None


def _resolve_legacy_lane_destination(
    _repo_root: Path,
) -> tuple[Path, str]:
    """Resolve the operator's current lane worktree + its checked-out branch.

    Returns ``(worktree_root, branch_short_name)``.

    Algorithm:

    1. Take ``Path.cwd()`` and walk ancestors until a ``.git`` entry is
       found.  A ``.git`` *file* indicates a linked worktree; a ``.git``
       *directory* indicates the main checkout.  Either is acceptable as
       a legacy write target — pre-coord-topology bookkeeping ran in
       whichever checkout the operator stood in.
    2. Read ``git symbolic-ref HEAD`` from that worktree to obtain the
       branch name and strip ``refs/heads/`` so it is comparable to the
       short-form refs used elsewhere in the transaction.

    Raises :class:`BookkeepingLegacyResolutionFailed` when no ``.git``
    marker is found or HEAD is detached.
    """
    cwd = Path.cwd().resolve()
    worktree_root: Path | None = None
    for ancestor in [cwd, *cwd.parents]:
        marker = ancestor / ".git"
        if marker.exists():
            worktree_root = ancestor
            break
    if worktree_root is None:
        raise BookkeepingLegacyResolutionFailed(
            f"Legacy mission detected but no git worktree found above {cwd}",
        )
    try:
        head = subprocess.check_output(
            ["git", "-C", str(worktree_root), "symbolic-ref", "HEAD"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise BookkeepingLegacyResolutionFailed(
            f"Legacy mission detected at {worktree_root} but HEAD is detached or symbolic-ref failed: {exc.stderr or exc}"
        ) from exc
    branch = head.removeprefix("refs/heads/")
    if not branch:
        raise BookkeepingLegacyResolutionFailed(f"Legacy mission detected at {worktree_root} but HEAD resolves to an empty branch name")
    # Defensive: discourage running legacy bookkeeping against repo_root
    # if that happens to be the main checkout sitting on `main`.  We do
    # not refuse here — the pre-flight policy gate in `acquire()` will
    # catch protected-ref writes via the same machinery used for the
    # coord topology (SC-11 behaviour parity).
    return worktree_root, branch


def _legacy_warning_marker_path(repo_root: Path, mission_id: str) -> Path:
    """Path of the per-mission once-only deprecation warning marker."""
    safe_mission_id = _validate_safe_segment("mission_id", mission_id)
    return repo_root / ".kittify" / f"legacy-warning-shown-{safe_mission_id}"


def _emit_legacy_warning_once(
    repo_root: Path,
    mission_id: str,
    mission_slug: str,
) -> None:
    """Emit a one-line stderr deprecation warning, at most once per mission.

    Idempotent: subsequent invocations within the same project see the
    marker file and no-op.  The marker lives under ``.kittify/`` so it
    is project-scoped (per-mission ID) and survives across invocations.
    """
    marker = _legacy_warning_marker_path(repo_root, mission_id)
    if marker.exists():
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError as exc:
        # Marker write failure is non-fatal: we still emit the warning
        # (worst case: warning repeats next invocation).
        logger.debug(
            "BookkeepingTransaction: failed to write legacy-warning marker %s: %s",
            marker,
            exc,
        )
    print(
        f"warning: mission {mission_slug!r} uses the legacy topology "
        f"(no coordination branch). New atomicity invariants apply, "
        f"but consider migrating: see "
        f"docs/migrations/legacy-to-coordination.md "
        f"or run `spec-kitty migrate backfill-topology` to persist the "
        f"stored shape.",
        file=sys.stderr,
    )
