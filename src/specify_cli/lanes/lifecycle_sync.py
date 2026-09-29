"""Lane lifecycle sync points for coordination-branch missions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from specify_cli.lanes.auto_rebase import AutoRebaseReport, attempt_auto_rebase
from specify_cli.lanes.compute import is_repo_root_lane
from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
from specify_cli.lanes.worktree_allocator import predict_lane_worktree
from mission_runtime import MissionArtifactKind, placement_seam

LANE_AUTO_REBASE_FAILED = "LANE_AUTO_REBASE_FAILED"
WORKTREES_DIRNAME = ".worktrees"


@dataclass
class LaneAutoRebaseSyncError(RuntimeError):
    """Structured failure for a lane sync-point auto-rebase refusal."""

    lane_id: str
    lane_branch: str
    lane_worktree_path: Path
    coordination_branch: str
    coordination_head: str | None
    halt_reason: str

    error_code: ClassVar[str] = LANE_AUTO_REBASE_FAILED

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    @property
    def message(self) -> str:
        return (
            f"{self.error_code}: auto-rebase refused for {self.lane_id}: "
            f"{self.halt_reason}"
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "error_code": self.error_code,
            "lane_id": self.lane_id,
            "lane_branch": self.lane_branch,
            "lane_worktree_path": str(self.lane_worktree_path),
            "coordination_branch": self.coordination_branch,
            "coordination_head": self.coordination_head,
            "halt_reason": self.halt_reason,
        }


def _git_stdout(repo_root: Path, *args: str) -> str | None:
    # coord-commit-integrity WP04/T015 (campsite): tolerate a non-existent
    # ``cwd``. A caller may pass a repo path that does not exist yet (a coord
    # commit whose lane was never materialized). ``subprocess.run(cwd=<absent
    # dir>)`` raises a raw ``FileNotFoundError`` ([Errno 2]) that crashed the
    # auto-rebase sync instead of degrading to an unresolved read.
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def sync_lane_after_coordination_commit(
    *,
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    coordination_branch: str,
) -> AutoRebaseReport | None:
    """Merge the coordination branch into a WP lane at lifecycle sync points.

    Returns ``None`` when the WP is not lane-owned or no lane worktree exists.
    Raises :class:`LaneAutoRebaseSyncError` on a refused auto-rebase. The
    underlying auto-rebase path aborts failed git merges before this exception
    is raised, so lane worktree state remains at its pre-sync tip.
    """
    # FR-002 (#2185): ``lanes.json`` is a LANE_STATE (PRIMARY-partition) artifact
    # that lives ONLY on the PRIMARY checkout post-#2106. The auto-rebase callers
    # thread the coord-aware STATUS feature dir (the ``-coord`` husk for a
    # coord-topology mission), which lacks ``lanes.json`` — so trusting that dir
    # here makes ``read_lanes_json`` return ``None`` and SILENTLY skips the
    # post-coordination lane auto-rebase. Self-resolve the read by its real kind
    # so it lands on PRIMARY regardless of topology; the callers' STATUS legs (the
    # append-only event log) stay coord-aware untouched (C-001).
    lanes_read_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.LANE_STATE
    )
    try:
        lanes_manifest = read_lanes_json(lanes_read_dir)
    except CorruptLanesError as exc:
        raise LaneAutoRebaseSyncError(
            lane_id="unknown",
            lane_branch="unknown",
            # A non-lane-shaped sentinel path (the ``.worktrees`` dir itself,
            # not a fabricated ``<slug>-unknown`` worktree name): the lane is
            # unresolvable at this point (the manifest itself is corrupt), so
            # there is no real lane worktree to point at. The previous
            # ``f"{mission_slug}-unknown"`` guess was still a hand-rolled
            # worktree-dir compose outside the naming seam even though it was
            # never opened (WP11 gate-pinned site).
            lane_worktree_path=repo_root / WORKTREES_DIRNAME,
            coordination_branch=coordination_branch,
            coordination_head=_git_stdout(repo_root, "rev-parse", coordination_branch),
            halt_reason=str(exc),
        ) from exc

    if lanes_manifest is None:
        return None

    lane = lanes_manifest.lane_for_wp(wp_id)
    if lane is None or is_repo_root_lane(lane):
        return None

    # Placement (path + branch) comes from the single predict seam (PD-1):
    # the write authority (``allocate_lane_worktree``) and this read-only
    # sync point must never diverge on this decision. No candidate probing,
    # no HEAD fallback (C-004) — ``lanes_manifest.mission_slug`` (PD-2) is
    # the same value as ``mission_slug`` for every real caller.
    worktree_path, lane_branch = predict_lane_worktree(
        repo_root, lanes_manifest.mission_slug, lane.lane_id
    )
    coordination_head = _git_stdout(repo_root, "rev-parse", coordination_branch)
    if not (worktree_path / ".git").exists():
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        add_result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), lane_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if add_result.returncode != 0:
            raise LaneAutoRebaseSyncError(
                lane_id=lane.lane_id,
                lane_branch=lane_branch,
                lane_worktree_path=worktree_path,
                coordination_branch=coordination_branch,
                coordination_head=coordination_head,
                halt_reason=(
                    "could not create lane worktree for auto-rebase: "
                    f"{(add_result.stderr or add_result.stdout).strip()}"
                ),
            )

    report = attempt_auto_rebase(
        lane=lane,
        branch=lane_branch,
        mission_branch=coordination_branch,
        repo_root=repo_root,
        worktree_path=worktree_path,
    )
    if report.succeeded:
        return report

    raise LaneAutoRebaseSyncError(
        lane_id=lane.lane_id,
        lane_branch=lane_branch,
        lane_worktree_path=worktree_path,
        coordination_branch=coordination_branch,
        coordination_head=coordination_head,
        halt_reason=report.halt_reason or "auto-rebase failed",
    )


__all__ = [
    "LANE_AUTO_REBASE_FAILED",
    "LaneAutoRebaseSyncError",
    "sync_lane_after_coordination_commit",
]
