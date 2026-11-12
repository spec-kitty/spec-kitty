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
of ``lane-planning`` (which resolves to the target). A commit-to-target ``single_branch``
Mission (write branch == target) stamps the target branch head (#7578): the review range reads a
recorded window on every topology. Consolidation still leaves such a Mission unbounded (FR-078):
the write-branch and approval-stamp bounds read only a minted Mission branch. The planning lane of
a ``lanes`` Mission stays unstamped.

**Best-effort, never blocking (C-1):** :func:`read_lane_head` never raises.
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
``status`` package. ``LANE_HEAD_KEY``, :class:`LaneHeadReading`
and :class:`LaneHeadReader` are the only symbols a pure caller
(``status/transition_pipeline.py``) needs, and none requires those imports.

**Window-open record (WP07, FR-002/FR-003):** :func:`read_lane_head` returns a
:class:`LaneHeadReading` -- the sha, "not applicable", or a typed failure
(:class:`CaptureCause`, defined with the rest of the ``wp_window`` codec in
``status/wp_window.py``) -- so the pipeline can write ``policy_metadata["wp_window"]``
from the same single reading as ``lane_head`` (W-2, NFR-006).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from .wp_window import GAP_DETAIL_MAX_LENGTH, CaptureCause

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

logger = logging.getLogger(__name__)

#: The ``policy_metadata`` key a stamped lane-head sha is recorded under.
#: Re-exported from ``status/__init__.py`` (the facade) so
#: ``specify_cli.status.<submodule>`` imports stay forbidden outside the
#: ``status`` package (SR-2, ``tests/architectural/test_status_module_boundary.py``).
LANE_HEAD_KEY: Final = "lane_head"


@dataclass(frozen=True)
class LaneHeadReading:
    """What the injected reader observed for one work package at one transition.

    Exactly one holds: ``sha`` is set (never empty); ``applicable`` is ``False`` (planning lane, work
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
        if sum(states) != 1 or self.sha == "":
            raise ValueError(f"LaneHeadReading needs exactly one of sha / not applicable / cause, got {self!r}")
        if len(self.detail) > GAP_DETAIL_MAX_LENGTH:
            object.__setattr__(self, "detail", self.detail[:GAP_DETAIL_MAX_LENGTH])

    @classmethod
    def of_sha(cls, sha: str) -> LaneHeadReading:
        return cls(sha=sha, applicable=True, cause=None)

    @classmethod
    def not_applicable(cls) -> LaneHeadReading:
        return cls(sha=None, applicable=False, cause=None)

    @classmethod
    def failed(cls, cause: CaptureCause, detail: str) -> LaneHeadReading:
        return cls(sha=None, applicable=True, cause=cause, detail=detail)


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

    For a ``single_branch`` Mission the sha is its write branch's head instead, for every work
    package: the minted Mission branch (S8, FR-070) or, for a commit-to-target Mission, the
    target branch (#7578).

    ``sha`` is ``None`` for every non-exceptional "no stamp" case (no ``lanes.json``,
    corrupt ``lanes.json``, *wp_id* unassigned, the planning lane, or the lane branch not
    existing in *repo_root*); an unexpected error becomes
    ``failed(PROBE_ERROR, "<exception class>: <message>")``, with the repository root and
    the home directory redacted from the message.

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
        return LaneHeadReading.failed(CaptureCause.PROBE_ERROR, _redacted(f"{type(exc).__name__}: {exc}", repo_root))


def _redacted(detail: str, repo_root: Path) -> str:
    """*detail* with the repository root and the home directory replaced (N4).

    The detail is written into the committed event log, so it must not carry a
    machine-specific absolute path: the repository root reads ``<repo>`` and the
    home directory ``~``. Only whole path segments are replaced (``/repo`` does
    not match inside ``/repob``), a non-absolute root is left alone, and an
    unknown home directory skips the home redaction instead of raising.
    """
    roots = {str(repo_root): "<repo>", str(repo_root.resolve()): "<repo>"} if repo_root.is_absolute() else {}
    try:
        roots[str(Path.home())] = "~"
    except (RuntimeError, KeyError, OSError):
        # HOME unset and no passwd entry for the uid: nothing to redact, and this
        # best-effort reader must never raise into a status transition.
        logger.debug("_redacted: home directory unknown; skipping home redaction", exc_info=True)
    for root, placeholder in sorted(roots.items(), key=lambda item: -len(item[0])):
        if root in ("", "/"):
            continue
        detail = re.sub(re.escape(root) + _SEGMENT_END, placeholder, detail)
    return detail


#: A replaced root must end at a path separator or a non-name character, never inside a longer segment.
_SEGMENT_END: Final = r"(?![\w-]|\.\w)"


_NO_STAMP_WARNING = (
    "read_lane_head: %s/%s is in execution lane %s but no lane-head stamp could be taken (%s); "
    "this transition carries no commit attribution, so a later mixed-lane consolidation may refuse"
)


#: What the no-stamp warning names as the "lane" of a ``single_branch`` Mission's work package.
_WRITE_BRANCH_LANE = "the Mission write branch"


#: How a no-stamp detail names a commit-to-target Mission's write branch (it is the target, never a Mission branch).
_TARGET_BRANCH_ROLE: Final = "target branch"
_MISSION_BRANCH_ROLE: Final = "Mission branch"


#: ``git rev-parse --verify --quiet`` exits 1 when the ref does not exist; any other
#: non-zero exit is a git failure (FR-003), never "branch missing".
_REF_ABSENT_EXIT: Final = 1


class _GitReadError(RuntimeError):
    """A lane-branch read that failed for a reason other than the branch not existing."""


def _branch_head(repo_root: Path, branch: str) -> str | None:
    """``refs/heads/<branch>`` sha, ``None`` when the branch does not exist.

    Raises :class:`_GitReadError` when git itself fails (any exit other than 0 and
    :data:`_REF_ABSENT_EXIT`), so the caller records a git error, not a missing branch.
    """
    from specify_cli.core.git_ops import run_command

    ret, out, err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret == _REF_ABSENT_EXIT:
        return None
    if ret != 0:
        raise _GitReadError(f"git rev-parse exited {ret}: {err.strip()}")
    sha = out.strip()
    return sha or None


def _any_branch_exists(repo_root: Path, branches: Iterable[str]) -> bool:
    """Whether any of *branches* exists; a git failure counts as "exists" (it only raises the log level)."""
    for branch in branches:
        try:
            if _branch_head(repo_root, branch) is not None:
                return True
        except _GitReadError:
            return True
    return False


def _warn_no_stamp(mission_slug: str, wp_id: str, lane_id: str, why: str) -> None:
    logger.warning(_NO_STAMP_WARNING, mission_slug, wp_id, lane_id, why)


def _write_branch_head(repo_root: Path, mission_slug: str, wp_id: str, write_branch: str, *, branch_role: str = _MISSION_BRANCH_ROLE) -> LaneHeadReading:
    """S8 (#7283, FR-070; #7578): the reading of a ``single_branch`` Mission's write branch (minted, or the target).

    Every work package of such a Mission is stamped with this one branch's head, whatever
    lane ``lanes.json`` puts it in. A missing branch is logged at WARNING and reads as
    ``lane_branch_missing``; a failing git read is logged and reads as ``git_error`` (FR-003).
    Either way ``consolidate`` then treats the approval as unstamped (FR-074).
    """
    try:
        sha = _branch_head(repo_root, write_branch)
    except _GitReadError as exc:
        _warn_no_stamp(mission_slug, wp_id, _WRITE_BRANCH_LANE, f"git error: {exc}")
        return LaneHeadReading.failed(CaptureCause.GIT_ERROR, _redacted(str(exc), repo_root))
    if sha is None:
        why = f"{branch_role} {write_branch} does not exist"
        _warn_no_stamp(mission_slug, wp_id, _WRITE_BRANCH_LANE, why)
        return LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, why)
    return LaneHeadReading.of_sha(sha)


def _single_branch_write_branch(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> tuple[str, str] | None:
    """``(write branch, role)`` a STORED ``single_branch`` Mission stamps, read from ``meta.json`` alone, else ``None``.

    The minted Mission branch when there is one (S8, FR-070); the target branch itself for a
    commit-to-target Mission (#7578). ``None`` for any other topology and for a Mission with no
    recorded ``target_branch``, which keep the lane-map reading. *role* names the branch in a
    no-stamp detail.
    """
    from specify_cli.lanes.single_branch_landing import is_single_branch_meta, stored_mission_meta, write_branch_from_meta

    meta = stored_mission_meta(repo_root, mission_slug, owned=owned)
    target = meta.get("target_branch")
    if not (isinstance(target, str) and target) or not is_single_branch_meta(meta):
        return None
    branch = write_branch_from_meta(meta, target)
    return (branch, _TARGET_BRANCH_ROLE) if branch == target else (branch, _MISSION_BRANCH_ROLE)


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

    write_branch = _single_branch_write_branch(repo_root, mission_slug, owned)
    if write_branch is not None:
        return _write_branch_head(repo_root, mission_slug, wp_id, write_branch[0], branch_role=write_branch[1])
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
        return LaneHeadReading.failed(CaptureCause.GIT_ERROR, _redacted(str(exc), repo_root))
    if sha is not None:
        return LaneHeadReading.of_sha(sha)
    other_branches = (lane_created_branch(manifest, other.lane_id) for other in manifest.lanes if other.lane_id != lane.lane_id and not is_planning_lane(other))
    if _any_branch_exists(repo_root, other_branches):
        _warn_no_stamp(mission_slug, wp_id, lane.lane_id, f"lane branch {branch} does not exist")
    else:
        logger.debug("read_lane_head: %s/%s lane %s has no branch yet (pre-implementation)", mission_slug, wp_id, lane.lane_id)
    return LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, f"refs/heads/{branch} not found")
