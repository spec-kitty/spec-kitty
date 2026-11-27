"""Incorporate a sibling lane, at its newest approval stamp, into a work package's lane checkout.

The incorporate step of the approved-lane re-review route (FR-001, operator ruling
DM-01M7WX8AX56E23AXBZRWGNX4EM option b): ``spec-kitty agent action implement <WP>
--mission <m> --incorporate <lane>`` merges the named sibling lane into the lane
checkout of a work package that was sent back for rework.

The sibling is merged at its newest **approval stamp**, never its live tip: the
reconciliation gate lets a reviewed merge author what it brought in only when every
non-first parent is reachable from another approved lane's approval stamp
(``reconciliation_authorship._trusted_history_roots``), so a sibling merged past its
stamp would fail the gate even after re-review.

Incorporating is not approving (C-001, C-004): this module writes no status event,
stamps nothing and attests nothing. The merge it creates is new content on the lane;
only a new independent review approval that reaches it makes it reviewed.

Every precondition refuses with an :class:`IncorporateRefused` that names an
:class:`IncorporateCode`, before any side effect; a probe that cannot answer refuses
too (fail closed). The merge-attribute guard is one of those preconditions (squad-3 I2): it
judges every path the lane sync point and the incorporation merge would merge, before the claim. The merge runs through the merge-conclusion owner
(:func:`specify_cli.git.merge_conclusion.run_committing_op`). This module never prints.

Merge attributes (FR-010, WP07): git computes a merge with clone-local and unreviewed merge
attributes and drivers (a ``merge=union`` turns a conflict into bytes neither side wrote). In its
preflight (before the claim and the sync point), again before its merge, and inside its
canceled-window merge probe, ``--incorporate`` runs WP01's guard
(:func:`~specify_cli.consolidation.merge_attribute_guard.assert_registered_merge_behaviour`) with the
target branch tip, read once per resolution, as the committed attributes source (the claim's own
rule, :func:`~specify_cli.consolidation.merge_attribute_guard.committed_attributes_source`; #5604
review fold I3), and the merge runs with the one pinned merge env (``pinned_merge_env``). A guard
refusal or a probe error refuses with ``INCORPORATE_MERGE_ATTRIBUTES_REFUSED`` before any merge; an
unreadable target branch tip honours no committed ``union`` (fail closed).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.git import GitCommandError, changed_paths, status_entries
from specify_cli.core.vcs.git import git_merge_base
from specify_cli.git.merge_conclusion import run_committing_op
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.compute import is_planning_lane, is_repo_root_lane
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.stale_check import AGENT_PLACEHOLDER
from specify_cli.status import Lane, StatusEvent

if TYPE_CHECKING:
    from specify_cli.consolidation.wp_attribution import Unattributable

__all__ = [
    "INCORPORATE_CONFLICT_EXIT",
    "IncorporateCode",
    "IncorporateOutcome",
    "IncorporateRefused",
    "SiblingStamp",
    "incorporate_sibling",
    "prepare_incorporation",
    "render_outcome",
]

#: Exit code of ``implement --incorporate`` when the merge stops on a conflict (operator ruling
#: 2026-11-20): non-zero so scripts notice, distinct from a refusal (1) and typer's usage error (2).
INCORPORATE_CONFLICT_EXIT = 3

#: The lanes a work package may incorporate from: it was claimed, or sent back for rework.
_MAY_INCORPORATE = frozenset({Lane.CLAIMED, Lane.IN_PROGRESS})
#: The lanes a work package leaves with the move-back command.
_SEND_BACK_LANES = frozenset({Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE})
_IN_PROGRESS_REFS = ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
_SHORT = 12


class IncorporateCode(StrEnum):
    """Why ``implement --incorporate`` refused, before any side effect."""

    LANE_UNKNOWN = "INCORPORATE_LANE_UNKNOWN"
    OWN_LANE = "INCORPORATE_OWN_LANE"
    PLANNING_LANE = "INCORPORATE_PLANNING_LANE"
    NO_APPROVAL_STAMP = "INCORPORATE_NO_APPROVAL_STAMP"
    STAMP_NOT_ON_LANE = "INCORPORATE_STAMP_NOT_ON_LANE"
    CANCELED_CONTENT_UNDER_STAMP = "INCORPORATE_CANCELED_CONTENT_UNDER_STAMP"
    WP_NOT_SENT_BACK = "INCORPORATE_WP_NOT_SENT_BACK"
    CHECKOUT_BUSY = "INCORPORATE_CHECKOUT_BUSY"
    PROBE_FAILED = "INCORPORATE_PROBE_FAILED"
    MERGE_ATTRIBUTES_REFUSED = "INCORPORATE_MERGE_ATTRIBUTES_REFUSED"


class IncorporateRefused(RuntimeError):
    """A refusal of ``implement --incorporate``, carrying its :class:`IncorporateCode`."""

    def __init__(self, code: IncorporateCode, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SiblingStamp:
    """The sibling lane to incorporate and the approval stamp it is merged at."""

    lane_id: str
    branch: str
    stamp: str
    wp_ids: tuple[str, ...]
    #: The target branch tip whose committed ``.gitattributes`` may set a reviewed ``union`` (WP07, #5604
    #: review fold I3: the claim's rule); ``None`` (unread) honours no committed ``union``.
    attributes_source: str | None = None


@dataclass(frozen=True)
class IncorporateOutcome:
    """What :func:`incorporate_sibling` did in *checkout*."""

    sibling: SiblingStamp
    merged: bool
    already_present: bool
    merge_sha: str | None
    conflicted_paths: tuple[str, ...]
    checkout: Path

    @property
    def conflicted(self) -> bool:
        return bool(self.conflicted_paths)


def _short(sha: str) -> str:
    return sha[:_SHORT]


def _move_back(wp_id: str, mission_slug: str, lane: Lane) -> str:
    from specify_cli.consolidation.approved_bound import move_back_command

    command = move_back_command(wp_id, mission_slug)
    return f'{command} --force --note "<why>"' if lane is Lane.DONE else command


def _check_wp_may_incorporate(lane: Lane, wp_id: str, mission_slug: str) -> None:
    """Refuse unless *wp_id* is ``claimed`` or ``in_progress`` (an approved WP must be sent back first)."""
    if lane in _MAY_INCORPORATE:
        return
    if lane in _SEND_BACK_LANES:
        message = (
            f"{wp_id} is {lane}; a work package incorporates a sibling lane only after it was sent back for rework. "
            f"Send it back first: {_move_back(wp_id, mission_slug, lane)}"
        )
    elif lane is Lane.PLANNED:
        claim = f"spec-kitty agent action implement {wp_id} --mission {mission_slug} --agent {AGENT_PLACEHOLDER}"
        message = f"{wp_id} is planned: there is nothing to resolve yet. Claim it first: {claim}"
    else:
        message = f"{wp_id} is {lane}; only a claimed or in-progress work package can incorporate a sibling lane."
    raise IncorporateRefused(IncorporateCode.WP_NOT_SENT_BACK, message)


def _find_lane(manifest: LanesManifest, lane_id: str) -> ExecutionLane | None:
    return next((lane for lane in manifest.lanes if lane.lane_id == lane_id), None)


def _sibling_lane(manifest: LanesManifest, own_lane_id: str, sibling_lane_id: str) -> ExecutionLane:
    sibling = _find_lane(manifest, sibling_lane_id)
    if sibling is None:
        known = ", ".join(lane.lane_id for lane in manifest.lanes) or "none"
        raise IncorporateRefused(IncorporateCode.LANE_UNKNOWN, f"no lane {sibling_lane_id!r} in this Mission (lanes: {known}).")
    if sibling.lane_id == own_lane_id:
        raise IncorporateRefused(IncorporateCode.OWN_LANE, f"{sibling_lane_id} is this work package's own lane; name a sibling lane.")
    if is_repo_root_lane(sibling) or is_planning_lane(sibling):
        raise IncorporateRefused(
            IncorporateCode.PLANNING_LANE, f"{sibling_lane_id} is a planning lane (the repository root checkout); it has no lane branch to incorporate."
        )
    return sibling


def _approved_stamps(events: Sequence[StatusEvent], lane: ExecutionLane) -> dict[str, str]:
    """``{wp_id: newest approval stamp}`` of *lane*'s approved or done work packages; refuse an unstamped one.

    Approved membership is the gate's one predicate (``reconciliation_authorship.approved_wp_ids``, squad-3 A5).
    """
    from specify_cli.consolidation.approved_bound import approval_stamp
    from specify_cli.consolidation.reconciliation_authorship import approved_wp_ids
    from specify_cli.status import reduce

    work_packages = reduce(list(events)).work_packages
    approved = approved_wp_ids(lane, work_packages)
    if not approved:
        raise IncorporateRefused(IncorporateCode.NO_APPROVAL_STAMP, f"{lane.lane_id} has no approved work package, so it has no approval stamp to incorporate.")
    stamps = {wp: approval_stamp(events, wp) for wp in approved}
    unstamped = [wp for wp, stamp in stamps.items() if stamp is None]
    if unstamped:
        raise IncorporateRefused(
            IncorporateCode.NO_APPROVAL_STAMP,
            f"{lane.lane_id}: {', '.join(unstamped)} is approved with no approval stamp, so its content cannot be shown reviewed.",
        )
    return {wp: stamp for wp, stamp in stamps.items() if stamp is not None}


def _newest_stamp(repo_root: Path, stamps: dict[str, str], lane_id: str) -> str:
    """The stamp every other stamp is reachable from; refuse diverged stamps."""
    from specify_cli.consolidation.git_probes import sha_reachable_from

    candidates = list(dict.fromkeys(stamps.values()))
    for candidate in candidates:
        if all(other == candidate or sha_reachable_from(repo_root, other, candidate) for other in candidates):
            return candidate
    listed = ", ".join(f"{wp}={_short(stamp)}" for wp, stamp in stamps.items())
    raise IncorporateRefused(IncorporateCode.STAMP_NOT_ON_LANE, f"{lane_id}'s approval stamps diverged ({listed}); no one stamp holds every approval.")


def _require_stamp_on_branch(repo_root: Path, stamp: str, branch: str, lane_id: str) -> None:
    from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit, sha_reachable_from

    try:
        tip = resolve_commit(repo_root, f"refs/heads/{branch}")
    except GitProbeError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"cannot read {lane_id}'s branch {branch}: {exc}") from exc
    if not sha_reachable_from(repo_root, stamp, tip):
        raise IncorporateRefused(
            IncorporateCode.STAMP_NOT_ON_LANE,
            f"{lane_id}'s approval stamp {_short(stamp)} is not on its branch {branch} (the lane was rewritten); approve it again first.",
        )


def _canceled_wp_ids(events: Sequence[StatusEvent], wp_ids: Sequence[str]) -> list[str]:
    from specify_cli.status import reduce

    snapshot = reduce(list(events))
    return [wp for wp in wp_ids if str((snapshot.work_packages.get(wp) or {}).get("lane")) == Lane.CANCELED]


def _refusal(lane_id: str, wp_id: str, stamp: str, why: str) -> IncorporateRefused:
    return IncorporateRefused(
        IncorporateCode.CANCELED_CONTENT_UNDER_STAMP,
        f"{lane_id}'s approval stamp {_short(stamp)} {why} of canceled {wp_id}; incorporating it would bring canceled work into this lane. "
        "Rework that lane first so its approved stamp no longer carries them.",
    )


@dataclass(frozen=True)
class _IncorporateRoute:
    """The incorporating work package, its Mission and the sibling lane: what a refusal's remedy names."""

    wp_id: str
    mission_slug: str
    sibling_lane_id: str

    def rerun(self) -> str:
        return f"spec-kitty agent action implement {self.wp_id} --mission {self.mission_slug} --incorporate {self.sibling_lane_id} --agent {AGENT_PLACEHOLDER}"

    def attest(self, canceled_wp_id: str) -> str:
        from specify_cli.consolidation.canceled_attestation import ATTEST_FLAG, ATTEST_REASON_FLAG

        return f'spec-kitty consolidate --mission {self.mission_slug} {ATTEST_FLAG} {canceled_wp_id} {ATTEST_REASON_FLAG} "<what you checked>"'


