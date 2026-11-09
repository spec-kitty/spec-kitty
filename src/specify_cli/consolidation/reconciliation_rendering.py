"""Refusal and clause text shared by the reconciliation checks (Mission consolidation-window-provenance-01M6Y84D, WP11).

The recovery tail, the compound-refusal separators, the two content error codes and the helpers that
render a divergence entry or join refusals. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

from collections.abc import Sequence

from specify_cli.consolidation.canceled_attestation import ATTEST_FLAG, ATTEST_REASON_FLAG
from specify_cli.consolidation.reconciliation_claim_types import _GAP_ABSENT, CanceledDependencyContent, MissingApprovedContent
from specify_cli.consolidation.wp_attribution import CanceledPathState


# Mixed-lane canceled-content recovery tail (contract C4 / NFR-003, #5046):
# shared by the FAIL rendering (:func:`_describe_canceled_content`) and both
# REFUSE reasons the axis can raise (hoisted per Sonar S1192 — used 4+ times).
_RECOVERY_TAIL = "then re-run spec-kitty consolidate"


#: The compound claim refusal (#5720): the first refusal, then the approved-bound refusals the
#: operator would otherwise meet one run later. The first refusal is never reworded.
_ALSO_HAS = "This Mission also has:"


_BOTH_NEEDED = (
    "Both parts need their own fix, in either order: the recovery in the first part does not approve the new content, "
    "and approving the work package again does not clear the first part. Re-run spec-kitty consolidate after both."
)


#: Error code of the #5571 verdict: an approved lane's final authored content is
#: absent from (or not applied to) the target and no later approved lane
#: superseded the path -- e.g. the operator committed the staged deletions an
#: interrupted run left behind. A content verdict: it FAILs and rolls back.
APPROVED_CONTENT_MISSING = "APPROVED_CONTENT_MISSING"


#: Error code of the #5569 verdict (#5613): a fully-canceled dependency lane's
#: content reached an approved lane through the allocator's fast-forwarded
#: dependency step and is on the target. Rendered alongside the strategy axis's
#: own clause. A content verdict: it FAILs and no attestation lifts it, for a
#: stamped and for a legacy (unstamped) canceled WP alike.
CANCELED_REACHABLE_VIA_DEPENDENCY = "CANCELED_REACHABLE_VIA_DEPENDENCY"


def _describe_canceled_content(entry: CanceledPathState) -> str:
    """Render one mixed-lane canceled-content divergence clause (contract C4).

    Exactly one internal ``;`` — a situation clause naming the path (in single
    quotes) together with its wording, then a recovery clause — matching the
    binding rendering contract with the real-CLI suite
    (``tests/terminus/test_mixed_lane_canceled_content_verdicts.py`` extracts
    the verdict block, splits it on ``;``, and matches each path to its own
    clause; the recovery clause coming AFTER never shadows the situation
    clause a path-substring search finds first).
    """
    who = f"canceled {entry.wp_id}"
    recovery = f"revert {entry.wp_id}'s change to '{entry.path}' on the lane through a surviving WP's governed work, {_RECOVERY_TAIL}"
    if entry.canceled_state is None:
        situation = f"file '{entry.path}' was deleted by {who} (lane {entry.lane_id}) and that deletion is on the target — approved content would be lost"
    else:
        situation = f"file '{entry.path}'{_renamed_note(entry.renamed_from)} carries {who}'s change (lane {entry.lane_id}) on the target — canceled work would ship"
    return f"{situation}; {recovery}"


def _renamed_note(renamed_from: str | None) -> str:
    """`` (renamed from '<old>')`` for canceled content a survivor moved to a new path (#6309), else empty.

    No ``;`` (the clause contract splits situation from recovery on it).
    """
    return f" (renamed from '{renamed_from}')" if renamed_from else ""


def _describe_approved_content_missing(entry: MissingApprovedContent) -> str:
    """Render one #5571 clause: names the approved WP(s), their lane(s) and the path.

    One ``;`` between the situation and the recovery, like
    :func:`_describe_canceled_content`. The recovery names the cause an operator
    can act on: a worktree that was committed while it lagged its own HEAD. The
    axis only reports a path the target itself left alone since the lane was cut
    (:func:`_dropped_own_change`), so the loss is on the mission side and the
    recovery says so: it must never read as advice to revert a target commit.
    """
    who = ", ".join(entry.wp_ids)
    lanes = ", ".join(entry.lane_ids)
    if entry.expected is None:
        what = f"its deletion of '{entry.path}' is not applied to the target"
    elif entry.found == _GAP_ABSENT:
        what = f"file '{entry.path}' is absent from the target"
    else:
        what = f"file '{entry.path}' on the target still holds its pre-consolidation content"
    situation = f"{APPROVED_CONTENT_MISSING}: approved {who} (lane {lanes}) {what} and no later approved WP superseded it — approved work would be dropped"
    recovery = (
        f"restore {who}'s change to '{entry.path}' on the mission branch — the target branch did not change this path, so revert nothing there "
        f"(if you committed the staged changes of a lagging coordination or mission worktree, revert that commit on the mission branch, "
        f"and never commit such changes — discard them with `git reset --hard HEAD`), {_RECOVERY_TAIL}"
    )
    return f"{situation}; {recovery}"


def _describe_canceled_reachable(entry: CanceledDependencyContent) -> str:
    """Render one ``CANCELED_REACHABLE_VIA_DEPENDENCY`` clause: the canceled WP(s), both lanes and the path.

    One ``;`` between the situation and the recovery, like
    :func:`_describe_canceled_content`. No attestation is offered: the content is
    on the target, and an attestation only ever covers attribution evidence.
    """
    who = f"canceled {', '.join(entry.wp_ids)}"
    effect = "its deletion" if entry.state is None else "its change"
    situation = (
        f"{CANCELED_REACHABLE_VIA_DEPENDENCY}: file '{entry.path}'{_renamed_note(entry.renamed_from)} carries {who}'s work "
        f"(lane {entry.canceled_lane_id}), which reached "
        f"approved lane {entry.carrier_lane_id} through a dependency lane, and {effect} IS on the target — canceled work would ship"
    )
    recovery = (
        f"undo {effect} to '{entry.path}' on lane {entry.carrier_lane_id} through a surviving WP's governed work "
        f"(do not rebuild the lane, and no attestation lifts this while the content ships), {_RECOVERY_TAIL}"
    )
    return f"{situation}; {recovery}"


def _join_refusals(refusals: Sequence[str]) -> str:
    """One text for several refusals of one kind, in the order given: every refusal is named, none is reworded.

    One refusal per line: each ends in a sentence of its own, so a ``; `` join would read ``....; mixed lane ...``.
    The sibling multi-refusal texts further down join with ``; `` and stay as they are.
    """
    return "\n".join(refusals)


def _attest_tail(wp_id: str) -> str:
    """The FR-012 override step, named in every REFUSE it can lift."""
    return f're-run spec-kitty consolidate with {ATTEST_FLAG} {wp_id} {ATTEST_REASON_FLAG} "<what you checked>"'


__all__ = [
    "APPROVED_CONTENT_MISSING",
    "CANCELED_REACHABLE_VIA_DEPENDENCY",
    "_ALSO_HAS",
    "_BOTH_NEEDED",
    "_RECOVERY_TAIL",
    "_attest_tail",
    "_describe_approved_content_missing",
    "_describe_canceled_content",
    "_describe_canceled_reachable",
    "_join_refusals",
    "_renamed_note",
]
