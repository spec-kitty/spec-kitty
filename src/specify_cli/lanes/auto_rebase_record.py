"""The durable auto-rebase record (FR-005, research R-03, ``contracts/auto-rebase-record.md``).

* Ref ``refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>`` -> ``<merge-sha>``; one writer:
  ``lanes.auto_rebase.attempt_auto_rebase``, after it creates the merge commit.
* Two readers: the claim-time FR-004 exemption (a merge is tool-made exactly when this ref
  exists and resolves to that SHA) and the rollback, which deletes it after undoing the move.
* The reconciliation gate never reads it (C-002, C-003); it never exempts content.
* Deleted by that rollback and by lane cleanup when the lane branch is removed.

Every ``refs/spec-kitty/**`` write goes through :mod:`specify_cli.git.ref_advance` (C-006). A
read that git cannot answer raises :class:`AutoRebaseRecordError`; it is never "not recorded".
Like :mod:`specify_cli.lanes.lane_tip`, this module never imports ``consolidation.*``.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from specify_cli.git.ref_advance import delete_bookkeeping_ref, delete_bookkeeping_refs, write_bookkeeping_ref

# ``recorded_merges`` is public but joins ``__all__`` only once a caller outside this module exists
# (the dead-symbol gate). ``is_recorded`` (FR-004's claim check) and ``delete`` (the rollback) have one.
__all__ = [
    "AutoRebaseRecordError",
    "delete",
    "delete_for_lane",
    "is_recorded",
    "record",
]

_AUTO_REBASE_REF_PREFIX = "refs/spec-kitty/auto-rebase/"

# A full object name: SHA-1 (40) or SHA-256 (64) hex, lowercase as git prints it.
_FULL_SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


class AutoRebaseRecordError(Exception):
    """A record read could not be answered (git failed, or the ref names another commit)."""


def _require(lane_branch: str, sha: str) -> None:
    if not lane_branch:
        raise ValueError("an auto-rebase record needs the lane branch name")
    if not _FULL_SHA.fullmatch(sha):
        raise ValueError(f"an auto-rebase record needs a full commit SHA, got {sha!r}")


def _lane_prefix(lane_branch: str) -> str:
    return f"{_AUTO_REBASE_REF_PREFIX}{lane_branch}/"


def _record_ref(lane_branch: str, merge_sha: str) -> str:
    """The ref that records ``merge_sha`` as an auto-rebase merge on ``lane_branch``."""
    _require(lane_branch, merge_sha)
    return f"{_lane_prefix(lane_branch)}{merge_sha}"


def record(repo_root: Path, lane_branch: str, merge_sha: str) -> bool:
    """Write the record (create-only); ``True`` when the ref holds ``merge_sha`` afterwards.

    A retried call finds the ref already holding the same SHA and succeeds. A ref holding
    anything else, or any git failure, is ``False``: the writer then halts (NFR-002).
    """
    ref = _record_ref(lane_branch, merge_sha)
    if write_bookkeeping_ref(repo_root, ref, merge_sha, create_only=True):
        return True
    try:
        return is_recorded(repo_root, lane_branch, merge_sha)
    except AutoRebaseRecordError:
        return False


def is_recorded(repo_root: Path, lane_branch: str, sha: str) -> bool:
    """``True`` exactly when the record for ``sha`` exists under ``lane_branch`` and resolves to ``sha``.

    Raises:
        AutoRebaseRecordError: git could not answer, or the record names another commit.
    """
    ref = _record_ref(lane_branch, sha)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AutoRebaseRecordError(f"cannot run git to read {ref} in {repo_root}: {exc}") from exc
    value = result.stdout.strip()
    if result.returncode == 0 and value == sha:
        return True
    if result.returncode == 1 and not value:
        return False
    detail = result.stderr.strip() or (f"it names {value}" if value else f"git exited {result.returncode}")
    raise AutoRebaseRecordError(f"cannot read the auto-rebase record {ref} in {repo_root}: {detail}")


def recorded_merges(repo_root: Path, lane_branch: str) -> frozenset[str]:
    """Every merge SHA recorded under ``lane_branch``, in one git call.

    An empty set from a successful listing means the lane has no record. A nested lane
    branch (``<lane_branch>/...``) has its own records and is not listed here.

    Raises:
        AutoRebaseRecordError: git could not list the refs.
    """
    if not lane_branch:
        raise ValueError("an auto-rebase record needs the lane branch name")
    prefix = _lane_prefix(lane_branch)
    try:
        listing = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)", prefix],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AutoRebaseRecordError(f"cannot run git to list the auto-rebase records in {repo_root}: {exc}") from exc
    if listing.returncode != 0:
        detail = listing.stderr.strip() or f"git exited {listing.returncode}"
        raise AutoRebaseRecordError(f"git could not list the auto-rebase records of {lane_branch} in {repo_root}: {detail}")
    names = (line.removeprefix(prefix) for line in listing.stdout.splitlines() if line.startswith(prefix))
    return frozenset(name for name in names if _FULL_SHA.fullmatch(name))


def delete(repo_root: Path, lane_branch: str, merge_sha: str) -> bool:
    """Delete one record; ``True`` on success, also when it was already absent."""
    return bool(delete_bookkeeping_ref(repo_root, _record_ref(lane_branch, merge_sha)))


def delete_for_lane(repo_root: Path, lane_branch: str) -> tuple[str, ...]:
    """Delete every record of ``lane_branch``; return the refs that could not be deleted.

    Raises:
        AutoRebaseRecordError: the records could not be listed.
    """
    refs = [_record_ref(lane_branch, sha) for sha in sorted(recorded_merges(repo_root, lane_branch))]
    return delete_bookkeeping_refs(repo_root, refs)