def _unattributable_refusal(lane_id: str, wp_id: str, outcome: Unattributable, *, overridable: bool, route: _IncorporateRoute) -> IncorporateRefused:
    """The refusal when the window authority cannot attribute a canceled WP's commits: a verdict of doubt, not a finding.

    It names the reason code, the work package and (in the detail) the commits; an overridable
    reason prints the attestation route ``consolidate`` owns, then the incorporate re-run.
    """
    lines = [
        f"{lane_id}: canceled {wp_id}'s commits cannot be attributed ({outcome.reason.name}: {outcome.detail}), "
        "so the approval stamp cannot be shown free of its work.",
    ]
    if overridable:
        lines += [
            f"If you checked by hand that {wp_id} left nothing on {lane_id}, record that with:",
            f"  {route.attest(wp_id)}",
            "  (only spec-kitty consolidate records this attestation, and the same command then starts a consolidation of the Mission)",
        ]
    else:
        lines.append("Repair what the reason names; an attestation cannot lift it.")
    lines.append(f"Then re-run: {route.rerun()}")
    return IncorporateRefused(IncorporateCode.CANCELED_CONTENT_UNDER_STAMP, "\n".join(lines))


def _refuse_attributed_commits(repo_root: Path, commits: frozenset[str], lane_id: str, wp_id: str, stamp: str) -> None:
    """Refuse when the stamp reaches a commit the window authority attributed to the canceled WP."""
    from specify_cli.consolidation.git_probes import GitProbeError, is_ancestor_strict

    # A probe that errors must refuse: reading "cannot tell" as "not reachable" would pass the stamp.
    try:
        under = sorted(sha for sha in commits if is_ancestor_strict(repo_root, sha, stamp))
    except GitProbeError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"cannot tell whether {wp_id}'s commits are under {lane_id}'s stamp {_short(stamp)}: {exc}") from exc
    if under:
        raise _refusal(lane_id, wp_id, stamp, f"reaches commits ({', '.join(_short(sha) for sha in under)})")


