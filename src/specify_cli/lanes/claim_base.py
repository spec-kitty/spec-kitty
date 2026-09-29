"""The claim-base ref: a repo-root lane's ``for_review`` starting point.

A work package in a repo-root lane (today: every planning-artifact WP; from
WP05 onward, also a ``single_branch`` mission's code WPs) has no lane branch
of its own -- it executes directly in the write checkout, on the mission's
target branch. The ``for_review`` commit gate (:mod:`.for_review_gate`) still
needs SOME starting point to diff against, so this module records one at
claim time: ``refs/spec-kitty/wp-base/<mission_slug>/<wp_id>``, the write
checkout's ``HEAD`` the moment the WP is resolved to a repo-root lane.

Contract (``contracts/single-branch-execution.md``, "Claim base and
for_review", post-plan fold B2):

* **Claim**: :func:`record_claim_base` records the ref -- but ONLY when it is
  absent. A resumed claim (implement re-invoked on an already in_progress WP)
  never moves an already-recorded base.
* **for_review**: the gate requires at least one commit in
  ``wp-base..HEAD`` in the write checkout. See :mod:`.for_review_gate` for
  the exclusion of status-only commits (kitty-specs status/issue-matrix,
  ``.kittify/**``).
* **Cleanup**: :func:`on_wp_terminal` is the ONE terminal-transition hook
  (called once a WP reaches ``done``/``canceled``) that clears the ref. WP07
  extends this SAME hook to also clear the lane-tip ref -- this module never
  grows a second terminal hook.

Refs live in git's *common* dir, so every worktree of the same repository
(including the write checkout itself) shares them -- there is nothing
worktree-local about a claim base.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from specify_cli.git.ref_advance import delete_bookkeeping_ref, write_bookkeeping_ref

__all__ = [
    "on_wp_terminal",
    "read_claim_base",
    "record_claim_base",
]

_CLAIM_BASE_REF_PREFIX = "refs/spec-kitty/wp-base"


def _claim_base_ref(mission_slug: str, wp_id: str) -> str:
    """The ref name a repo-root-lane WP's claim base is recorded under.

    Private: nothing outside this module needs the ref name itself today
    (every external caller goes through :func:`read_claim_base` /
    :func:`record_claim_base` / :func:`on_wp_terminal`) -- the
    symbol-level dead-code gate (``tests/architectural/test_no_dead_symbols.py``)
    requires a real external ``src/`` caller for a public name, and an
    intra-module reference does not count. Widen back to public if a future
    caller genuinely needs to compose the ref name directly.
    """
    return f"{_CLAIM_BASE_REF_PREFIX}/{mission_slug}/{wp_id}"


def read_claim_base(repo_root: Path, mission_slug: str, wp_id: str) -> str | None:
    """Return the recorded claim-base SHA, or ``None`` if never recorded.

    Never raises: an absent ref (the ordinary case before the first claim, or
    a WP claimed before this ref existed) resolves to ``None`` so callers can
    fall back to their own pre-existing refusal (:mod:`.for_review_gate`
    never passes the gate vacuously on a missing ref).
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", _claim_base_ref(mission_slug, wp_id)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def record_claim_base(repo_root: Path, write_checkout: Path, mission_slug: str, wp_id: str) -> str:
    """Record the write checkout's current ``HEAD`` as the claim base.

    Idempotent-by-absence: if the ref is already recorded (a resumed claim,
    or a re-invoked ``implement`` on an already in_progress WP), the existing
    SHA is returned UNCHANGED -- this never re-bases an in-flight WP's
    ``for_review`` window onto a later commit.

    Args:
        repo_root: The repository root whose common git dir owns the ref.
        write_checkout: The checkout whose ``HEAD`` is recorded (the repo
            root itself for a flat/single_branch write target).
        mission_slug: Mission slug the ref is scoped under.
        wp_id: Work package ID the ref is scoped under.

    Returns:
        The claim-base SHA (either the pre-existing one, or the one just
        recorded).

    Raises:
        RuntimeError: ``HEAD`` could not be resolved in ``write_checkout``
            (an unborn/empty repository -- there is nothing to record).
    """
    existing = read_claim_base(repo_root, mission_slug, wp_id)
    if existing is not None:
        return existing

    head_result = subprocess.run(
        ["git", "-C", str(write_checkout), "rev-parse", "--verify", "--quiet", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if head_result.returncode != 0:
        raise RuntimeError(f"cannot record claim base for {mission_slug}/{wp_id}: HEAD does not resolve in {write_checkout}")
    head_sha = head_result.stdout.strip()

    if not write_bookkeeping_ref(repo_root, _claim_base_ref(mission_slug, wp_id), head_sha):
        raise RuntimeError(f"cannot record claim base for {mission_slug}/{wp_id}: git update-ref failed in {repo_root}")
    return head_sha


def _clear_claim_base(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """Delete the claim-base ref. A no-op when the ref is already absent.

    Private: see :func:`_claim_base_ref`'s docstring -- the only caller is
    :func:`on_wp_terminal`, which IS the public, externally-called clear
    primitive.
    """
    delete_bookkeeping_ref(repo_root, _claim_base_ref(mission_slug, wp_id))


def _clear_lane_tip_if_lane_fully_terminal(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """WP07 (#5115): clear the lane-tip ref once EVERY WP sharing this lane is terminal.

    A code lane can be shared by several WPs (``ExecutionLane.wp_ids``), so
    clearing the tip the moment any ONE of them reaches ``done``/``canceled``
    would strand the guard's protection for a sibling WP still in flight in
    the SAME worktree. A no-op for a planning/repo-root lane (never a real
    ``-lane-``-matching branch, so no tip ref was ever recorded for it) and
    for any lookup failure this hook is not positioned to interpret (no
    ``lanes.json``, the WP not assigned to any lane, an unreadable status
    surface) -- this hook must never raise and block the terminal transition
    it is attached to; worst case the tip ref simply outlives the lane a
    little longer, which is fail-safe (the guard only ever refuses on it,
    never silently proceeds past stale data it cannot classify).
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.lane_tip import clear_tip
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound
    from specify_cli.status import CanonicalStatusNotFoundError, get_wp_lane, is_terminal

    try:
        planning_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
        manifest = read_lanes_json(planning_dir)
    except CorruptLanesError:
        return
    if manifest is None:
        return
    lane = manifest.lane_for_wp(wp_id)
    if lane is None or is_repo_root_lane(lane):
        return

    try:
        status_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
        if any(not is_terminal(str(get_wp_lane(status_dir, sibling_id).value)) for sibling_id in lane.wp_ids):
            return
    except (CanonicalStatusNotFoundError, StatusReadPathNotFound):
        return

    _, branch = predict_lane_worktree(repo_root, mission_slug, lane.lane_id)
    clear_tip(repo_root, branch)


def on_wp_terminal(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """The ONE terminal-transition hook: clear per-WP git refs on done/canceled.

    Called from the single seam where a WP reaches a terminal lane (see
    ``coordination/status_transition.py``'s three emit paths, which all fan
    out to this hook once per terminal event). Clears the claim-base ref
    unconditionally (a repo-root lane's ``wp-base`` is always WP-scoped), and
    WP07 extends this SAME function to also clear the SHARED lane-tip ref,
    once every WP in that lane is terminal -- no second terminal hook is ever
    created (post-tasks fold M-3). Callers must gate on terminality
    themselves (this function does not re-check the transition) so it stays
    a pure "clear this WP's refs" primitive, reusable by both
    status_transition.py's terminal check and any future caller that already
    knows the WP is terminal.
    """
    _clear_claim_base(repo_root, mission_slug, wp_id)
    _clear_lane_tip_if_lane_fully_terminal(repo_root, mission_slug, wp_id)
