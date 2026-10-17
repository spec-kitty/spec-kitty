"""Protected single_branch landing helpers (WP08 / #5100 IC-05, T037, research R-9).

Owned by WP08 so the sibling-owned ``consolidation/*`` modules only call
into it with a few lines each (C-005).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    error = _checkout_target(repo, mission_branch, target_branch)
    if error is not None:
        raise RuntimeError(
            f"Landed {mission_branch!r} onto {target_branch!r}, but could not switch the write "
            f"checkout back to {target_branch!r}: {error}. Resolve the checkout "
            "(it may be dirty), then re-run 'spec-kitty consolidate --resume'."
        )


def leave_mission_branch_for_discard(repo: Path, mission_branch: str, target_branch: str) -> None:
    """Move the write checkout off *mission_branch* before a discard deletes it.

    ``git branch -D`` refuses a checked-out branch, so ``mission close --discard`` of
    a protected single_branch mission must first return the checkout to the target.
    A checkout that git refuses to switch (typically a dirty tree) raises before
    anything destructive has run.
    """
    error = _checkout_target(repo, mission_branch, target_branch)
    if error is not None:
        raise RuntimeError(
            f"cannot discard: the write checkout is on {mission_branch!r} and could not be switched to "
            f"{target_branch!r} so the branch can be deleted: {error}. Commit or stash the changes you "
            f"want to keep, or check out {target_branch!r} yourself, then retry."
        )


def _checkout_target(repo: Path, mission_branch: str, target_branch: str) -> str | None:
    """Check out *target_branch*; ``None`` on success/no-op, else git's stderr."""
    if mission_branch == target_branch:
        return None
    if _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == target_branch:
        return None
    result = _git(repo, "checkout", target_branch)
    return None if result.returncode == 0 else result.stderr.strip()


def worktree_lanes(manifest: LanesManifest) -> list[ExecutionLane]:
    """Lanes that own a ``.worktrees/`` checkout (never the repo-root lane, which has none)."""
    from specify_cli.lanes.compute import is_repo_root_lane

    return [lane for lane in manifest.lanes if not is_repo_root_lane(lane)]


def minted_mission_branch(repo: Path, mission_slug: str, target_branch: str) -> str | None:
    """The create-time ``mission_branch`` of a protected single_branch mission, else ``None``.

    Non-``None`` only when the STORED topology is single_branch AND ``meta.json``
    carries a ``mission_branch`` distinct from the target.

    Never the manifest's ``mission_branch != target_branch`` (true for every
    legacy manifest) and never a DERIVED topology (unstamped planning-only
    missions derive single_branch): both would land legacy missions.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.mission_metadata import load_meta_or_empty

    meta = load_meta_or_empty(placement_seam(repo, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA))
    return minted_branch_from_meta(meta, target_branch)


def minted_branch_from_meta(meta: Mapping[str, Any], target_branch: str) -> str | None:
    """:func:`minted_mission_branch` over an already-loaded ``meta.json`` mapping."""
    from mission_runtime import is_single_branch
    from specify_cli.migration.backfill_topology import stored_topology

    minted = meta.get("mission_branch")
    if not (isinstance(minted, str) and minted and minted != target_branch):
        return None
    return minted if is_single_branch(stored_topology(meta)) else None


def _is_protected_single_branch(repo: Path, mission_slug: str, target_branch: str) -> bool:
    """True when :func:`minted_mission_branch` names a branch (STORED topology, never derived)."""
    return minted_mission_branch(repo, mission_slug, target_branch) is not None


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
    ``--resume``) it is on the target. From any THIRD branch the mission is only
    reachable through its still-existing ``mission_branch``, so that is the
    branch to name -- ``target_branch`` would send the operator to a checkout
    that does not carry the mission. Every other mission expects the target.
    """
    if not lands_mission_branch(repo, manifest):
        return target_branch
    head = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    mission_branch = str(manifest.mission_branch)
    if head == mission_branch:
        return mission_branch
    if head != target_branch and _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{mission_branch}").returncode == 0:
        return mission_branch
    return target_branch


