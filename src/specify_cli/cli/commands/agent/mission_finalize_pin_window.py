"""``finalize-tasks``: the single_branch pin's branch line and evidence-window guard (#7793, #7297).

A ``single_branch`` Mission's implementation evidence window is ``planning_commit..mission_branch``
(:func:`specify_cli.lanes.single_branch_landing.single_branch_evidence_window`). This module keeps
finalize's pin decisions consistent with that window (ADR ``2026-10-04-5`` Amendment 2026-11-22):

* :func:`resolve_pin_line` -- the branch the pin is captured from, refreshed against and derived on
  (``lanes.planning_base.pin_branch_line`` over the stored ``meta.json``).
* :func:`window_keeps_owned_work` -- a candidate pin is acceptable only when its window still holds
  a change to some work package's ``owned_files`` whenever the recorded window held one. It reads
  the same evidence the ``move-task`` gate and ``consolidate`` read (``consolidation.wp_evidence``),
  so it cannot disagree with them.
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
    "OrphanFollow",
    "PATCH_ID_AMBIGUOUS",
    "WOULD_EMPTY_WINDOW",
    "PinLine",
    "PinWindowUnreadable",
    "follow_orphaned_pin",
    "mission_owned_patterns",
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
class PinLine:
    """Where this Mission's pin lives: the branch, and whether the single_branch rules apply."""

    branch: str
    single_branch: bool


def resolve_pin_line(repo_root: Path, mission_slug: str, target_branch: str, *, owned: OwnedCheckout | None = None) -> PinLine:
    """The pin branch line of *mission_slug*, read from its stored ``meta.json`` (#7297 item 2)."""
    from mission_runtime import is_single_branch

    from specify_cli.lanes.planning_base import pin_branch_line
    from specify_cli.lanes.single_branch_landing import stored_mission_meta
    from specify_cli.migration.backfill_topology import stored_topology

    meta: dict[str, Any] = stored_mission_meta(repo_root, mission_slug, owned=owned)
    return PinLine(branch=pin_branch_line(meta, target_branch), single_branch=is_single_branch(stored_topology(meta)))


def mission_owned_patterns(planning_dir: Path) -> tuple[str, ...]:
    """Every work package's normalized ``owned_files`` patterns (``tasks/WP*.md``), in file order.

    Raises:
        PinWindowUnreadable: a work package task file cannot be read, so its ownership is unknown.
    """
    from specify_cli.frontmatter import FrontmatterError
    from specify_cli.ownership.matching import owned_patterns
    from specify_cli.status.wp_metadata import read_authored_wp_frontmatter

    patterns: list[str] = []
    for wp_file in sorted((planning_dir / "tasks").glob("WP*.md")):
        try:
            metadata, _body = read_authored_wp_frontmatter(wp_file)
        except (FrontmatterError, ValueError, OSError) as exc:  # ValueError covers pydantic's ValidationError
            raise PinWindowUnreadable(f"the work package task file {wp_file} could not be read ({type(exc).__name__})") from exc
        patterns.extend(owned_patterns(metadata.owned_files))
    return tuple(patterns)


def window_keeps_owned_work(repo_root: Path, mission_slug: str, planning_dir: Path, *, recorded: str | None, candidate: str, tip: str) -> bool:
    """False when *candidate*..*tip* loses the owned-file change *recorded*..*tip* holds (#7793).

    True when nothing is recorded, no work package owns a file, or the recorded window holds no
    owned change (nothing committed yet can be lost).

    Raises:
        PinWindowUnreadable: the ownership or either window cannot be read (the caller fails closed).
    """
    from specify_cli.consolidation import wp_evidence
    from specify_cli.consolidation.git_probes import GitProbeError

    if recorded is None or recorded == candidate:
        return True
    patterns = mission_owned_patterns(planning_dir)
    if not patterns:
        return True
    try:
        if not wp_evidence.has_owned_change(wp_evidence.evidence_paths(repo_root, (recorded, tip), mission_slug), patterns):
            return True
        kept: bool = wp_evidence.has_owned_change(wp_evidence.evidence_paths(repo_root, (candidate, tip), mission_slug), patterns)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the evidence window could not be read: {exc}") from exc
    return kept


@dataclass(frozen=True)
class OrphanFollow:
    """The re-pin target for an orphaned pin, or the refusal code and reason when there is none."""

    sha: str | None
    error_code: str | None = None
    reason: str = ""


def follow_orphaned_pin(repo_root: Path, recorded: str, tip: str) -> OrphanFollow:
    """The rebased copy of the orphaned *recorded* pin on *tip*'s history, by patch-id (#7793).

    Raises:
        PinWindowUnreadable: a git probe failed (never read as "no match").
    """
    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes.planning_base import follow_pin_by_patch_id

    try:
        follow = follow_pin_by_patch_id(repo_root, recorded, tip)
    except GitProbeError as exc:
        raise PinWindowUnreadable(f"the patch-id of the recorded planning commit could not be followed: {exc}") from exc
    if follow.sha is not None:
        return OrphanFollow(sha=follow.sha)
    if follow.miss == "ambiguous":
        return OrphanFollow(sha=None, error_code=PATCH_ID_AMBIGUOUS, reason=f"its change is on {len(follow.candidates)} commits ({', '.join(follow.candidates)})")
    if follow.miss == "no_patch_id":
        return OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="it has an empty diff, so there is no change to follow")
    return OrphanFollow(sha=None, error_code=NO_PATCH_ID_MATCH, reason="no commit on the branch carries its change (the rebase dropped or rewrote it)")
