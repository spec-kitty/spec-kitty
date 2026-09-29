"""Protected single_branch landing helpers (WP08 / #5100 IC-05, T037, research R-9).

Owned by WP08 so the sibling-owned ``consolidation/*`` modules only call
into it with a few lines each (C-005).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def switch_checkout_to_target(repo: Path, mission_branch: str, target_branch: str) -> None:
    """Return the write checkout to *target_branch* after *mission_branch* landed.

    No-op when the two are equal (unprotected / ``commit_to_target``) or the
    checkout is already on the target. Must run before ``git branch -D`` of
    the mission branch (git refuses to delete a checked-out branch) and before
    the post-merge refresh (which requires the checkout on the target).
    """
    if mission_branch == target_branch:
        return
    if _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == target_branch:
        return
    result = _git(repo, "checkout", target_branch)
    if result.returncode != 0:
        raise RuntimeError(
            f"Landed {mission_branch!r} onto {target_branch!r}, but could not switch the write "
            f"checkout back to {target_branch!r}: {result.stderr.strip()}. Resolve the checkout "
            "(it may be dirty), then re-run 'spec-kitty consolidate --resume'."
        )


def worktree_lanes(manifest: LanesManifest) -> list[ExecutionLane]:
    """Lanes that own a ``.worktrees/`` checkout (never the repo-root lane, which has none)."""
    from specify_cli.lanes.compute import is_repo_root_lane

    return [lane for lane in manifest.lanes if not is_repo_root_lane(lane)]


def _is_protected_single_branch(repo: Path, mission_slug: str, target_branch: str) -> bool:
    """STORED topology is single_branch AND ``meta.json`` carries the create-time ``mission_branch``.

    Never the manifest's ``mission_branch != target_branch`` (true for every
    legacy manifest) and never a DERIVED topology (unstamped planning-only
    missions derive single_branch): both would land legacy missions.
    """
    from specify_cli.migration.backfill_topology import stored_topology
    from specify_cli.mission_metadata import load_meta_or_empty
    from mission_runtime import MissionTopology

    meta = load_meta_or_empty(repo / "kitty-specs" / mission_slug)
    minted = meta.get("mission_branch")
    if not (isinstance(minted, str) and minted and minted != target_branch):
        return False
    return bool(stored_topology(meta) == MissionTopology.SINGLE_BRANCH)


def lands_mission_branch(repo: Path, manifest: LanesManifest) -> bool:
    """True when consolidate must land ``mission_branch`` onto the target.

    A single_branch manifest has ONE ``lane-planning`` lane, so the lane-based
    ``is_planning_artifact_only`` reads True even when the mission holds code on a
    protected mission branch; that must not short-circuit the landing phase nor
    demand the checkout already be on the target.
    """
    return _is_protected_single_branch(repo, manifest.mission_slug, manifest.target_branch)


def expected_consolidate_checkout(repo: Path, manifest: LanesManifest, target_branch: str) -> str:
    """Branch the write checkout must be on when consolidate starts.

    A protected single_branch mission's checkout sits on its ``mission_branch``
    (that is where every commit landed); once landed and switched back (or on a
    ``--resume``) it is on the target. Every other mission expects the target.
    """
    if lands_mission_branch(repo, manifest) and _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == manifest.mission_branch:
        return str(manifest.mission_branch)
    return target_branch


def authorship_window(repo: Path, mission_slug: str, mission_branch: str, target_branch: str) -> tuple[str, str] | None:
    """``(fork_point, mission_branch)`` for a protected single_branch repo-root lane, else ``None``.

    Gated on the STORED topology (a coord mission's ``mission_branch`` is its
    coordination branch and must keep the ordinary lane resolution). The base is
    ``merge-base(target, mission_branch)``: the lane's authored first-parent
    history is ``base..mission_branch`` (R-9). Unresolvable fork point -> ``None``.
    """
    if mission_branch == target_branch or not _is_protected_single_branch(repo, mission_slug, target_branch):
        return None
    result = _git(repo, "merge-base", target_branch, mission_branch)
    base = result.stdout.strip()
    return (base, mission_branch) if result.returncode == 0 and base else None
