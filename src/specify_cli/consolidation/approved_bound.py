"""The approved bound: which commit did review approve for a work package (#5668).

``consolidate`` builds an approved work package's claim from the live lane tip. A
commit added to the lane after review approved the work package therefore reads as
approved authorship on every axis and lands under a "verified" banner. The approval
stamp -- ``policy_metadata["lane_head"]`` of the work package's newest ``approved``
event -- names the commit review saw. This module reads it (plan D-1) and checks one
code lane against it (plan D-2):

* an approved work package with no approval stamp refuses (``APPROVAL_STAMP_MISSING``);
  the stamp is never replaced by the lane tip;
* an approval stamp that is not on the lane (a rewritten lane) refuses
  (``APPROVAL_STAMP_NOT_ON_LANE``);
* a content commit reachable from no covered point (the approval stamps, plus the latest
  stamp of each canceled work package of a mixed lane), from no anchor and not from the
  claim base refuses (``LANE_MOVED_AFTER_APPROVAL``). The whole commit range is walked,
  never the first-parent spine: a late commit that arrives through a merge from a branch
  that is not an anchor is found. Merge commits and commits that touch only bookkeeping
  paths are tool-made movement and never count.

Pure functions over a status event list and git probes; no status write, no lane
state, no prompt. The claim builder calls it before any branch moves
(:func:`specify_cli.consolidation.reconciliation.approved_bound_refusal`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from specify_cli.status import StatusEvent

from .canceled_attestation import ATTESTATION_KEY
from .git_probes import GitProbeError, changed_paths_of, commits_in_range, is_merge_commit, resolve_commit, sha_reachable_from
from .wp_attribution import is_migration_event, lane_exempt_commits, stamp_of

#: ``policy_metadata[ATTESTATION_KEY]`` value an operator attestation of an approval records.
APPROVED_REVIEWED = "approved_reviewed"
#: The CLI flag that lifts :attr:`BoundRefusalCode.APPROVAL_STAMP_MISSING` for one work package.
ATTEST_APPROVED_FLAG = "--attest-approved-reviewed"

_APPROVED_LANE = "approved"
_MAX_NAMED_COMMITS = 3
_SHORT_SHA = 7
_RERUN = "then re-run spec-kitty consolidate"
_ATTEST_REASON = '--attest-reason "<what you checked>"'
_MOVE_BACK = "spec-kitty agent tasks move-task {wp} --to in_progress --mission <mission>"


class BoundRefusalCode(StrEnum):
    """The stable codes of the three refusals this module produces."""

    LANE_MOVED_AFTER_APPROVAL = "LANE_MOVED_AFTER_APPROVAL"
    APPROVAL_STAMP_MISSING = "APPROVAL_STAMP_MISSING"
    APPROVAL_STAMP_NOT_ON_LANE = "APPROVAL_STAMP_NOT_ON_LANE"


@dataclass(frozen=True)
class BoundRefusal:
    """One lane the approved bound refuses, with what the operator needs to act."""

    code: BoundRefusalCode
    lane_id: str
    branch: str
    wp_ids: tuple[str, ...]
    commits: tuple[str, ...] = ()
    path: str | None = None
    stamp: str | None = None

    def render(self) -> str:
        """The operator-facing text, led by ``<CODE>: `` like the other claim refusals."""
        wps = ", ".join(self.wp_ids)
        head = f"{self.code.value}: "
        if self.code is BoundRefusalCode.APPROVAL_STAMP_MISSING:
            first = self.wp_ids[0]
            return (
                f"{head}{wps} on lane {self.lane_id} has no recorded approval stamp, so the commit review approved cannot be determined. "
                f"Recovery: move {wps} back for review ({_MOVE_BACK.format(wp=first)}), approve it again, {_RERUN}; "
                f"or, after checking by hand that the lane holds only reviewed work, {_RERUN} with {ATTEST_APPROVED_FLAG} {first} {_ATTEST_REASON}"
            )
        if self.code is BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE:
            return (
                f"{head}the approval of {wps} names commit {_short(self.stamp)}, which is not on lane {self.lane_id} (branch '{self.branch}'); "
                f"the lane was rewritten after review approved it. "
                f"Recovery: move {wps} back for review ({_MOVE_BACK.format(wp=self.wp_ids[0])}), approve it again, {_RERUN}"
            )
        named = ", ".join(_short(sha) for sha in self.commits[:_MAX_NAMED_COMMITS])
        more = len(self.commits) - _MAX_NAMED_COMMITS
        if more > 0:
            named += f" and {more} more"
        return (
            f"{head}lane {self.lane_id} (branch '{self.branch}') holds content committed after review approved the lane "
            f"(work packages {wps} of this lane): {named} (e.g. '{self.path}'). "
            f"Recovery: move {self.wp_ids[0]} back for review ({_MOVE_BACK.format(wp=self.wp_ids[0])}) so the new content is reviewed, approve it again, {_RERUN}"
        )


def _short(sha: str | None) -> str:
    return (sha or "")[:_SHORT_SHA]


def is_approved_reviewed_attestation(policy_metadata: Mapping[str, object] | None) -> bool:
    """True iff *policy_metadata* (an event's, parsed or raw) marks an operator attestation of an approval, which is not a review.

    The one test of that marker, for every reader that must tell an attestation from a
    review approval (the stamp readers here, the hollow-review merge gate).
    """
    return isinstance(policy_metadata, Mapping) and policy_metadata.get(ATTESTATION_KEY) == APPROVED_REVIEWED


def _is_approval(event: StatusEvent) -> bool:
    return str(event.to_lane) == _APPROVED_LANE or is_approved_reviewed_attestation(event.policy_metadata)


def _newest_approval(events: Sequence[StatusEvent], wp_id: str) -> StatusEvent | None:
    """*wp_id*'s newest approval event, or ``None`` when it has none.

    Walks *events* in append order. An approval is an event whose ``to_lane`` is
    ``approved`` or an operator attestation of an approval (:data:`APPROVED_REVIEWED`,
    any ``to_lane``). The ``approved -> done`` event is neither, so the restamp the run
    itself writes is never read; migration-synthesized events (FR-011) never count.
    """
    newest: StatusEvent | None = None
    for event in events:
        if event.wp_id == wp_id and not is_migration_event(event) and _is_approval(event):
            newest = event
    return newest


def approval_stamp(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """The ``lane_head`` stamp of *wp_id*'s newest approval, or ``None`` when it has none (plan D-1).

    The newest approval decides: an approval with no stamp yields ``None`` even when an
    older approval had one.
    """
    newest = _newest_approval(events, wp_id)
    return None if newest is None else stamp_of(newest)


def approval_is_attested(events: Sequence[StatusEvent], wp_id: str) -> bool:
    """True iff *wp_id*'s newest approval is an operator attestation (:data:`APPROVED_REVIEWED`), not a review approval (plan D-5)."""
    newest = _newest_approval(events, wp_id)
    return newest is not None and is_approved_reviewed_attestation(newest.policy_metadata)


def _latest_stamp(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """The newest stamp *wp_id*'s non-migration events carry, or ``None`` when none carries one.

    The newest STAMPED event, not the newest event: an operator attestation recorded
    when the probe could not read the lane carries no stamp, and must not hide the stamp
    the canceled work package's own transitions took.
    """
    stamp: str | None = None
    for event in events:
        if event.wp_id == wp_id and not is_migration_event(event):
            stamp = stamp_of(event) or stamp
    return stamp


def commits_beyond(repo_root: Path, tip: str, excluded: Sequence[str]) -> list[str]:
    """Commits reachable from *tip* and from none of *excluded*, newest first.

    The intersection of ``ref..tip`` over every excluded ref: the FULL commit range, a
    commit reached through any merge parent included, never the first-parent spine.
    Raises :class:`~specify_cli.consolidation.git_probes.GitProbeError` when a ref does
    not resolve (fail-closed, as every sibling probe).
    """
    if not excluded:
        raise ValueError("commits_beyond needs at least one excluded ref")
    beyond = commits_in_range(repo_root, excluded[0], tip)
    for ref in excluded[1:]:
        if not beyond:
            break
        reachable = set(commits_in_range(repo_root, ref, tip))
        beyond = [sha for sha in beyond if sha in reachable]
    return beyond


def content_commits(repo_root: Path, commits: Iterable[str], is_bookkeeping: Callable[[str], bool]) -> list[tuple[str, str]]:
    """The ``(sha, first content path)`` of every commit that is real content.

    Merge commits are tool-made movement (a dependency, mission-branch or target sync)
    and a commit that touches only bookkeeping paths is housekeeping; neither counts.
    """
    content: list[tuple[str, str]] = []
    for sha in commits:
        if is_merge_commit(repo_root, sha):
            continue
        path = next((candidate for candidate in changed_paths_of(repo_root, sha) if not is_bookkeeping(candidate)), None)
        if path is not None:
            content.append((sha, path))
    return content


def resolves_commit(repo_root: Path, ref: str) -> bool:
    """True iff *ref* names a commit now."""
    try:
        resolve_commit(repo_root, ref)
    except GitProbeError:
        return False
    return True


def _covered_points(
    repo_root: Path,
    events: Sequence[StatusEvent],
    branch: str,
    approval_stamps: Iterable[str],
    canceled_wp_ids: Iterable[str],
) -> list[str]:
    """The commits whose history is already accounted for: approval stamps and canceled work packages' latest stamps.

    A canceled work package's covered point is dropped when it is not on the lane (the
    existing closed world owns a mixed lane's canceled work), and a canceled work package
    with no stamp at all contributes none: its commits are beyond the bound. An approval
    stamp is validated by the caller.
    """
    covered = list(approval_stamps)
    for wp_id in sorted(canceled_wp_ids):
        stamp = _latest_stamp(events, wp_id)
        if stamp is not None and sha_reachable_from(repo_root, stamp, branch):
            covered.append(stamp)
    return covered


def check_lane(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    canceled_wp_ids: Iterable[str],
    claim_base: str,
    anchors: Iterable[str],
    is_bookkeeping: Callable[[str], bool],
    tip: str | None = None,
) -> BoundRefusal | None:
    """Refuse *lane_id* when it is not within what review approved, else ``None`` (plan D-2).

    *branch* names the lane in the refusal; *tip* (default *branch*) is what is read, so a
    caller that froze the lane tip once reads exactly that commit. *anchors* are the
    lane-base anchors (dependency-lane tips, the target's pre-consolidation tip, the
    other lanes' approval stamps); *claim_base* bounds the lane's own range and must
    predate every commit the run merges (a live mission-branch tip does not). A lane with no commit
    beyond *claim_base* has nothing to bound and is not refused. A *claim_base* or lane tip that
    does not resolve raises :class:`~specify_cli.consolidation.git_probes.GitProbeError`: the
    check never passes for want of an answer, and every caller turns the error into a refusal.
    """
    lane_tip = tip or branch
    if not commits_in_range(repo_root, claim_base, lane_tip):
        return None
    approved = tuple(sorted(approved_wp_ids))
    stamps = {wp_id: approval_stamp(events, wp_id) for wp_id in approved}
    missing = tuple(wp_id for wp_id, stamp in stamps.items() if stamp is None)
    if missing:
        return BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_MISSING, lane_id, branch, missing)
    for wp_id, stamp in stamps.items():
        if stamp is not None and not sha_reachable_from(repo_root, stamp, lane_tip):
            return BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE, lane_id, branch, (wp_id,), stamp=stamp)
    covered = _covered_points(repo_root, events, lane_tip, (stamp for stamp in stamps.values() if stamp is not None), canceled_wp_ids)
    exempt = lane_exempt_commits(repo_root, claim_base, anchors)
    beyond = [sha for sha in commits_beyond(repo_root, lane_tip, [claim_base, *covered]) if sha not in exempt]
    content = content_commits(repo_root, beyond, is_bookkeeping)
    if not content:
        return None
    return BoundRefusal(
        BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
        lane_id,
        branch,
        approved,
        commits=tuple(sha for sha, _path in content),
        path=content[0][1],
    )


__all__ = [
    "APPROVED_REVIEWED",
    "ATTEST_APPROVED_FLAG",
    "BoundRefusal",
    "BoundRefusalCode",
    "approval_stamp",
    "check_lane",
    "commits_beyond",
    "content_commits",
    "is_approved_reviewed_attestation",
    "resolves_commit",
]
