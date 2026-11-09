"""Best-effort lane-branch-head stamping for persisted status transitions.

FR-001 (mission ``mixed-lane-authorship-soundness-01M3M7Y0``, WP03): every
persisted lifecycle transition of a WP mapped to a non-planning execution
lane whose branch exists is stamped with ``policy_metadata["lane_head"]`` --
that lane branch's HEAD sha at persist time. The stamp lets a later
consolidation (D-2/D-3 of ``plan.md``) recover which commits a WP's
implementation/review windows actually covered, even after the lane branch
has moved on.

**single_branch Missions (S8, #7283, FR-070):** a Mission whose STORED topology is
``single_branch`` and whose write branch is a minted Mission branch (``meta.mission_branch``,
distinct from the target) stamps every work package's transitions with that branch's head,
whatever lane ``lanes.json`` assigns. The decision reads ``meta.json`` only, never
``is_planning_lane`` or ``execution_mode: direct_repo``, and never ``lane_created_branch``
of ``lane-planning`` (which resolves to the target). The planning lane of a ``lanes`` Mission
stays unstamped; a commit-to-target ``single_branch`` Mission keeps the lane-map behaviour
(unbounded residual, FR-078).

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
those are imported function-locally inside :func:`_read_lane_head`, mirroring
``lanes/for_review_gate.py::_resolve_lane`` and the cold-import discipline
``tests/architectural/test_cold_import_status_boundary.py`` enforces on the
``status`` package. ``LANE_HEAD_KEY``, ``WP_WINDOW_KEY``, :class:`LaneHeadReading`
and :class:`LaneHeadReader` are the only symbols a pure caller
(``status/transition_pipeline.py``) needs, and none requires those imports.

**Window-open record (WP07, FR-002/FR-003):** :func:`read_lane_head` returns a
:class:`LaneHeadReading` -- the sha, "not applicable", or a typed failure
(:class:`CaptureCause`) -- so the pipeline can write ``policy_metadata["wp_window"]``
from the same single reading as ``lane_head`` (W-2, NFR-006). :func:`probe_lane_head`
stays as the sha-only adapter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
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

#: The ``policy_metadata`` key the window-open record is written under (WP07, FR-002/FR-003):
#: ``{"schema_version": 1, "open_sha": <sha>}`` or a typed gap. Re-exported from the facade
#: like :data:`LANE_HEAD_KEY` (SR-2). Contract: the Mission's ``contracts/status-event-wp-window.md``.
WP_WINDOW_KEY: Final = "wp_window"

#: Contract ``maxLength`` of ``gap.detail``.
_DETAIL_MAX_LENGTH: Final = 500


class CaptureCause(StrEnum):
    """Why a lane-head reading of an applicable work package has no sha (closed set)."""

    LANE_BRANCH_MISSING = "lane_branch_missing"
    GIT_ERROR = "git_error"
    PROBE_ERROR = "probe_error"


@dataclass(frozen=True)
class LaneHeadReading:
    """What the injected reader observed for one work package at one transition.

    Exactly one holds: ``sha`` is set; ``applicable`` is ``False`` (planning lane, work
    package not in ``lanes.json``, no ``lanes.json``); ``cause`` is set (an applicable
    reading that failed). A violation is a programming error (``ValueError``), never a
    capture failure.
    """

    sha: str | None
    applicable: bool
    cause: CaptureCause | None
    detail: str = ""

    def __post_init__(self) -> None:
        states = (self.sha is not None, not self.applicable, self.cause is not None)
        if sum(states) != 1:
            raise ValueError(f"LaneHeadReading needs exactly one of sha / not applicable / cause, got {self!r}")
        if len(self.detail) > _DETAIL_MAX_LENGTH:
            object.__setattr__(self, "detail", self.detail[:_DETAIL_MAX_LENGTH])

    @classmethod
    def of_sha(cls, sha: str) -> LaneHeadReading:
        return cls(sha=sha, applicable=True, cause=None)

    @classmethod
    def not_applicable(cls) -> LaneHeadReading:
        return cls(sha=None, applicable=False, cause=None)

    @classmethod
    def failed(cls, cause: CaptureCause, detail: str) -> LaneHeadReading:
        return cls(sha=None, applicable=True, cause=cause, detail=detail)


class LaneHeadProbe(Protocol):
    """Callable shape ``prepare_transition`` accepts to stamp a lane head.

    Injected by the two composition shells (``status/emit.py``,
    ``coordination/status_transition.py``); the pure pipeline never
    constructs one itself.
    """

    def __call__(self, *, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> str | None: ...


class LaneHeadReader(Protocol):
    """Callable shape ``prepare_transition`` accepts to take the one lane-head reading.

    Injected by the two composition shells (``status/emit.py``,
    ``coordination/status_transition.py``) as :func:`read_lane_head`; the pure
    pipeline never constructs one itself (C-002). The same reading feeds both
    ``lane_head`` and ``wp_window`` (W-2).
    """

    def __call__(self, *, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> LaneHeadReading: ...


def read_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> LaneHeadReading:
    """Return the lane-head reading of *wp_id*; never raises (C-1).

    See :func:`probe_lane_head` for the arguments. An unexpected error becomes
    ``failed(PROBE_ERROR, "<exception class>: <message>")``.
    """
    try:
        # Broad catch is intentional (C-1): this reader is best-effort and
        # must never raise into a status transition -- any lanes.json,
        # placement-seam, or git-invocation failure degrades to a failed reading.
        return _read_lane_head(repo_root=repo_root, mission_slug=mission_slug, wp_id=wp_id, owned=owned)
    except Exception as exc:
        logger.debug(
            "read_lane_head: could not resolve lane head for %s/%s under %s",
            mission_slug,
            wp_id,
            repo_root,
            exc_info=True,
        )
        return LaneHeadReading.failed(CaptureCause.PROBE_ERROR, f"{type(exc).__name__}: {exc}")


def probe_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> str | None:
    """Return *wp_id*'s lane branch HEAD sha, or ``None`` when unavailable.

    For a ``single_branch`` Mission with a minted write branch the sha is that branch's
    head instead (S8, FR-070), for every work package.

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
    return read_lane_head(repo_root=repo_root, mission_slug=mission_slug, wp_id=wp_id, owned=owned).sha