def _canceled_window_merges(repo_root: Path, events: Sequence[StatusEvent], wp_id: str, stamp: str, base_ref: str) -> list[str]:
    """The merges the stamp reaches beyond *base_ref* (through any parent) that lie inside *wp_id*'s work windows.

    ``resolve_canceled_wp`` never attributes a merge to a work package, so content folded into a
    merge's own resolution needs this separate look. The window rule is the one
    :func:`~specify_cli.consolidation.wp_attribution.merges_in_canceled_windows` (squad-3 A1), the
    rule ``consolidate``'s claim reads: a window with a missing stamp holds every merge (fail
    closed). A history git cannot read raises ``GitProbeError`` (the caller refuses).
    """
    from specify_cli.consolidation.approved_bound import merges_beyond
    from specify_cli.consolidation.wp_attribution import merges_in_canceled_windows

    merges = merges_beyond(repo_root, stamp, [base_ref])
    inside = merges_in_canceled_windows(repo_root, events, [wp_id], merges)
    return [sha for sha in merges if sha in inside]


_ATTRIBUTES_REMEDY = (
    "nothing was merged. Remove the clone-local or uncommitted merge attribute or driver the reason names, "
    "or commit it to the Mission branch through a reviewed change, then re-run the command."
)


def _attributes_refusal(subject: str, exc: Exception) -> IncorporateRefused:
    """``INCORPORATE_MERGE_ATTRIBUTES_REFUSED``: a merge git would compute under unreviewed merge settings, or one that cannot be judged."""
    message = f"{subject} cannot be judged under the effective merge attributes ({exc}); {_ATTRIBUTES_REMEDY}"
    return IncorporateRefused(IncorporateCode.MERGE_ATTRIBUTES_REFUSED, message)