def branch_holding_path(repo: Path, rel_path: str) -> str | None:
    """The minted ``kitty/*`` branch whose tree carries *rel_path*, else ``None``.

    A protected single_branch mission's files exist only on its minted branch, so a
    consolidate started from any other checkout cannot read them. Locating the
    branch lets the error name it instead of sending the operator to ``finalize-tasks``.
    """
    listing = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/kitty/")
    for branch in sorted(listing.stdout.split()):
        if _git(repo, "cat-file", "-e", f"{branch}:{rel_path}").returncode == 0:
            return branch
    return None


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


def is_single_branch_meta(meta: Mapping[str, Any]) -> bool:
    """True when an already-loaded ``meta.json`` mapping declares a STORED single_branch topology.

    Slug-free (takes the loaded mapping, not a slug): a caller that holds the mission directory
    reads meta from it directly and avoids feeding a slug into path-segment validation on a path
    the #5939 axis may not apply to (the orchestrator planning-only no-op, where the slug can be
    a test mock).
    """
    from mission_runtime import is_single_branch

    from specify_cli.migration.backfill_topology import stored_topology

    return is_single_branch(stored_topology(meta))


def is_single_branch_mission(repo: Path, manifest: LanesManifest) -> bool:
    """True when the mission's STORED topology is single_branch.

    Distinct from :func:`single_branch_evidence_window`, which also returns ``None`` when the
    mission IS single_branch but its evidence window is uncomputable (a legacy ``lanes.json``
    with no ``planning_commit_sha``). The #5939 backstop uses this to fail CLOSED on that
    uncomputable case rather than silently no-opping it.

    Scope of the #5939 fail-closed guarantee (#6324 review nit): the backstop fails CLOSED on
    an uncomputable *evidence window*, not on *topology detection*. A mission whose ``meta.json``
    is missing or malformed reads here as "not single_branch" (``load_meta_or_empty`` yields an
    empty mapping), so the axis no-ops rather than refusing -- but that case never reaches the
    axis unexploited: ``consolidate``'s earlier selector/identity/retention preflights hard-fail
    on a corrupt or missing ``meta.json``, and an unmigrated single_branch mission with code
    lanes trips ``SINGLE_BRANCH_CODE_LANES_UNMIGRATED`` first. Topology is read STORED (never
    derived), so this is deliberate: the axis does not re-derive topology from in-flight
    ``lanes.json`` signals.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    from specify_cli.mission_metadata import load_meta_or_empty

    meta = load_meta_or_empty(placement_seam(repo, manifest.mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA))
    return is_single_branch_meta(meta)


def single_branch_evidence_window(repo: Path, manifest: LanesManifest, *, assume_single_branch: bool = False) -> tuple[str, str] | None:
    """``(planning_commit, mission_branch)`` implementation-evidence window for ANY single_branch mission, else ``None``.

    Unlike :func:`authorship_window` (the PROTECTED minted-branch case only, whose base is
    ``merge-base(target, mission_branch)``), this covers EVERY single_branch mission -- a
    commit-to-target one whose ``mission_branch`` IS the target included -- by windowing the
    recorded finalize-tasks planning-artifact commit (``lanes.json planning_commit_sha``) to
    the mission-branch tip. Implementation commits land after planning, so a diff of
    ``planning_commit..mission_branch`` is exactly the mission's authored change set (#5939).

    Gated on the STORED topology (never a derived one), so a coord/lanes mission is never
    treated as single_branch here. Returns ``None`` when the mission is not single_branch, or
    when no planning commit / mission branch was recorded (a pre-``planning_commit_sha`` legacy
    manifest cannot be windowed). A caller that must distinguish "not single_branch" from
    "single_branch but uncomputable" (the #5939 fail-closed backstop) pairs this with
    :func:`is_single_branch_mission`.

    ``assume_single_branch`` (#6324 review nit): a caller that has *already* established the
    STORED topology via :func:`is_single_branch_mission` passes ``True`` to skip the redundant
    ``meta.json`` read here (the two reads otherwise duplicate the same ``load_meta_or_empty``).
    The topology gate is unchanged for the default path; ``True`` is only ever passed right
    after a positive :func:`is_single_branch_mission` on the same ``(repo, manifest)``.
    """
    if not assume_single_branch and not is_single_branch_mission(repo, manifest):
        return None
    base = manifest.planning_commit_sha
    tip = manifest.mission_branch
    if not base or not tip:
        return None
    return (base, tip)