_NO_STAMP_WARNING = (
    "probe_lane_head: %s/%s is in execution lane %s but no lane-head stamp could be taken (%s); "
    "this transition carries no commit attribution, so a later mixed-lane consolidation may refuse"
)


#: What the no-stamp warning names as the "lane" of a ``single_branch`` Mission's work package.
_WRITE_BRANCH_LANE = "the Mission write branch"


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


def _write_branch_head(repo_root: Path, mission_slug: str, wp_id: str, write_branch: str) -> LaneHeadReading:
    """S8 (#7283, FR-070): the reading of a ``single_branch`` Mission's minted write branch.

    Every work package of such a Mission is stamped with this one branch's head, whatever
    lane ``lanes.json`` puts it in. A missing branch is logged at WARNING and reads as
    ``lane_branch_missing``; a git error propagates to :func:`read_lane_head`, which turns it
    into ``probe_error`` (C-1). Either way ``consolidate`` then treats the approval as
    unstamped (FR-074).
    """
    sha = _branch_head(repo_root, write_branch)
    if sha is None:
        why = f"Mission branch {write_branch} does not exist"
        _warn_no_stamp(mission_slug, wp_id, _WRITE_BRANCH_LANE, why)
        return LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, why)
    return LaneHeadReading.of_sha(sha)


def _read_lane_head(*, repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None = None) -> LaneHeadReading:
    """Unguarded lanes.json resolution; exceptions are the caller's (:func:`read_lane_head`) to catch.

    Once the WP's execution lane is known, a git error or a missing branch is
    handled here (never raised) so it can be logged with the WP and the lane.
    A corrupt ``lanes.json`` is a failed reading (``probe_error``): the work
    package may well be lane-mapped, so it is not "not applicable" (W-3).
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.lanes.compute import is_planning_lane, lane_created_branch
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
    from specify_cli.lanes.single_branch_landing import minted_write_branch

    write_branch = minted_write_branch(repo_root, mission_slug, owned=owned)
    if write_branch is not None:
        return _write_branch_head(repo_root, mission_slug, wp_id, write_branch)
    planning_dir = owned.mission_dir if owned is not None else placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    try:
        manifest = read_lanes_json(planning_dir)
    except CorruptLanesError:
        return LaneHeadReading.failed(CaptureCause.PROBE_ERROR, "corrupt lanes.json")
    if manifest is None:
        return LaneHeadReading.not_applicable()
    lane = manifest.lane_for_wp(wp_id)
    if lane is None or is_planning_lane(lane):
        return LaneHeadReading.not_applicable()
    branch = lane_created_branch(manifest, lane.lane_id)
    try:
        sha = _branch_head(repo_root, branch)
    except Exception as exc:  # noqa: BLE001 — best-effort (C-1): a git error is logged, never raised
        _warn_no_stamp(mission_slug, wp_id, lane.lane_id, f"git error: {exc}")
        return LaneHeadReading.failed(CaptureCause.GIT_ERROR, str(exc))
    if sha is not None:
        return LaneHeadReading.of_sha(sha)
    other_branches = (lane_created_branch(manifest, other.lane_id) for other in manifest.lanes if other.lane_id != lane.lane_id and not is_planning_lane(other))
    if any(_branch_head(repo_root, other) is not None for other in other_branches):
        _warn_no_stamp(mission_slug, wp_id, lane.lane_id, f"lane branch {branch} does not exist")
    else:
        logger.debug("probe_lane_head: %s/%s lane %s has no branch yet (pre-implementation)", mission_slug, wp_id, lane.lane_id)
    return LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, f"refs/heads/{branch} not found")