def _merge_own_paths(repo_root: Path, merge: str, lane_id: str, attributes_source: str | None) -> list[str]:
    """WP01's window-merge probe under its guard and pinned config; any probe error refuses with the merge-attribute code."""
    from specify_cli.consolidation import git_probes

    try:
        return list(git_probes.merge_own_changed_paths(repo_root, merge, attributes_source=attributes_source))
    except git_probes.GitProbeError as exc:
        raise _attributes_refusal(f"{lane_id}: merge {_short(merge)} in a canceled work window", exc) from exc


def _refuse_canceled_merges(
    repo_root: Path, events: Sequence[StatusEvent], lane_id: str, wp_id: str, stamp: str, *, base_ref: str, attributes_source: str | None
) -> None:
    """Refuse when the stamp reaches a merge in the canceled WP's window that adds content of its own, or cannot be judged."""
    from specify_cli.consolidation import git_probes

    try:
        merges = _canceled_window_merges(repo_root, events, wp_id, stamp, base_ref)
    except git_probes.GitProbeError as exc:
        raise _refusal(lane_id, wp_id, stamp, f"cannot be cleared: a merge in the window cannot be judged ({exc})") from exc
    for merge in merges:
        own = _merge_own_paths(repo_root, merge, lane_id, attributes_source)
        if own:
            raise _refusal(lane_id, wp_id, stamp, f"reaches merge {_short(merge)}, whose own resolution changed {', '.join(own)} in the window")


