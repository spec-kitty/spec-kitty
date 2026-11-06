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

import os
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination.workspace import lane_status_exclusion_patterns
from specify_cli.core.git_ops import exclude_from_git_index
from specify_cli.lanes.branch_naming import code_lane_branch_name, coord_mission_dir_name, is_lane_branch, resolve_mid8
from specify_cli.mission_metadata import load_meta

__all__ = [
    "LaneCheckoutError",
    "LaneCheckoutRequest",
    "LaneCheckoutRoute",
    "MissionCodeLane",
    "RegisteredCheckout",
    "exclude_lane_status_files",
    "is_mission_status_file",
    "lane_checkout_containing",
    "lane_mission_dir_name",
    "lane_mission_dir_name_from_meta",
    "mission_code_lanes",
    "open_lane_checkout",
    "read_registered_checkouts",
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


# ---------------------------------------------------------------------------
# Registry classification of lane checkouts (Mission WP10, FR-041/FR-044/FR-045)
# ---------------------------------------------------------------------------

#: The Mission status files a lane checkout never shows and a lane never changes.
_MISSION_STATUS_FILE_NAMES = frozenset({"status.events.jsonl", "status.json"})


def is_mission_status_file(relative_path: str) -> bool:
    """True for ``kitty-specs/<dir>/status.events.jsonl`` or ``.../status.json`` (any Mission).

    Judged on the repository-relative path, with either separator (NFR-008).
    """
    parts = PurePosixPath(relative_path.replace("\\", "/")).parts
    return len(parts) == 3 and parts[0] == "kitty-specs" and parts[2] in _MISSION_STATUS_FILE_NAMES


@dataclass(frozen=True)
class RegisteredCheckout:
    """A checkout the git worktree registry lists, with the branch it has checked out (``None`` when detached)."""

    path: Path
    branch: str | None
    is_main: bool

    @property
    def is_lane(self) -> bool:
        """A linked checkout on a lane branch: the registry, not the path shape, decides."""
        return not self.is_main and self.branch is not None and is_lane_branch(self.branch)


def read_registered_checkouts(repo_root: Path) -> tuple[RegisteredCheckout, ...]:
    """Every checkout ``git worktree list --porcelain`` registers, main checkout first.

    Raises:
        WorktreeRegistryUnavailable: git cannot read the registry (fail closed).
    """
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise WorktreeRegistryUnavailable(repo_root=repo_root, detail=str(exc)) from exc
    if result.returncode != 0:
        raise WorktreeRegistryUnavailable(repo_root=repo_root, detail=(result.stderr or result.stdout).strip() or f"exit {result.returncode}")
    return tuple(_parse_porcelain(result.stdout))


def _parse_porcelain(porcelain: str) -> Iterator[RegisteredCheckout]:
    for index, block in enumerate(chunk for chunk in porcelain.split("\n\n") if chunk.strip()):
        path: Path | None = None
        branch: str | None = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = Path(line[len("worktree ") :].strip()).resolve(strict=False)
            elif line.startswith("branch refs/heads/"):
                branch = line[len("branch refs/heads/") :].strip()
        if path is not None:
            yield RegisteredCheckout(path=path, branch=branch, is_main=index == 0)


def _normcase(path: Path) -> str:
    return os.path.normcase(str(path))


def _within(path: Path, root: Path) -> bool:
    target, anchor = _normcase(path), _normcase(root)
    return target == anchor or target.startswith(anchor.rstrip(os.sep) + os.sep)


def lane_checkout_containing(path: Path) -> RegisteredCheckout | None:
    """The registered lane checkout *path* lies in, or ``None``.

    The innermost registered checkout enclosing *path* decides (a lane checkout
    nested under the repository root checkout's ``.worktrees/`` wins over the
    root). A path outside every git repository is in no lane checkout.

    Raises:
        WorktreeRegistryUnavailable: *path* is in a git repository whose
            registry cannot be read (fail closed, never path shape).
    """
    probe = _nearest_existing(path.resolve(strict=False))
    if probe is None or not _inside_git_repository(probe):
        return None
    resolved = path.resolve(strict=False)
    enclosing = [checkout for checkout in read_registered_checkouts(probe) if _within(resolved, checkout.path)]
    if not enclosing:
        return None
    innermost = max(enclosing, key=lambda checkout: len(checkout.path.parts))
    return innermost if innermost.is_lane else None


def _nearest_existing(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.is_dir():
            return candidate
    return None


def _inside_git_repository(directory: Path) -> bool:
    probe = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


@dataclass(frozen=True)
class MissionCodeLane:
    """One code lane of one Mission, as its ``lanes.json`` and ``meta.json`` declare it."""

    mission: str
    """The Mission's directory name under the repository root checkout's ``kitty-specs/``."""
    mission_dir_name: str
    """The Mission's directory name inside a lane tree (:func:`lane_mission_dir_name_from_meta`)."""
    lane_id: str
    branch: str
    coordination_branch: str | None
    mission_branch: str | None
    target_branch: str | None

    @property
    def status_paths(self) -> tuple[str, str]:
        """The repository-relative status files of this Mission inside a lane tree."""
        return (f"kitty-specs/{self.mission_dir_name}/status.events.jsonl", f"kitty-specs/{self.mission_dir_name}/status.json")


def mission_code_lanes(repo_root: Path) -> tuple[MissionCodeLane, ...]:
    """Every code lane of every Mission with a readable ``lanes.json`` under ``kitty-specs/``.

    A Mission whose manifest or ``meta.json`` cannot be read is skipped: it has
    no lanes this enumeration can name.
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    specs = repo_root / "kitty-specs"
    if not specs.is_dir():
        return ()
    found: list[MissionCodeLane] = []
    for mission_dir in sorted(child for child in specs.iterdir() if child.is_dir()):
        try:
            manifest = read_lanes_json(mission_dir)
        except (CorruptLanesError, OSError, ValueError):
            continue
        if manifest is None:
            continue
        meta = load_meta(mission_dir, on_malformed="none") or {}
        dir_name = lane_mission_dir_name_from_meta(manifest.mission_slug, meta)
        coordination = meta.get("coordination_branch")
        for lane in manifest.lanes:
            if lane.lane_id == PLANNING_LANE_ID:
                continue
            found.append(
                MissionCodeLane(
                    mission=mission_dir.name,
                    mission_dir_name=dir_name,
                    lane_id=lane.lane_id,
                    branch=code_lane_branch_name(manifest.mission_slug, lane.lane_id),
                    coordination_branch=coordination if isinstance(coordination, str) and coordination else None,
                    mission_branch=manifest.mission_branch or None,
                    target_branch=manifest.target_branch or None,
                )
            )
    return tuple(found)
