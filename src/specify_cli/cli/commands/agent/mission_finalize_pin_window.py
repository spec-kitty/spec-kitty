"""``finalize-tasks``: the single_branch pin's branch line and evidence-window guard (#7793, #7297).

A ``single_branch`` Mission's implementation evidence window is ``planning_commit..mission_branch``
(:func:`specify_cli.lanes.single_branch_landing.single_branch_evidence_window`). This module keeps
finalize's pin decisions consistent with that window (ADR ``2026-10-04-5`` Amendment 2026-11-22):

* :func:`resolve_pin_line` -- the branch the pin is captured from, refreshed against and derived on
  (``lanes.planning_base.pin_branch_line`` over the stored ``meta.json``).
* :func:`window_keeps_owned_work` -- a candidate pin is acceptable only when, for every work
  package whose ``owned_files`` the recorded window changes, the candidate window still changes
  them. It reads the same evidence the ``move-task`` gate and ``consolidate`` read
  (``consolidation.wp_evidence``), per work package as they do.
* :func:`follow_orphaned_pin` -- the rebased copy of an orphaned pin, matched by patch-id, or the
  named refusal code when there is none.

The window itself stays computed only in ``consolidation.wp_evidence``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from mission_runtime import OwnedCheckout

__all__ = [
    "NO_PATCH_ID_MATCH",
    "WOULD_EMPTY_WINDOW",
    "PinWindowUnreadable",
    "follow_orphaned_pin",
    "resolve_pin_line",
    "window_keeps_owned_work",
]

#: The orphaned pin's change is on no commit of the branch (or the pin has an empty diff).
NO_PATCH_ID_MATCH: Final = "PLANNING_PIN_NO_PATCH_ID_MATCH"
#: The orphaned pin's change is on more than one commit of the branch; finalize never guesses.
PATCH_ID_AMBIGUOUS: Final = "PLANNING_PIN_PATCH_ID_AMBIGUOUS"
#: The candidate pin would drop the committed owned-file work out of the evidence window.
WOULD_EMPTY_WINDOW: Final = "PLANNING_PIN_WOULD_EMPTY_WINDOW"


class PinWindowUnreadable(Exception):
    """The window guard could not read a work package's ownership or the window itself (fail closed)."""


@dataclass(frozen=True)
class _PinLine:
    """Where this Mission's pin lives: the branch, whether the single_branch rules apply, and the
    upstream branches whose copy of the planning commit is never the Mission's own (#7793 B2)."""

    branch: str
    single_branch: bool
    upstream_refs: tuple[str, ...] = ()


def resolve_pin_line(repo_root: Path, mission_slug: str, target_branch: str, *, owned: OwnedCheckout | None = None) -> _PinLine:
    """The pin branch line of *mission_slug*, read from its stored ``meta.json`` (#7297 item 2).

    ``upstream_refs`` are the target branch and the repository's primary branch, less the pin line
    itself: a rebase moves a Mission onto one of them, and a copy of the planning commit already
    there is that upstream's, not the Mission's.
    """
    from mission_runtime import is_single_branch

    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.lanes.planning_base import pin_branch_line
    from specify_cli.lanes.single_branch_landing import stored_mission_meta
    from specify_cli.migration.backfill_topology import stored_topology

    meta: dict[str, Any] = stored_mission_meta(repo_root, mission_slug, owned=owned)
    branch = pin_branch_line(meta, target_branch)
    single_branch = is_single_branch(stored_topology(meta))
    upstream: tuple[str, ...] = ()
    if single_branch:
        primary = resolve_primary_branch(repo_root, bias=False)
        upstream = tuple(dict.fromkeys(ref for ref in (target_branch, primary) if ref and ref != branch))
    return _PinLine(branch=branch, single_branch=single_branch, upstream_refs=upstream)