def _refuse_canceled_content_under_stamp(
    repo_root: Path,
    events: Sequence[StatusEvent],
    sibling: ExecutionLane,
    stamp: str,
    *,
    branch: str,
    base_ref: str,
    route: _IncorporateRoute,
    attributes_source: str | None,
) -> None:
    """Refuse when a canceled work package of the sibling lane has content the stamp reaches.

    The canceled WP's commits come from the one window authority,
    ``wp_attribution.resolve_canceled_wp``, read exactly as ``consolidate`` reads them: an
    ``Unattributable`` result refuses (fail closed) unless an operator canceled-superseded
    attestation lifts it (FR-012, ``OVERRIDABLE_REASONS``). A merge in the canceled window
    whose own resolution changed paths refuses too, since the resolver never attributes merges.
    """
    from specify_cli.consolidation.canceled_attestation import OVERRIDABLE_REASONS, attestation_stamps
    from specify_cli.consolidation.reconciliation_kernel import is_mission_bookkeeping_path
    from specify_cli.consolidation.wp_attribution import Unattributable, resolve_canceled_wp

    attested = attestation_stamps(events)
    canceled = _canceled_wp_ids(events, sibling.wp_ids)
    anchors = [anchor for wp in canceled if (anchor := attested.get(wp))]
    for wp_id in canceled:
        outcome = resolve_canceled_wp(
            repo_root,
            events=events,
            lane_id=sibling.lane_id,
            lane_wp_ids=sibling.wp_ids,
            canceled_wp_id=wp_id,
            lane_branch=branch,
            coord_base_ref=base_ref,
            is_bookkeeping=lambda path: is_mission_bookkeeping_path(path, route.mission_slug),
            closed_world_anchors=anchors,
            never_exempt_commits=frozenset(),
        )
        if isinstance(outcome, Unattributable):
            if wp_id in attested and outcome.reason in OVERRIDABLE_REASONS:
                continue
            raise _unattributable_refusal(sibling.lane_id, wp_id, outcome, overridable=outcome.reason in OVERRIDABLE_REASONS, route=route)
        _refuse_attributed_commits(repo_root, outcome.commits, sibling.lane_id, wp_id, stamp)
        _refuse_canceled_merges(repo_root, events, sibling.lane_id, wp_id, stamp, base_ref=base_ref, attributes_source=attributes_source)


