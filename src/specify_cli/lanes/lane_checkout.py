"""The one lane-checkout helper: every lane ``git worktree add`` goes through here.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP09 (FR-021, FR-022, FR-040,
C-013). ADR 2026-07-29-1 Amendment 2026-11-06 (restated ruling 3: a lane
checkout never shows the Mission's status files; the fork-time blob stays in
lane history) and ADR 2026-04-03-1 Amendment 2026-11-06 (this helper is the
future lease acquire; no lease state is built here, C-007).

:func:`open_lane_checkout` is the only place in ``src/`` that creates a lane
checkout. On every route it:

1. refuses a detached checkout (the ``post-commit`` lane-tip hook only fires on
   an attached branch);
2. runs ``git worktree add`` on that attached branch (``-b`` when the branch
   is created here);
3. installs the lane-tip recorder hooks through the existing installer (which
   keeps its skip-with-warning rules for a global, ``/dev/null`` or in-tree
   ``core.hooksPath``);
4. adds ``.spec-kitty/`` to the common-dir local exclude;
5. registers the sparse exclusion of the Mission's ``status.events.jsonl`` and
   ``status.json`` and reapplies it, so the files leave the disk. git keeps a
   locally modified status file on disk (with a warning) rather than discard
   it, so no local status row is ever lost.

The architectural gate ``tests/architectural/test_lane_checkout_single_seam.py``
fails on any lane ``git worktree add`` outside this module.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination.workspace import lane_status_exclusion_patterns
from specify_cli.core.git_ops import exclude_from_git_index
from specify_cli.lanes.branch_naming import coord_mission_dir_name, resolve_mid8
from specify_cli.mission_metadata import load_meta

__all__ = [
    "LaneCheckoutError",
    "LaneCheckoutRequest",
    "LaneCheckoutRoute",
    "lane_mission_dir_name",
    "lane_mission_dir_name_from_meta",
    "open_lane_checkout",
    "resolve_lane_mission_dir_name",
]

#: The spec-kitty runtime-state directory a lane checkout must never show as untracked (#5434).
_SPEC_KITTY_STATE_EXCLUDE = ".spec-kitty/"


class LaneCheckoutRoute(StrEnum):
    """Every route that creates a lane checkout (data-model §4)."""

    ALLOCATION_FRESH = "allocation_fresh"
    """``allocate_lane_worktree`` FRESH_COORD: a new lane cut from the coordination branch."""
    ALLOCATION_LEGACY = "allocation_legacy"
    """``allocate_lane_worktree`` FRESH_LEGACY: a new lane cut from the Mission branch."""
    RECOVERY = "recovery"
    """``allocate_lane_worktree`` CRASH_RECOVERY: the branch survived, the checkout was lost."""
    LIFECYCLE_SYNC = "lifecycle_sync"
    """``lifecycle_sync`` recreating a missing checkout before the auto-rebase."""
    REVIEW = "review"
    """``agent action review`` creating the review checkout."""
    RECREATE = "recreate"
    """``implement --recover`` recreating a lost checkout (``lanes/recovery.py``)."""


_FAILURE_PREFIX: dict[LaneCheckoutRoute, str] = {
    LaneCheckoutRoute.ALLOCATION_FRESH: "Failed to create lane worktree at",
    LaneCheckoutRoute.ALLOCATION_LEGACY: "Failed to create lane worktree at",
    LaneCheckoutRoute.RECOVERY: "Failed to recover worktree at",
    LaneCheckoutRoute.LIFECYCLE_SYNC: "Failed to recreate lane worktree at",
    LaneCheckoutRoute.REVIEW: "Failed to create review worktree at",
    LaneCheckoutRoute.RECREATE: "Failed to recover worktree at",
}


class LaneCheckoutError(RuntimeError):
    """A lane checkout could not be created; nothing was registered with git."""


@dataclass(frozen=True)
class LaneCheckoutRequest:
    """What one lane checkout needs (data-model §4 ``LaneCheckoutRequest``).

    ``worktree_path`` is the placement the caller already resolved (the
    naming seam or the resolved workspace); the helper never re-derives it.
    ``create_branch_from`` set means ``branch`` is created here from that
    ref (``git worktree add -b``); ``None`` means ``branch`` must already be
    a local branch, attached as is.
    """

    repo_root: Path
    mission_slug: str
    mission_dir_name: str
    lane_id: str | None
    branch: str
    worktree_path: Path
    create_branch_from: str | None
    route: LaneCheckoutRoute


def lane_mission_dir_name(mission_slug: str, *, coordination_mid8: str | None) -> str:
    """The Mission's directory name under ``kitty-specs/`` as a lane tree carries it.

    A coordination-topology lane is cut from the coordination branch, whose
    Mission dir is ``<slug>-<mid8>`` (no double suffix); pass its mid8 as
    ``coordination_mid8``. Every other lane carries the Mission dir verbatim
    as ``mission_slug``.
    """
    if coordination_mid8:
        return coord_mission_dir_name(mission_slug, mid8=coordination_mid8)
    return mission_slug


def lane_mission_dir_name_from_meta(mission_slug: str, meta: Mapping[str, object]) -> str:
    """:func:`lane_mission_dir_name` for one Mission's ``meta.json`` record.

    The single derivation every reader of the status exclusion shares: the
    helper that writes it (through :func:`resolve_lane_mission_dir_name`) and
    the sparse-checkout policy that recognizes it as Mission-managed
    (``git/sparse_checkout.py``). A ``coordination_branch`` makes the
    directory ``<slug>-<mid8>``; every other topology carries ``mission_slug``.
    """
    coordination_branch = meta.get("coordination_branch")
    if not (isinstance(coordination_branch, str) and coordination_branch):
        return lane_mission_dir_name(mission_slug, coordination_mid8=None)
    mission_id = meta.get("mission_id")
    mid8 = resolve_mid8(mission_slug, mission_id=mission_id if isinstance(mission_id, str) else None)
    return lane_mission_dir_name(mission_slug, coordination_mid8=mid8 or None)


def resolve_lane_mission_dir_name(repo_root: Path, mission_slug: str) -> str:
    """Resolve :func:`lane_mission_dir_name` from the Mission's ``meta.json``.

    For routes that hold only a slug (review, recreate, lifecycle sync). The
    coordination branch and ``mission_id`` are read from ``meta.json`` on the
    PRIMARY partition, exactly as the allocator reads them.
    """
    meta_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    return lane_mission_dir_name_from_meta(mission_slug, load_meta(meta_dir, on_malformed="none") or {})


def open_lane_checkout(request: LaneCheckoutRequest) -> Path:
    """Create one lane checkout, attached, with the hook and every exclusion; return its path.

    Raises:
        LaneCheckoutError: the branch would check out detached (nothing is
            created), ``git worktree add`` failed (nothing is registered), or
            the status exclusion could not be applied (the checkout stays
            registered, as git created it, and the error names the git step).
    """
    _refuse_detached(request)
    _add_worktree(request)
    _ensure_lane_tip_hook(request.repo_root)
    exclude_from_git_index(request.repo_root, [_SPEC_KITTY_STATE_EXCLUDE])
    exclude_lane_status_files(request.worktree_path, request.mission_dir_name)
    return request.worktree_path


def exclude_lane_status_files(checkout: Path, mission_dir_name: str) -> None:
    """Register and apply the status-file sparse exclusion in one lane checkout.

    Uses git's own sparse-checkout commands (no shell globbing, NFR-008).
    The configuration is per worktree (clone-local). ``reapply`` leaves a
    locally modified status file on disk with a warning, so a dirty copy's
    rows are never discarded (C-009); a clean one leaves the disk.
    """
    _git(checkout, "sparse-checkout", "init", "--no-cone")
    sparse_file = Path(_git(checkout, "rev-parse", "--git-path", "info/sparse-checkout"))
    if not sparse_file.is_absolute():
        sparse_file = checkout / sparse_file
    sparse_file.parent.mkdir(parents=True, exist_ok=True)
    sparse_file.write_text("\n".join(lane_status_exclusion_patterns(mission_dir_name)) + "\n", encoding="utf-8")
    _git(checkout, "sparse-checkout", "reapply")


def _refuse_detached(request: LaneCheckoutRequest) -> None:
    """An attach route needs an existing LOCAL branch: anything else would check out detached."""
    if not request.branch:
        raise LaneCheckoutError(f"{_failure(request)}: no lane branch was given; a lane checkout is never detached")
    if request.create_branch_from is not None:
        return
    probe = subprocess.run(
        ["git", "-C", str(request.repo_root), "show-ref", "--verify", "--quiet", f"refs/heads/{request.branch}"],
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        raise LaneCheckoutError(f"{_failure(request)}: {request.branch} is not a local branch; a lane checkout is never detached")


def _add_worktree(request: LaneCheckoutRequest) -> None:
    request.worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if request.create_branch_from is None:
        argv = ["git", "worktree", "add", str(request.worktree_path), request.branch]
    else:
        argv = ["git", "worktree", "add", "-b", request.branch, str(request.worktree_path), request.create_branch_from]
    result = subprocess.run(argv, cwd=str(request.repo_root), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LaneCheckoutError(f"{_failure(request)}: {(result.stderr or result.stdout).strip()}")


def _ensure_lane_tip_hook(repo_root: Path) -> None:
    """Install the lane-tip recorder unless it is already the active ``post-commit`` hook.

    The allocator installs the recorder before its destroyed-lane guard, so on
    its routes the recorder is normally active already and this is a cheap
    probe. When the installer has to skip (a global, ``/dev/null`` or in-tree
    ``core.hooksPath``, or a foreign hook) it warns, as it always has (C-010).
    """
    from specify_cli.policy.lane_tip_recorder import install_lane_tip_recorder, lane_tip_recorder_active

    if not lane_tip_recorder_active(repo_root):
        install_lane_tip_recorder(repo_root)


def _failure(request: LaneCheckoutRequest) -> str:
    return f"{_FAILURE_PREFIX[request.route]} {request.worktree_path}"


def _git(cwd: Path, *args: str) -> str:
    """Run one git command in ``cwd``; raise :class:`LaneCheckoutError` on a non-zero exit."""
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LaneCheckoutError(f"git {' '.join(args)} failed in {cwd}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()