def _owned_patterns_by_wp(planning_dir: Path) -> dict[str, tuple[str, ...]]:
    """Each work package's normalized ``owned_files`` patterns (``tasks/WP*.md``), keyed by file name.

    Raises:
        PinWindowUnreadable: a work package task file cannot be read, so its ownership is unknown.
    """
    from specify_cli.frontmatter import FrontmatterError
    from specify_cli.ownership.matching import owned_patterns
    from specify_cli.status.wp_metadata import read_authored_wp_frontmatter

    by_wp: dict[str, tuple[str, ...]] = {}
    for wp_file in sorted((planning_dir / "tasks").glob("WP*.md")):
        try:
            metadata, _body = read_authored_wp_frontmatter(wp_file)
        except (FrontmatterError, ValueError, OSError) as exc:  # ValueError covers pydantic's ValidationError
            raise PinWindowUnreadable(f"the work package task file {wp_file} could not be read ({type(exc).__name__})") from exc
        by_wp[wp_file.name] = tuple(owned_patterns(metadata.owned_files))
    return by_wp


def window_keeps_owned_work(repo_root: Path, mission_slug: str, planning_dir: Path, *, recorded: str | None, candidate: str, tip: str) -> bool:
    """False when *candidate*..*tip* loses some work package's owned-file change *recorded*..*tip* holds (#7793).

    Judged per work package, as the gates judge it: every work package with an owned change in the
    recorded window must keep one in the candidate window. True when nothing is recorded or no
    such work package exists (nothing committed yet can be lost).

    Raises:
        PinWindowUnreadable: the ownership or either window cannot be read (the caller fails closed).
    """
    from specify_cli.consolidation import wp_evidence
    from specify_cli.consolidation.git_probes import GitProbeError

    if recorded is None or recorded == candidate:
        return True
    by_wp = {wp: patterns for wp, patterns in _owned_patterns_by_wp(planning_dir).items() if patterns}
    if not by_wp:
        return True
    try:
        before = wp_evidence.evidence_paths(repo_root, (recorded, tip), mission_slug)
        at_risk = [patterns for patterns in by_wp.values() if wp_evidence.has_owned_change(before, patterns)]
        if not at_risk:
            return True
        after = wp_evidence.evidence_paths(repo_root, (candidate, tip), mission_slug)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the evidence window could not be read: {exc}") from exc
    return all(wp_evidence.has_owned_change(after, patterns) for patterns in at_risk)


@dataclass(frozen=True)
class _OrphanFollow:
    """The re-pin target for an orphaned pin, or the refusal code and reason when there is none."""

    sha: str | None
    error_code: str | None = None
    reason: str = ""


def follow_orphaned_pin(repo_root: Path, recorded: str, tip: str, *, upstream_refs: tuple[str, ...] = ()) -> _OrphanFollow:
    """The rebased copy of the orphaned *recorded* pin on *tip*'s history, by patch-id (#7793).

    A copy reachable from one of *upstream_refs* is the upstream's, never the Mission's (B2).

    Raises:
        PinWindowUnreadable: a git probe failed (never read as "no match").
    """
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes.planning_base import follow_pin_by_patch_id

    try:
        follow = follow_pin_by_patch_id(repo_root, recorded, tip, upstream_refs=upstream_refs)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the patch-id of the recorded planning commit could not be followed: {exc}") from exc
    if follow.sha is not None:
        return _OrphanFollow(sha=follow.sha)
    if follow.miss == "ambiguous":
        return _OrphanFollow(sha=None, error_code=PATCH_ID_AMBIGUOUS, reason=f"its change is on {len(follow.candidates)} commits ({', '.join(follow.candidates)})")
    if follow.miss == "upstream_only":
        return _OrphanFollow(
            sha=None,
            error_code=NO_PATCH_ID_MATCH,
            reason=(
                f"its change is only on the upstream ({', '.join(upstream_refs)}): the rebase dropped the Mission's copy as "
                "already applied, and pinning the upstream copy would count the upstream's later commits as this Mission's work"
            ),
        )
    if follow.miss == "no_patch_id":
        return _OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="it has an empty diff, so there is no change to follow")
    return _OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="no commit on the branch carries its change (the rebase dropped or rewrote it)")