def _resolve_sibling_stamp(
    repo_root: Path,
    mission_slug: str,
    manifest: LanesManifest,
    *,
    own_lane_id: str,
    sibling_lane_id: str,
    events: Sequence[StatusEvent],
    wp_id: str,
) -> SiblingStamp:
    """Resolve *sibling_lane_id*'s branch and newest approval stamp, or refuse (no side effect)."""
    from specify_cli.consolidation.merge_attribute_guard import committed_attributes_source

    attributes_source = committed_attributes_source(repo_root, manifest.target_branch)
    sibling = _sibling_lane(manifest, own_lane_id, sibling_lane_id)
    branch = lane_branch_name(mission_slug, sibling.lane_id, target_branch=manifest.target_branch)
    stamps = _approved_stamps(events, sibling)
    stamp = _newest_stamp(repo_root, stamps, sibling.lane_id)
    _require_stamp_on_branch(repo_root, stamp, branch, sibling.lane_id)
    _refuse_canceled_content_under_stamp(
        repo_root,
        events,
        sibling,
        stamp,
        branch=branch,
        base_ref=f"refs/heads/{manifest.mission_branch}",
        route=_IncorporateRoute(wp_id=wp_id, mission_slug=mission_slug, sibling_lane_id=sibling.lane_id),
        attributes_source=attributes_source,
    )
    return SiblingStamp(lane_id=sibling.lane_id, branch=branch, stamp=stamp, wp_ids=tuple(sibling.wp_ids), attributes_source=attributes_source)


def _read_manifest(repo_root: Path, mission_slug: str) -> LanesManifest:
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    try:
        manifest = read_lanes_json(placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.LANE_STATE))
    except CorruptLanesError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"lanes.json cannot be read: {exc}") from exc
    if manifest is None:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"{mission_slug} has no lanes.json; it has no lanes to incorporate.")
    return manifest


def _read_events(repo_root: Path, mission_slug: str) -> list[StatusEvent]:
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.coordination.surface_resolver import StatusReadPathNotFound, WorktreeRegistryUnavailable
    from specify_cli.status import StoreError, read_status_events, resolve_status_read

    try:
        events: list[StatusEvent] = read_status_events(resolve_status_read(repo_root, mission_slug))
    except (OSError, StoreError, ValueError, StatusReadPathNotFound, StatusSurfaceRefUnreadable, WorktreeRegistryUnavailable) as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"the status of {mission_slug} cannot be read: {exc}") from exc
    return events


def _wp_lane(events: Sequence[StatusEvent], wp_id: str) -> Lane:
    from specify_cli.status import reduce

    state = reduce(list(events)).work_packages.get(wp_id) or {}
    raw = state.get("lane")
    try:
        return Lane(str(raw))
    except ValueError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"{wp_id} has no readable lane in the status log ({raw!r}).") from exc


def _own_lane_ref(repo_root: Path, mission_slug: str, manifest: LanesManifest, own: ExecutionLane) -> str:
    """The incorporating lane's branch ref, or the Mission branch's when the lane branch does not exist yet (the claim cuts it there)."""
    from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit

    ref = f"refs/heads/{lane_branch_name(mission_slug, own.lane_id, target_branch=manifest.target_branch)}"
    try:
        resolve_commit(repo_root, ref)
    except GitProbeError:
        return f"refs/heads/{manifest.mission_branch}"
    return ref


