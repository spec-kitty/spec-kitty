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
  (``APPROVAL_STAMP_NOT_ON_LANE``). The approval may also record ``lane_head_presync``, the lane
  tip before the review's own sync merge(s) (#7802); the effective stamp is whichever recorded
  stamp the lane contains (:func:`effective_stamp`), and a stamp whose object is not in this
  clone at all gets its own remedy (push the lane from the reviewer's clone);
* a content commit reachable from no approval stamp, from no anchor and not from the claim
  base refuses (``LANE_MOVED_AFTER_APPROVAL``). Nothing a canceled work package of the lane
  does covers a commit (#5720): this module reads no event of a canceled work package and
  no attestation, so a commit that work package made after the approval, in its own stamped
  work window or not, refuses until the approved work package is approved again. The
  canceled-content checks then judge the lane the reviewer saw. The whole commit range is walked,
  never the first-parent spine: a late commit that arrives through a merge from a branch
  that is not an anchor is found. Merge commits and commits that touch only bookkeeping
  paths are tool-made movement and never count.

Pure functions over a status event list and git probes; no status write, no lane
state, no prompt. The claim builder calls it before any branch moves
(:func:`specify_cli.consolidation.reconciliation.approved_bound_refusal`).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from specify_cli.status import LANE_HEAD_KEY, LANE_HEAD_PRESYNC_KEY, StatusEvent, is_migration_event, stamp_of

from .canceled_attestation import ATTESTATION_KEY
from .git_probes import GitProbeError, changed_paths_of, commit_in_clone, commits_in_range, is_merge_commit, resolve_commit, sha_reachable_from
from .wp_attribution import lane_exempt_commits

logger = logging.getLogger(__name__)

#: ``policy_metadata[ATTESTATION_KEY]`` value an operator attestation of an approval records.
APPROVED_REVIEWED = "approved_reviewed"
#: The CLI flag that lifts :attr:`BoundRefusalCode.APPROVAL_STAMP_MISSING` for one work package.
ATTEST_APPROVED_FLAG = "--attest-approved-reviewed"

_APPROVED_LANE = "approved"
_DONE_LANE = "done"
_IN_REVIEW_LANE = "in_review"
_APPROVED_VERDICT = "approved"
_MAX_NAMED_COMMITS = 3
_SHORT_SHA = 7
_ATTEST_REASON = '--attest-reason "<what you checked>"'
_STAMP_NAME = "approval stamp"
_STAMP_DEFINITION = f"{_STAMP_NAME} (the lane commit recorded when review approved it)"
_COMMAND_INDENT = "  "


class BoundRefusalCode(StrEnum):
    """The stable codes of the three refusals this module produces."""

    LANE_MOVED_AFTER_APPROVAL = "LANE_MOVED_AFTER_APPROVAL"
    APPROVAL_STAMP_MISSING = "APPROVAL_STAMP_MISSING"
    APPROVAL_STAMP_NOT_ON_LANE = "APPROVAL_STAMP_NOT_ON_LANE"


class StampDetail(StrEnum):
    """Why no recorded approval stamp is on the lane (#7802); the refusal code stays ``APPROVAL_STAMP_NOT_ON_LANE``."""

    #: No recorded stamp names a commit in this clone: the reviewer's clone holds it and never pushed it.
    ABSENT_FROM_CLONE = "absent_from_clone"
    #: A recorded stamp is in this clone but the lane does not reach it: the lane was rewritten.
    NOT_ON_LANE = "not_on_lane"


@dataclass(frozen=True)
class StampVerdict:
    """The effective approval stamp of one approval on one lane tip (:func:`effective_stamp`).

    ``stamp`` is the newest recorded stamp the lane contains (``lane_head``, else
    ``lane_head_presync``), ``None`` when none is on the lane or the approval is unstamped.
    ``recorded`` is the approval's ``lane_head``. ``detail`` says why ``stamp`` is ``None`` for a
    stamped approval, and is ``None`` otherwise.
    """

    stamp: str | None
    recorded: str | None
    detail: StampDetail | None = None


def _recorded_sha(metadata: Mapping[str, object] | None, key: str) -> str | None:
    value = metadata.get(key) if isinstance(metadata, Mapping) else None
    return value if isinstance(value, str) and value else None


def effective_stamp(repo_root: Path, event_metadata: Mapping[str, object] | None, lane_tip: str) -> StampVerdict:
    """The recorded approval stamp *lane_tip* contains: ``lane_head`` when reachable, else ``lane_head_presync`` (#7802).

    *event_metadata* is the approval event's ``policy_metadata``. An approval with no ``lane_head``
    is unstamped (``StampVerdict(None, None)``): a pre-sync stamp alone never stands in for it.
    The pre-sync stamp is consulted only when ``lane_head`` is absent from this clone (the
    reviewer's unpushed sync merge). A ``lane_head`` present in the clone but off the lane means
    the lane was rewritten after the approval and refuses ``not_on_lane``. When no recorded stamp
    is on the lane the detail is ``absent_from_clone`` when neither names a commit in this clone,
    else ``not_on_lane``.

    The pre-sync stamp keeps the bound sound: the status pipeline records it only when every
    commit between it and ``lane_head`` is a merge commit, and both tiers of the bound drop merge
    commits, so measuring from it judges every content commit ``lane_head`` would have judged.
    A happy-path lane costs one ``merge-base --is-ancestor``, as before. A git failure in the
    absence probe raises :class:`~specify_cli.consolidation.git_probes.GitProbeError`.
    """
    head = _recorded_sha(event_metadata, LANE_HEAD_KEY)
    if head is None:
        return StampVerdict(None, None)
    if sha_reachable_from(repo_root, head, lane_tip):
        return StampVerdict(head, head)
    if commit_in_clone(repo_root, head):
        # ``lane_head`` is here but off the lane: the lane was rewritten after the approval.
        # The pre-sync fallback is only for a ``lane_head`` this clone never received
        # (the reviewer's unpushed sync merge), so it never stands in here (Tier R N1).
        return StampVerdict(None, head, StampDetail.NOT_ON_LANE)
    presync = _recorded_sha(event_metadata, LANE_HEAD_PRESYNC_KEY)
    if presync is None or presync == head:
        return StampVerdict(None, head, StampDetail.ABSENT_FROM_CLONE)
    if sha_reachable_from(repo_root, presync, lane_tip):
        return StampVerdict(presync, head)
    detail = StampDetail.NOT_ON_LANE if commit_in_clone(repo_root, presync) else StampDetail.ABSENT_FROM_CLONE
    return StampVerdict(None, head, detail)


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
    #: A window refusal only: the commit precedes every newest approval stamp on the branch, so ``wp_ids``
    #: names the first work package approved after it, and approving again cannot cover it.
    precedes_approvals: bool = False
    #: ``APPROVAL_STAMP_NOT_ON_LANE`` only: why no recorded stamp is on the lane (#7802).
    stamp_detail: StampDetail | None = None

    def render(self, mission_slug: str) -> str:
        """The operator-facing text of this one refusal, led by ``<CODE>: `` like the other claim refusals."""
        return render_refusals([self], mission_slug)


def _short(sha: str | None) -> str:
    return (sha or "")[:_SHORT_SHA]


def move_back_command(wp_id: str, mission_slug: str) -> str:
    """The command that sends *wp_id* of *mission_slug* back to ``in_progress`` for rework and re-review."""
    return f"spec-kitty agent tasks move-task {wp_id} --to in_progress --mission {mission_slug}"


def attest_command(wp_ids: Sequence[str], mission_slug: str) -> str:
    """One ``consolidate`` command attesting every work package of *wp_ids* (``APPROVAL_STAMP_MISSING`` only)."""
    flags = " ".join(f"{ATTEST_APPROVED_FLAG} {wp_id}" for wp_id in wp_ids)
    return f"spec-kitty consolidate --mission {mission_slug} {flags} {_ATTEST_REASON}"


class _StampTerm:
    """Names the approval stamp: defined on first use, short after, so a text defines it once."""

    def __init__(self) -> None:
        self._defined = False

    def __call__(self) -> str:
        if self._defined:
            return _STAMP_NAME
        self._defined = True
        return _STAMP_DEFINITION


def _distinct_wp_ids(group: Sequence[BoundRefusal]) -> list[str]:
    return list(dict.fromkeys(wp_id for refusal in group for wp_id in refusal.wp_ids))


def _send_back_recovery(wp_ids: Sequence[str], mission: str, purpose: str) -> list[str]:
    """The move-back block shared by the two refusals only a review can lift: one command per work package, then the re-approval."""
    pronoun = "it" if len(wp_ids) == 1 else "them"
    return [
        f"Recovery: send {', '.join(wp_ids)} back for review so {purpose}:",
        *(f"{_COMMAND_INDENT}{move_back_command(wp_id, mission)}" for wp_id in wp_ids),
        f"Then approve {pronoun} again and re-run spec-kitty consolidate.",
    ]


def _missing_block(group: Sequence[BoundRefusal], mission: str, term: _StampTerm) -> list[str]:
    findings: list[str] = []
    for refusal in group:
        for wp_id in refusal.wp_ids:
            suffix = "." if findings else ", so the commit review approved cannot be determined."
            findings.append(f"{wp_id} ({refusal.lane_id}) has no {term()}{suffix}")
    wps = _distinct_wp_ids(group)
    noun = "approval" if len(wps) == 1 else "approvals"
    return [
        f"{BoundRefusalCode.APPROVAL_STAMP_MISSING.value}: {findings[0]}",
        *findings[1:],
        f"Recovery, either attest the {noun} after checking by hand that the lane holds only reviewed work:",
        f"{_COMMAND_INDENT}{attest_command(wps, mission)}",
        "or send " + (wps[0] if len(wps) == 1 else f"each of {', '.join(wps)}") + " back for review:",
        *(f"{_COMMAND_INDENT}{move_back_command(wp_id, mission)}" for wp_id in wps),
        f"and, after approving {'it' if len(wps) == 1 else 'them'} again, re-run spec-kitty consolidate.",
    ]


def _is_absent(refusal: BoundRefusal) -> bool:
    return refusal.stamp_detail is StampDetail.ABSENT_FROM_CLONE


def _not_on_lane_finding(refusal: BoundRefusal, term: _StampTerm) -> str:
    where = f"branch '{refusal.branch}' (lane {refusal.lane_id})"
    if _is_absent(refusal):
        return (
            f"{refusal.wp_ids[0]}'s {term()} is {_short(refusal.stamp)}, which is not in this clone: "
            f"the reviewer's clone recorded it and {where} here does not hold it."
        )
    return f"{refusal.wp_ids[0]}'s {term()} is {_short(refusal.stamp)}, which is not on {where}: the lane was rewritten after review approved it."


def _push_recovery(absent: Sequence[BoundRefusal]) -> list[str]:
    """The push alternative of an absent stamp (#7802): one ``git push`` per lane, run in the reviewer's clone."""
    branches = list(dict.fromkeys(refusal.branch for refusal in absent))
    return [
        f"Recovery for {', '.join(_distinct_wp_ids(absent))}: push the lane from the reviewer's clone, which holds that commit:",
        *(f"{_COMMAND_INDENT}git push <remote> {branch}" for branch in branches),
        "then re-run spec-kitty consolidate. Otherwise rework, review and approve again:",
    ]


def _not_on_lane_block(group: Sequence[BoundRefusal], mission: str, term: _StampTerm) -> list[str]:
    findings = [_not_on_lane_finding(refusal, term) for refusal in group]
    absent = [refusal for refusal in group if _is_absent(refusal)]
    purpose = "the lane is reviewed again" if absent else "the rewritten lane is reviewed"
    return [
        f"{BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE.value}: {findings[0]}",
        *findings[1:],
        *(_push_recovery(absent) if absent else []),
        *_send_back_recovery(_distinct_wp_ids(group), mission, purpose),
    ]


def _moved_finding(refusal: BoundRefusal, term: _StampTerm) -> str:
    named = ", ".join(_short(sha) for sha in refusal.commits[:_MAX_NAMED_COMMITS])
    more = len(refusal.commits) - _MAX_NAMED_COMMITS
    if more > 0:
        named += f" and {more} more"
    return (
        f"branch '{refusal.branch}' ({refusal.lane_id} carries {', '.join(refusal.wp_ids)}) holds content committed after its {term()}: "
        f"{named} (e.g. '{refusal.path}'); see one with `git show {_short(refusal.commits[0])}`."
    )


def _moved_block(group: Sequence[BoundRefusal], mission: str, term: _StampTerm) -> list[str]:
    findings = [_moved_finding(refusal, term) for refusal in group]
    return [
        f"{BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL.value}: {findings[0]}",
        *findings[1:],
        *_send_back_recovery(_distinct_wp_ids(group), mission, "the new content is reviewed"),
    ]


def render_refusals(refusals: Sequence[BoundRefusal], mission_slug: str) -> str:
    """One operator-facing text for *refusals*: a short line per refused lane or work package, then ONE recovery block per code.

    The text starts with ``<CODE>: `` (the orchestrator extracts it) and each further code
    starts its own block. The approval stamp is defined once. Every printed command carries
    *mission_slug*, so it runs as printed.
    """
    groups: dict[BoundRefusalCode, list[BoundRefusal]] = {}
    for refusal in refusals:
        groups.setdefault(refusal.code, []).append(refusal)
    term = _StampTerm()
    blocks = {
        BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL: _moved_block,
        BoundRefusalCode.APPROVAL_STAMP_MISSING: _missing_block,
        BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE: _not_on_lane_block,
    }
    return "\n".join(line for code, group in groups.items() for line in blocks[code](group, mission_slug, term))


def refusal_codes(text: str) -> list[str]:
    """Every distinct :class:`BoundRefusalCode` that leads a line of *text*, in order of first appearance.

    :func:`render_refusals` starts each code's block with ``<CODE>: ``. A consumer that
    keys on codes (``orchestrator-api consolidate-mission``) reads them here, so the code
    list is exactly what the text names: one entry per distinct code, never a guess.
    """
    pattern = "|".join(re.escape(code.value) for code in BoundRefusalCode)
    return list(dict.fromkeys(re.findall(rf"^({pattern}): ", text, flags=re.MULTILINE)))


def is_approved_reviewed_attestation(policy_metadata: Mapping[str, object] | None) -> bool:
    """True iff *policy_metadata* (an event's, parsed or raw) marks an operator attestation of an approval, which is not a review.

    The one test of that marker, for every reader that must tell an attestation from a
    review approval (the stamp readers here, the hollow-review merge gate).
    """
    return isinstance(policy_metadata, Mapping) and policy_metadata.get(ATTESTATION_KEY) == APPROVED_REVIEWED


def _is_approval_transition(event: StatusEvent) -> bool:
    """True iff *event* is a move that can be a review's approval of a work package.

    Two transitions are: ``-> approved``, and an unforced ``in_review -> done``, which the
    state machine allows and which finishes a review that approved the work without the
    ``approved`` stop (its stamp is the reviewed tip). The ``approved -> done`` record the
    run itself writes is not one, and neither is a forced move to ``done``: neither is a
    review. An operator attestation of an approval is read separately. A forced move to
    ``approved`` is only a candidate: :func:`_is_forced_review_approval` decides it.
    """
    if str(event.to_lane) == _APPROVED_LANE:
        return True
    return str(event.to_lane) == _DONE_LANE and not event.force and str(event.from_lane) != _APPROVED_LANE


def _entered_review_by_claim(earlier: Sequence[StatusEvent], wp_id: str) -> bool:
    """True iff *wp_id*'s latest move into ``in_review`` in *earlier* is a reviewer's claim, i.e. not forced.

    ``agent action review`` (and an unforced ``move-task --to in_review``) records the claim as an
    unforced ``for_review -> in_review``. A forced move into ``in_review`` is the operator placing the
    work package there; no reviewer claimed it (#5721).
    """
    entry = next((event for event in reversed(earlier) if event.wp_id == wp_id and str(event.to_lane) == _IN_REVIEW_LANE), None)
    return entry is not None and not entry.force


def _is_claimed_review_verdict(event: StatusEvent, earlier: Sequence[StatusEvent]) -> bool:
    """True iff the forced *event* is a reviewer's approval verdict: a hop out of ``in_review`` that carries an
    approved ``review_result``, after a review claim (:func:`_entered_review_by_claim`).

    Nothing else the event carries is a review (#5721): an ``evidence.review`` reference (a typed
    ``--approval-ref``, the synthetic ``auto-approval:`` token, or the ``review-cycle://`` pointer the
    approval's own auto-committed artifact yields) and a reviewer name are written by the forced move itself.
    """
    result = event.review_result
    return str(event.from_lane) == _IN_REVIEW_LANE and result is not None and result.verdict == _APPROVED_VERDICT and _entered_review_by_claim(earlier, event.wp_id)


def _is_forced_review_approval(event: StatusEvent, earlier: Callable[[], Sequence[StatusEvent]]) -> bool:
    """True iff the forced move to ``approved`` *event* is a review's approval (#5721).

    Two are: a reviewer's verdict on a claimed review (:func:`_is_claimed_review_verdict`) and an
    arbiter override of a rejection; both are judged on the log strictly before *event* (*earlier*
    builds it). An approved-reviewed attestation is read before this is asked. Any other forced
    move is the operator restamping the lane, which is no review.
    """
    # Lazy, like every consolidation -> review import (preflight's too): no consolidation
    # module loads a review module at import time, and only a forced approval needs this one.
    from specify_cli.review.arbiter import is_arbiter_override_history

    log = earlier()
    if _is_claimed_review_verdict(event, log):
        return True
    return bool(is_arbiter_override_history(log, event.wp_id, str(event.from_lane), _APPROVED_LANE, True))


def _is_forced_approved_move(event: StatusEvent) -> bool:
    return event.force and str(event.to_lane) == _APPROVED_LANE and not is_approved_reviewed_attestation(event.policy_metadata)


def _is_approval(events: Sequence[StatusEvent], index: int) -> bool:
    """True iff ``events[index]`` is an approval: the log before it only matters to a forced move to ``approved``."""
    event = events[index]
    if is_approved_reviewed_attestation(event.policy_metadata):
        return True
    if not _is_approval_transition(event):
        return False
    return not _is_forced_approved_move(event) or _is_forced_review_approval(event, lambda: events[:index])


def _newest_approval(events: Sequence[StatusEvent], wp_id: str) -> StatusEvent | None:
    """*wp_id*'s newest approval event, or ``None`` when it has none.

    Walks *events* in append order. An approval is an approval transition
    (:func:`_is_approval_transition`) or an operator attestation of an approval
    (:data:`APPROVED_REVIEWED`, any ``to_lane``). The ``approved -> done`` event is
    neither, so the restamp the run itself writes is never read; forced moves to ``done``
    and migration-synthesized events (FR-011) never count. A forced move to ``approved``
    that records no review (:func:`_is_forced_review_approval`) is skipped, so the newest
    review approval stays the bound (#5721).
    """
    newest: StatusEvent | None = None
    for index, event in enumerate(events):
        if event.wp_id == wp_id and not is_migration_event(event) and _is_approval(events, index):
            newest = event
    return newest


def approval_metadata(events: Sequence[StatusEvent], wp_id: str) -> Mapping[str, object] | None:
    """The ``policy_metadata`` of *wp_id*'s newest approval (the input of :func:`effective_stamp`), ``None`` when it has none."""
    newest = _newest_approval(events, wp_id)
    return None if newest is None else newest.policy_metadata


def approval_presync_stamp(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """The ``lane_head_presync`` stamp of *wp_id*'s newest approval (#7802), ``None`` when it records none."""
    return _recorded_sha(approval_metadata(events, wp_id), LANE_HEAD_PRESYNC_KEY)


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


def _maps_to_code_lane(repo_root: Path, mission_slug: str, wp_id: str) -> bool:
    """True iff *wp_id* is assigned to a code (non-planning) lane of *mission_slug*; any lookup failure reads as False."""
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.lanes.persistence import read_lanes_json

    try:
        manifest = read_lanes_json(placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK))
    except Exception:
        # The warning is advisory and printed after the transition landed: a lookup failure must not fail it.
        logger.debug("could not read lanes.json for %s to check %s's approval stamp", mission_slug, wp_id, exc_info=True)
        return False
    lane = None if manifest is None else manifest.lane_for_wp(wp_id)
    return lane is not None and not is_planning_lane(lane)


def _approval_is_bounded(repo_root: Path, mission_slug: str, wp_id: str) -> bool:
    """True iff ``consolidate`` bounds *wp_id*'s approval by its stamp; any lookup failure reads as False.

    Two shapes are bounded: a work package in a code (non-planning) lane
    (:func:`_maps_to_code_lane`), and every work package of a Mission whose STORED topology
    is ``single_branch`` with a minted Mission branch (S8, #7283). A commit-to-target
    ``single_branch`` Mission (write branch == target) and a ``lanes`` planning lane are
    not bounded (FR-078).
    """
    if _maps_to_code_lane(repo_root, mission_slug, wp_id):
        return True
    from specify_cli.lanes.single_branch_landing import minted_write_branch

    try:
        return minted_write_branch(repo_root, mission_slug) is not None
    except Exception:
        # The warning is advisory and printed after the transition landed: a lookup failure must not fail it.
        logger.debug("could not read meta.json for %s to check %s's approval stamp", mission_slug, wp_id, exc_info=True)
        return False


def unstamped_approval_warning(event: StatusEvent | None, *, repo_root: Path, mission_slug: str) -> str | None:
    """The one-line warning for an approval that was persisted without an approval stamp, else ``None``.

    The stamp is best-effort (the status pipeline never refuses a transition for want of
    one), while ``consolidate`` refuses an approved work package that has none. This is
    what the shells that persist an approval print, so the operator learns it at approval
    time. Only a work package whose approval is bounded (:func:`_approval_is_bounded`) is
    warned about: a ``lanes`` planning lane and a commit-to-target ``single_branch`` Mission
    are never bounded.
    """
    if event is None or not _is_approval_transition(event) or stamp_of(event) is not None:
        return None
    if not _approval_is_bounded(repo_root, mission_slug, event.wp_id):
        return None
    return (
        f"Warning: no lane head could be recorded for {event.wp_id}'s approval; `spec-kitty consolidate` will refuse it "
        f"({BoundRefusalCode.APPROVAL_STAMP_MISSING.value}) until it is approved again or attested."
    )


def _log_before(events: Sequence[StatusEvent], event: StatusEvent) -> Sequence[StatusEvent]:
    """The part of *events* strictly before *event* (all of it when *event* is not in the log)."""
    for index, candidate in enumerate(events):
        if candidate.event_id == event.event_id:
            return events[:index]
    return events


def forced_approval_warning(event: StatusEvent | None, load_events: Callable[[], Sequence[StatusEvent]]) -> str | None:
    """The one-line warning for a forced move to ``approved`` that records no review, else ``None`` (#5721).

    Such a move is not a review approval, so it does not restamp the approval bound:
    ``consolidate`` keeps the work package bound at its last review approval. Whether it is a
    review is judged against the log strictly before *event*, read through *load_events*
    (:func:`_is_forced_review_approval`); a log or an event that cannot be classified is no warning
    (the warning is advisory and printed after the transition landed).
    """
    if event is None or not _is_forced_approved_move(event):
        return None
    try:
        is_review = _is_forced_review_approval(event, lambda: _log_before(load_events(), event))
    except Exception:
        # Advisory only, printed after the transition landed: a log or an event it cannot
        # classify never turns a recorded move into a failed command.
        logger.debug("could not classify %s's forced approval", event.wp_id, exc_info=True)
        return None
    if is_review:
        return None
    return (
        f"Warning: the forced approval of {event.wp_id} is not a review approval; `spec-kitty consolidate` still bounds "
        f"{event.wp_id} at its last review approval (commits made since refuse with {BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL.value}), "
        "and refuses it as unstamped when it has none."
    )


def approval_warnings(event: StatusEvent | None, load_events: Callable[[], Sequence[StatusEvent]], *, repo_root: Path, mission_slug: str) -> list[str]:
    """The warning lines a shell prints after persisting *event*, classified once (#5668, #5721).

    A forced approval that is not a review gets :func:`forced_approval_warning` only: that line
    already says an unstamped work package refuses. Every other approval, an arbiter override
    or a forced approval that could not be classified included, gets
    :func:`unstamped_approval_warning` when it recorded no approval stamp. Neither line prints
    for a work package whose approval is not bounded (:func:`_approval_is_bounded`): a
    ``lanes`` planning lane and a commit-to-target ``single_branch`` Mission, which
    ``consolidate`` does not bound, so it has nothing to say about them.
    """
    try:
        if event is None or not _approval_is_bounded(repo_root, mission_slug, event.wp_id):
            return []
        forced = forced_approval_warning(event, load_events)
        if forced is not None:
            return [forced]
        unstamped = unstamped_approval_warning(event, repo_root=repo_root, mission_slug=mission_slug)
    except Exception:
        # Advisory only, printed after the move landed: an event the shell cannot
        # classify never turns a recorded transition into a failed command.
        logger.debug("could not classify the approval warnings for a persisted event", exc_info=True)
        return []
    return [] if unstamped is None else [unstamped]


def commits_beyond(repo_root: Path, tip: str, excluded: Sequence[str]) -> list[str]:
    """Commits reachable from *tip* and from none of *excluded*, newest first.

    The intersection of ``ref..tip`` over every excluded ref: the FULL commit range, a
    commit reached through any merge parent included, never the first-parent spine.
    *excluded* is never empty (both callers always pass the claim base or the lane's own
    validated tip). Raises :class:`~specify_cli.consolidation.git_probes.GitProbeError`
    when a ref does not resolve (fail-closed, as every sibling probe).
    """
    beyond: list[str] = commits_in_range(repo_root, excluded[0], tip)
    for ref in excluded[1:]:
        if not beyond:
            break
        reachable = set(commits_in_range(repo_root, ref, tip))
        beyond = [sha for sha in beyond if sha in reachable]
    return beyond


def content_commits(repo_root: Path, commits: Iterable[str], is_bookkeeping: Callable[[str], bool]) -> list[tuple[str, str]]:
    """The ``(sha, first content path)`` of every commit that is real content.

    Merge commits are tool-made movement (a dependency, mission-branch or target sync, or a
    lane auto-rebase that resolved a conflict itself) and a commit that touches only
    bookkeeping paths is housekeeping; neither counts.
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


def approval_stamps(events: Sequence[StatusEvent], wp_ids: Iterable[str]) -> dict[str, str | None]:
    """``{wp_id: approval stamp or None}`` for *wp_ids*, in the given order (:func:`approval_stamp` each)."""
    return {wp_id: approval_stamp(events, wp_id) for wp_id in wp_ids}


def approval_presync_stamps(events: Sequence[StatusEvent], wp_ids: Iterable[str]) -> dict[str, str | None]:
    """``{wp_id: pre-sync stamp or None}`` for *wp_ids*, in the given order (:func:`approval_presync_stamp` each, #7802)."""
    return {wp_id: approval_presync_stamp(events, wp_id) for wp_id in wp_ids}


def _resolve_stamps(
    repo_root: Path,
    *,
    stamps: Mapping[str, str | None],
    presync_stamps: Mapping[str, str | None] | None,
    lane_id: str,
    branch: str,
    lane_tip: str,
) -> tuple[BoundRefusal | None, dict[str, str]]:
    """``(refusal, {wp_id: effective stamp})`` for *stamps* on *lane_tip* (the stamp-resolution half of :func:`check_lane`).

    Every work package with no stamp refuses together (``APPROVAL_STAMP_MISSING``), before any
    reachability probe; else the first work package, in *stamps* order, whose effective stamp
    (:func:`effective_stamp`: its ``lane_head``, else its *presync_stamps* entry) *lane_tip* does
    not reach refuses (``APPROVAL_STAMP_NOT_ON_LANE``, with the ``absent_from_clone`` /
    ``not_on_lane`` detail). A probe error raises
    :class:`~specify_cli.consolidation.git_probes.GitProbeError`.
    """
    missing = tuple(wp_id for wp_id, stamp in stamps.items() if stamp is None)
    if missing:
        return BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_MISSING, lane_id, branch, missing), {}
    effective: dict[str, str] = {}
    for wp_id, stamp in stamps.items():
        metadata = {LANE_HEAD_KEY: stamp, LANE_HEAD_PRESYNC_KEY: (presync_stamps or {}).get(wp_id)}
        verdict = effective_stamp(repo_root, metadata, lane_tip)
        if verdict.stamp is None:
            refusal = BoundRefusal(BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE, lane_id, branch, (wp_id,), stamp=stamp, stamp_detail=verdict.detail)
            return refusal, {}
        effective[wp_id] = verdict.stamp
    return None, effective


def check_lane(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    claim_base: str,
    anchors: Iterable[str],
    is_bookkeeping: Callable[[str], bool],
    tip: str | None = None,
    exempt: frozenset[str] | None = None,
) -> BoundRefusal | None:
    """Refuse *lane_id* when it is not within what review approved, else ``None`` (plan D-2).

    *branch* names the lane in the refusal; *tip* (default *branch*) is what is read, so a
    caller that froze the lane tip once reads exactly that commit. *anchors* are the
    lane-base anchors (dependency-lane tips, the target's pre-consolidation tip, the
    other lanes' approval stamps); *claim_base* bounds the lane's own range and must
    predate every commit the run merges (a live mission-branch tip does not).
    Only *approved_wp_ids* are read from *events*: a canceled work package of the lane
    covers no commit, whatever it recorded. Each approval is measured from its effective stamp
    (:func:`effective_stamp`, #7802). A lane with no commit
    beyond *claim_base* has nothing to bound and is not refused. A *claim_base* or lane tip that
    does not resolve raises :class:`~specify_cli.consolidation.git_probes.GitProbeError`: the
    check never passes for want of an answer, and every caller turns the error into a refusal.
    *exempt* is the lane's exempt set when the caller already computed it from *anchors*
    (:func:`~specify_cli.consolidation.wp_attribution.lane_exempt_commits`, once per lane,
    NFR-007); ``None`` computes it here, as every caller before the window model did.
    """
    refusal, _effective = check_lane_effective(
        repo_root,
        events=events,
        lane_id=lane_id,
        branch=branch,
        approved_wp_ids=approved_wp_ids,
        claim_base=claim_base,
        anchors=anchors,
        is_bookkeeping=is_bookkeeping,
        tip=tip,
        exempt=exempt,
    )
    return refusal


def check_lane_effective(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    claim_base: str,
    anchors: Iterable[str],
    is_bookkeeping: Callable[[str], bool],
    tip: str | None = None,
    exempt: frozenset[str] | None = None,
) -> tuple[BoundRefusal | None, dict[str, str] | None]:
    """:func:`check_lane`'s verdict plus ``{wp_id: effective stamp}`` (#7802), read with no extra git probe.

    The second item is ``None`` when the lane has no commit beyond *claim_base* (nothing to
    bound, nothing for a second tier to judge) or the lane refused on its stamps; otherwise it
    maps every work package of *approved_wp_ids* to the stamp the lane contains, which a second
    tier (``write_branch_bound``) uses as its window end.
    """
    lane_tip = tip or branch
    if not commits_in_range(repo_root, claim_base, lane_tip):
        return None, None
    approved = tuple(sorted(approved_wp_ids))
    refusal, effective = _resolve_stamps(
        repo_root,
        stamps=approval_stamps(events, approved),
        presync_stamps=approval_presync_stamps(events, approved),
        lane_id=lane_id,
        branch=branch,
        lane_tip=lane_tip,
    )
    if refusal is not None:
        return refusal, None
    covered = list(effective.values())
    exempt_set = lane_exempt_commits(repo_root, claim_base, anchors) if exempt is None else exempt
    beyond = [sha for sha in commits_beyond(repo_root, lane_tip, [claim_base, *covered]) if sha not in exempt_set]
    content = content_commits(repo_root, beyond, is_bookkeeping)
    if not content:
        return None, effective
    moved = BoundRefusal(
        BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
        lane_id,
        branch,
        approved,
        commits=tuple(sha for sha, _path in content),
        path=content[0][1],
    )
    return moved, effective


__all__ = [
    "APPROVED_REVIEWED",
    "ATTEST_APPROVED_FLAG",
    "BoundRefusal",
    "BoundRefusalCode",
    "approval_presync_stamp",
    "approval_stamp",
    "approval_stamps",
    "approval_warnings",
    "check_lane",
    "check_lane_effective",
    "commits_beyond",
    "content_commits",
    "is_approved_reviewed_attestation",
    "move_back_command",
    "refusal_codes",
    "render_refusals",
    "resolves_commit",
]
