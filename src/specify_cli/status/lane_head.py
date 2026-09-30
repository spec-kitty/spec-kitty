"""Best-effort lane-branch-head stamping for persisted status transitions.

FR-001 (mission ``mixed-lane-authorship-soundness-01M3M7Y0``, WP03): every
persisted lifecycle transition of a WP mapped to a non-planning execution
lane whose branch exists is stamped with ``policy_metadata["lane_head"]`` --
that lane branch's HEAD sha at persist time. The stamp lets a later
consolidation (D-2/D-3 of ``plan.md``) recover which commits a WP's
implementation/review windows actually covered, even after the lane branch
has moved on.

**Best-effort, never blocking (C-1):** :func:`probe_lane_head` never raises.
Any absence (no ``lanes.json``, unknown WP, planning lane, missing branch) or
git/read error resolves to ``None`` -- "no stamp" -- so a status transition is
never refused or delayed by this probe. "No ``lanes.json``", an unassigned WP
and the planning lane are silent (debug). A WP mapped to an execution lane whose
stamp could not be taken is logged at WARNING, naming the WP and the lane: a git
error, or a missing lane branch once implementation has started (another lane
branch of the mission exists). A missing branch before any lane branch exists
(``finalize-tasks`` seeding every WP) stays at debug -- that is the normal
pre-implementation state, not a lost stamp.

**Cold-import boundary:** this module's own top level imports nothing from
``mission_runtime``, ``specify_cli.lanes`` or ``specify_cli.core.git_ops`` --
those are imported function-locally inside :func:`_resolve_lane_head`, mirroring
``lanes/for_review_gate.py::_resolve_lane`` and the cold-import discipline
``tests/architectural/test_cold_import_status_boundary.py`` enforces on the
``status`` package. ``LANE_HEAD_KEY`` and :class:`LaneHeadProbe` are the only
symbols a pure caller (``status/transition_pipeline.py``) needs, and neither
requires those imports.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

logger = logging.getLogger(__name__)

#: The ``policy_metadata`` key a stamped lane-head sha is recorded under.
#: Re-exported from ``status/__init__.py`` (the facade) so
#: ``specify_cli.status.<submodule>`` imports stay forbidden outside the
#: ``status`` package (SR-2, ``tests/architectural/test_status_module_boundary.py``).
LANE_HEAD_KEY: Final = "lane_head"


class LaneHeadProbe(Protocol):
    """Callable shape ``prepare_transition`` accepts to stamp a lane head.

    Injected by the two composition shells (``status/emit.py``,
    ``coordination/status_transition.py``); the pure pipeline never
    constructs one itself.
    """

    def __call__(self, *, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> str | None: ...


def probe_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> str | None:
    """Return *wp_id*'s lane branch HEAD sha, or ``None`` when unavailable.

    ``None`` covers every non-exceptional "no stamp" case (no ``lanes.json``,
    corrupt ``lanes.json``, *wp_id* unassigned, the planning lane, or the
    lane branch not existing in *repo_root*) as well as any unexpected error
    -- this probe is best-effort and must never raise (C-1).

    Args:
        repo_root: The canonical repository root (never ``feature_dir`` --
            under coord topology that is the coordination worktree, which
            does not carry the lane branches).
        mission_slug: The mission whose ``lanes.json`` to resolve.
        wp_id: The work package to resolve a lane branch head for.
        owned: The validated owned-checkout fact of an owned transition
            (``TransitionRequest.owned``). When present the lane map is read
            from the fact's own ``mission_dir`` -- never re-derived from the
            repository root, whose copy of the mission may be stale
            (owned-checkout-lifecycle-authority single authority).
    """
    try:
        # Broad catch is intentional (C-1): this probe is best-effort and
        # must never raise into a status transition -- any lanes.json,
        # placement-seam, or git-invocation failure degrades to "no stamp".
        return _resolve_lane_head(repo_root=repo_root, mission_slug=mission_slug, wp_id=wp_id, owned=owned)
    except Exception:
        logger.debug(
            "probe_lane_head: could not resolve lane head for %s/%s under %s",
            mission_slug,
            wp_id,
            repo_root,
            exc_info=True,
        )
        return None


_NO_STAMP_WARNING = (
    "probe_lane_head: %s/%s is in execution lane %s but no lane-head stamp could be taken (%s); "
    "this transition carries no commit attribution, so a later mixed-lane consolidation may refuse"
)


def _branch_head(repo_root: Path, branch: str) -> str | None:
    """``refs/heads/<branch>`` sha, ``None`` when the branch does not exist."""
    from specify_cli.core.git_ops import run_command

    ret, out, _err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        return None
    sha = out.strip()
    return sha or None


def _warn_no_stamp(mission_slug: str, wp_id: str, lane_id: str, why: str) -> None:
    logger.warning(_NO_STAMP_WARNING, mission_slug, wp_id, lane_id, why)


def _resolve_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> str | None:
    """Unguarded lanes.json resolution; exceptions are the caller's (:func:`probe_lane_head`) to catch.

    Once the WP's execution lane is known, a git error or a missing branch is
    handled here (never raised) so it can be logged with the WP and the lane.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.lanes.compute import is_planning_lane, lane_created_branch
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    planning_dir = owned.mission_dir if owned is not None else placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    try:
        manifest = read_lanes_json(planning_dir)
    except CorruptLanesError:
        return None
    if manifest is None:
        return None
    lane = manifest.lane_for_wp(wp_id)
    if lane is None or is_planning_lane(lane):
        return None
    branch = lane_created_branch(manifest, lane.lane_id)
    try:
        sha = _branch_head(repo_root, branch)
    except Exception as exc:  # noqa: BLE001 — best-effort (C-1): a git error is logged, never raised
        _warn_no_stamp(mission_slug, wp_id, lane.lane_id, f"git error: {exc}")
        return None
    if sha is not None:
        return sha
    other_branches = (lane_created_branch(manifest, other.lane_id) for other in manifest.lanes if other.lane_id != lane.lane_id and not is_planning_lane(other))
    if any(_branch_head(repo_root, other) is not None for other in other_branches):
        _warn_no_stamp(mission_slug, wp_id, lane.lane_id, f"lane branch {branch} does not exist")
    else:
        logger.debug("probe_lane_head: %s/%s lane %s has no branch yet (pre-implementation)", mission_slug, wp_id, lane.lane_id)
    return None