def _guard_attributes_before_side_effects(repo_root: Path, own_ref: str, mission_branch: str, sibling: SiblingStamp) -> None:
    """WP01's guard, before the claim and the lane sync point (squad-3 I2): every path the sync-point merge
    (the Mission branch into the lane) or the incorporation merge (the stamp into the lane) would merge.

    A refusal here leaves everything as it was: no status event, no lane sync, no merge.
    """
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    env = _merge_env()
    subject = f"the merge of {sibling.lane_id} at approval stamp {_short(sibling.stamp)} into {own_ref}"
    paths: list[str] = []
    try:
        for side in (f"refs/heads/{mission_branch}", sibling.stamp):
            base = git_merge_base(repo_root, own_ref, side)
            if base is None:
                raise GitProbeError(f"the merge base of {own_ref} and {side} cannot be read")
            paths.extend(str(path) for tip in (own_ref, side) for path in changed_paths(repo_root, base, tip, env=env))
        assert_registered_merge_behaviour(repo_root, list(dict.fromkeys(paths)), attributes_source=sibling.attributes_source)
    except (GitCommandError, GitProbeError) as exc:
        raise _attributes_refusal(subject, exc) from exc


def prepare_incorporation(repo_root: Path, mission_slug: str, wp_id: str, sibling_lane_id: str, *, check_wp: bool = True) -> SiblingStamp:
    """Every precondition of ``implement --incorporate``, read only: the WP's lane, its own lane, the sibling and its stamp,
    and the merge-attribute guard over both merges the command would make (squad-3 I2), so a refusal precedes every side effect."""
    events = _read_events(repo_root, mission_slug)
    if check_wp:
        _check_wp_may_incorporate(_wp_lane(events, wp_id), wp_id, mission_slug)
    manifest = _read_manifest(repo_root, mission_slug)
    own = manifest.lane_for_wp(wp_id)
    if own is None:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"{wp_id} is not assigned to any lane in lanes.json.")
    if is_repo_root_lane(own):
        raise IncorporateRefused(
            IncorporateCode.PLANNING_LANE, f"{wp_id} runs in the repository root checkout (a planning lane); it has no lane checkout to incorporate into."
        )
    sibling = _resolve_sibling_stamp(repo_root, mission_slug, manifest, own_lane_id=own.lane_id, sibling_lane_id=sibling_lane_id, events=events, wp_id=wp_id)
    _guard_attributes_before_side_effects(repo_root, _own_lane_ref(repo_root, mission_slug, manifest, own), manifest.mission_branch, sibling)
    return sibling


def _merge_env() -> dict[str, str]:
    # The one merge env (#5604 review fold A1): the lane-consolidation pipeline's environment, so
    # spec-kitty's registered merge drivers resolve to the running spec-kitty, with WP01's pinned
    # merge config over every other source (WP07), as the auto-rebase and the merge probes run.
    from specify_cli.consolidation.merge_attribute_guard import pinned_merge_env

    env: dict[str, str] = pinned_merge_env()
    return env


def _guard_merge_attributes(checkout: Path, sibling: SiblingStamp, env: dict[str, str]) -> None:
    """WP01's guard over every path either side changed since the merge base, before the merge; any failure refuses."""
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    subject = f"the merge of {sibling.lane_id} at approval stamp {_short(sibling.stamp)} into {checkout}"
    base = git_merge_base(checkout, "HEAD", sibling.stamp)
    if base is None:
        raise _attributes_refusal(subject, GitProbeError(f"the merge base of HEAD and {_short(sibling.stamp)} cannot be read"))
    try:
        paths = [str(path) for side in ("HEAD", sibling.stamp) for path in changed_paths(checkout, base, side, env=env)]
        assert_registered_merge_behaviour(checkout, paths, attributes_source=sibling.attributes_source)
    except (GitCommandError, GitProbeError) as exc:
        raise _attributes_refusal(subject, exc) from exc


