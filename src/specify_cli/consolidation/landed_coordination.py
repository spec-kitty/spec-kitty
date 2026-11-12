"""The coordination tip a verified landing covered, kept where it outlives the consolidation record.

``refs/spec-kitty/landed-coordination/<coordination branch>`` names the coordination-branch tip whose
records a reconciliation PASS (and, after it, a proven late-window advance) showed are on the target.
The consolidation record (``ConsolidationState``) carries the same tip as
``coord_tip_after_projection`` while the run is in flight; the record is cleared when the run
finishes, the ref is not, so a later reclaim of a kept coordination branch (#4041) can tell which
coordination commits a landing already covered.

This module is the single authority for that ref. It is modelled on
:mod:`specify_cli.lanes.lane_tip` (``refs/spec-kitty/lane-tip/<branch>``) and writes only through the
bookkeeping-ref owner in :mod:`specify_cli.git.ref_advance`.

Soundness rules (operator rulings for #4041 and #7491):

* The ref is written only after a verified PASS, so it never names a tip whose landing was not proven.
* It only moves forward: an advance is accepted only when the recorded tip is an ancestor of the new
  one, and the write is a compare-and-swap on the value read.
* It exists only while its landing stands: the rollback authority deletes it when it restores the
  target off a landing (:func:`clear_landed_coordination_tip`).
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.consolidation.git_probes import commit_in_clone, is_ancestor_strict, resolve_commit
from specify_cli.git.ref_advance import delete_bookkeeping_ref, write_bookkeeping_ref

# The read side (LANDED_COORDINATION_REF_PREFIX, landed_coordination_ref, landed_coordination_tip) is exported by WP04 (#4041),
# which adds it to __all__ with its first caller.
__all__ = [
    "LandedCoordinationRefError",
    "clear_landed_coordination_tip",
    "record_landed_coordination_tip",
]

#: Namespace of the landed-coordination refs, one per coordination branch.
LANDED_COORDINATION_REF_PREFIX = "refs/spec-kitty/landed-coordination/"

_HEADS_PREFIX = "refs/heads/"


class LandedCoordinationRefError(RuntimeError):
    """The landed-coordination ref could not be written or moved as asked."""

    error_code = "LANDED_COORDINATION_REF_REFUSED"


def landed_coordination_ref(coordination_branch: str) -> str:
    """Return the ref that records *coordination_branch*'s landed tip (a ``refs/heads/`` prefix is dropped)."""
    branch = coordination_branch.removeprefix(_HEADS_PREFIX)
    if not branch:
        raise ValueError("a landed-coordination ref needs a coordination branch name")
    return f"{LANDED_COORDINATION_REF_PREFIX}{branch}"


def landed_coordination_tip(repo_root: Path, coordination_branch: str) -> str | None:
    """Return the recorded landed coordination tip for *coordination_branch*, or ``None`` when none is recorded.

    Raises:
        GitProbeError: git could not answer (never read as "no record").
    """
    ref = landed_coordination_ref(coordination_branch)
    if not commit_in_clone(repo_root, ref):
        return None
    tip: str = resolve_commit(repo_root, ref)
    return tip


def record_landed_coordination_tip(repo_root: Path, coordination_branch: str, tip: str) -> None:
    """Create the ref at *tip*, or advance it to *tip* when the recorded tip is an ancestor of it.

    Re-recording the same tip is a no-op. The write is a compare-and-swap on the value read here, so a
    concurrent writer makes it fail rather than be overwritten.

    Raises:
        LandedCoordinationRefError: the recorded tip is not an ancestor of *tip* (a rewritten or
            unrelated history), or the compare-and-swap write failed.
        GitProbeError: git could not answer the read or the ancestry question.
    """
    if not tip:
        raise ValueError("a landed coordination tip must name a commit")
    ref = landed_coordination_ref(coordination_branch)
    recorded = landed_coordination_tip(repo_root, coordination_branch)
    if recorded == tip:
        return
    if recorded is None:
        written = write_bookkeeping_ref(repo_root, ref, tip, create_only=True)
    elif is_ancestor_strict(repo_root, recorded, tip):
        written = write_bookkeeping_ref(repo_root, ref, tip, expected_old=recorded)
    else:
        raise LandedCoordinationRefError(f"{ref} records {recorded[:12]}, which is not an ancestor of {tip[:12]}; the landed tip only moves forward")
    if not written:
        raise LandedCoordinationRefError(f"{ref} moved while it was being advanced to {tip[:12]}; nothing was written")


def clear_landed_coordination_tip(repo_root: Path, coordination_branch: str) -> bool:
    """Delete the ref for *coordination_branch*; return ``True`` on success (an absent ref succeeds)."""
    deleted: bool = delete_bookkeeping_ref(repo_root, landed_coordination_ref(coordination_branch))
    return deleted