def _require_idle_checkout(checkout: Path, env: dict[str, str]) -> None:
    from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit

    for ref in _IN_PROGRESS_REFS:
        try:
            resolve_commit(checkout, ref)
        except GitProbeError:
            continue
        raise IncorporateRefused(IncorporateCode.CHECKOUT_BUSY, f"an operation is in progress in {checkout} ({ref} exists); finish or abort it first.")
    try:
        entries = status_entries(checkout, untracked="no", env=env)
    except GitCommandError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"cannot read the status of {checkout}: {exc}") from exc
    if entries:
        paths = ", ".join(str(entry.path) for entry in entries)
        raise IncorporateRefused(IncorporateCode.CHECKOUT_BUSY, f"{checkout} has uncommitted changes to tracked files ({paths}); commit or stash them first.")


def merge_message(sibling: SiblingStamp) -> str:
    """The incorporation merge commit's message: it names the sibling lane and its approval stamp."""
    return f"Incorporate {sibling.lane_id} at approval stamp {_short(sibling.stamp)} (spec-kitty implement --incorporate)"


def incorporate_sibling(checkout: Path, sibling: SiblingStamp) -> IncorporateOutcome:
    """Merge *sibling*'s approval stamp into *checkout*; stop with the merge in progress on a conflict."""
    from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit, sha_reachable_from

    env = _merge_env()
    _require_idle_checkout(checkout, env)
    if sha_reachable_from(checkout, sibling.stamp, "HEAD"):
        return IncorporateOutcome(sibling, merged=False, already_present=True, merge_sha=None, conflicted_paths=(), checkout=checkout)
    _guard_merge_attributes(checkout, sibling, env)
    result = run_committing_op(checkout, "merge", ["--no-ff", "-m", merge_message(sibling), sibling.stamp], env=env, disable_gpgsign=False)
    if result.returncode == 0:
        try:
            head = resolve_commit(checkout, "HEAD")
        except GitProbeError as exc:
            raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"the merge committed but HEAD cannot be read: {exc}") from exc
        return IncorporateOutcome(sibling, merged=True, already_present=False, merge_sha=head, conflicted_paths=(), checkout=checkout)
    try:
        conflicted = tuple(str(path) for path in changed_paths(checkout, diff_filter="U", env=env))
    except GitCommandError as exc:
        raise IncorporateRefused(IncorporateCode.PROBE_FAILED, f"the merge failed and its conflicts cannot be read: {exc}") from exc
    if not conflicted:
        detail = (result.stderr or result.stdout or "").strip()
        raise IncorporateRefused(
            IncorporateCode.PROBE_FAILED,
            f"the merge of {sibling.lane_id} failed without a conflict; {checkout} is left as git left it. git said: {detail}",
        )
    return IncorporateOutcome(sibling, merged=False, already_present=False, merge_sha=None, conflicted_paths=conflicted, checkout=checkout)


def render_outcome(outcome: IncorporateOutcome, wp_id: str, mission_slug: str) -> list[str]:
    """The operator-facing lines for *outcome*, printed before the work package prompt."""
    sibling = outcome.sibling
    stamp = _short(sibling.stamp)
    if outcome.merged:
        return [f"Incorporated {sibling.lane_id} at approval stamp {stamp} into {outcome.checkout} (merge {_short(outcome.merge_sha or '')})."]
    if outcome.already_present:
        return [f"{sibling.lane_id}'s approval stamp {stamp} is already in this lane; nothing to incorporate."]
    return [
        f"INCORPORATE STOPPED ON A CONFLICT: {sibling.lane_id} at approval stamp {stamp} into {outcome.checkout}",
        *(f"  conflicted: {path}" for path in outcome.conflicted_paths),
        "Next:",
        f"  1. Resolve the conflicts in {outcome.checkout} and commit the merge there.",
        f"  2. spec-kitty agent tasks move-task {wp_id} --to for_review --mission {mission_slug}",
        f"  3. An independent reviewer reviews {wp_id} and approves it; the new approval must reach the resolution merge.",
        f"  4. spec-kitty consolidate --mission {mission_slug}",
        f"To back out instead, run in {outcome.checkout}: git merge --abort",
        f"(exit code {INCORPORATE_CONFLICT_EXIT}: the merge is left in progress for resolution.)",
    ]
