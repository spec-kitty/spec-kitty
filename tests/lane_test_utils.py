"""Helpers for lane-only test fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from specify_cli.lanes.compute import is_planning_lane, lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json


def derive_mission_id(mission_slug: str) -> str:
    """Mint a deterministic, production-shaped 26-char ULID for a test mission.

    Post-083 every mission carries a ULID ``mission_id`` in ``meta.json``; the
    coordination-write seam derives the branch/worktree ``mid8`` from it and
    :func:`specify_cli.coordination.workspace._require_mid8` HARD-FAILS on an
    empty ``mid8`` (#2091, invariant M-1). A pre-3.2.x, meta-less test mission
    therefore trips that guard. Rather than a placeholder, this returns a
    stable, ULID-shaped identity derived from the slug: ``"01"`` + 24 uppercase
    hex chars. Every character is valid Crockford base32 (``0-9A-F`` are a subset
    of the ULID alphabet), so the first 8 chars form a valid ``mid8`` that
    satisfies ``_MID8_RE``. Deterministic per slug → unique, reproducible,
    collision-free across distinct missions.
    """
    return "01" + hashlib.sha1(mission_slug.encode("utf-8")).hexdigest().upper()[:24]


def write_mission_meta(feature_dir: Path, *, mission_type: str = "software-dev") -> Path:
    """Write a modern ``meta.json`` (ULID ``mission_id`` + ``mid8``) if absent.

    Modernizes a test mission to the 3.2.x mission-identity model so the
    coordination-write seam can resolve a non-empty ``mid8`` instead of tripping
    the #2091 empty-``mid8`` guard. No ``coordination_branch`` is written, so the
    mission classifies as a primary/lanes-without-coord surface and status writes
    route to the primary checkout (unchanged pre-#2091 routing). Idempotent: a
    caller that stages its own ``meta.json`` (e.g. a coord-topology fixture with
    an explicit ``mid8``) keeps it — this only fills the gap for the common case.
    """
    meta_path = feature_dir / "meta.json"
    if meta_path.exists():
        return meta_path
    mission_slug = feature_dir.name
    mission_id = derive_mission_id(mission_slug)
    meta_path.write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mission_id[:8],
                "mission_slug": mission_slug,
                "mission_type": mission_type,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return meta_path


def write_single_lane_manifest(
    feature_dir: Path,
    *,
    wp_ids: tuple[str, ...] = ("WP01",),
    lane_id: str = "lane-a",
    target_branch: str = "main",
    mission_id: str | None = None,
    write_scope: tuple[str, ...] = ("src/**",),
    predicted_surfaces: tuple[str, ...] = ("test",),
    depends_on_lanes: tuple[str, ...] = (),
    parallel_group: int = 0,
) -> Path:
    """Persist a minimal valid lanes.json for tests.

    Also stages a modern ``meta.json`` (ULID ``mission_id`` + ``mid8``) when the
    caller has not written one, so the coordination-write seam resolves a
    non-empty ``mid8`` rather than tripping the #2091 guard on a meta-less
    (pre-3.2.x) mission.
    """
    write_mission_meta(feature_dir)
    # #6715: record the planning commit (the repository's current tip, the commit a lane would be
    # cut from) when the fixture repository has one, so the evidence window every landing surface
    # reads is computable — as ``finalize-tasks`` records it on a real Mission.
    head = subprocess.run(
        ["git", "-C", str(feature_dir.parents[1]), "rev-parse", "--verify", "--quiet", "HEAD^{commit}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return write_lanes_json(
        feature_dir,
        LanesManifest(
            planning_commit_sha=head.stdout.strip() or None,
            version=1,
            mission_slug=feature_dir.name,
            mission_id=mission_id or feature_dir.name,
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch=target_branch,
            lanes=[
                ExecutionLane(
                    lane_id=lane_id,
                    wp_ids=wp_ids,
                    write_scope=write_scope,
                    predicted_surfaces=predicted_surfaces,
                    depends_on_lanes=depends_on_lanes,
                    parallel_group=parallel_group,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )


def lane_worktree_path(repo_root: Path, mission_slug: str, lane_id: str = "lane-a") -> Path:
    """Return the lane worktree path for a feature."""
    return repo_root / ".worktrees" / f"{mission_slug}-{lane_id}"


def lane_branch_name(mission_slug: str, lane_id: str = "lane-a") -> str:
    """Return the lane branch name for a feature."""
    return f"kitty/mission-{mission_slug}-{lane_id}"


def create_lane_branches(repo_root: Path, lanes_manifest: Any, *, start_point: str = "HEAD") -> list[str]:
    """Create each non-planning lane's CREATED branch in git, as ``implement`` would.

    The claim-time integrity refusal (#5338, ``claim_integrity_refusal``) refuses a
    consolidation whose approved lane has no created branch. Fixtures that drive a
    real ``_run_lane_based_consolidation`` must therefore allocate the lane
    branches instead of relying on the refusal being ignored (#5417). The name
    comes from the canonical ``lane_created_branch`` so fixtures cannot drift from
    what the allocator creates. Accepts a real ``LanesManifest`` or a mock with
    ``mission_slug``/``target_branch``/``lanes``. Fails if a lane branch already
    exists, so it can never silently reset real lane work. Returns the created names.

    It also ensures the mission branch (``mission_branch``) resolves, creating it
    only when absent: the approval-bound claim base (#5668) is that branch, and a
    claim whose base does not resolve is refused fail-closed before any lane is
    consolidated. An existing mission branch is never reset.
    """
    created: list[str] = []
    mission_branch = getattr(lanes_manifest, "mission_branch", None)
    if isinstance(mission_branch, str) and mission_branch:
        resolves = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{mission_branch}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if resolves.returncode != 0:
            subprocess.run(
                ["git", "-C", str(repo_root), "branch", mission_branch, start_point],
                check=True,
                capture_output=True,
                text=True,
            )
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane):
            continue
        branch = lane_created_branch(lanes_manifest, lane.lane_id)
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", branch, start_point],
            check=True,
            capture_output=True,
            text=True,
        )
        created.append(branch)
    return created


def commit_lane_implementation(repo_root: Path, feature_dir: Path, *, lane_id: str = "lane-a", path: str = "src/lane_impl.py") -> str:
    """#6715: commit a real change to *path* on a lane's branch, as an implementer would.

    ``move-task``, ``accept`` and ``consolidate`` refuse a work package whose evidence window
    (``planning_commit_sha..<lane branch>``, ``consolidation/wp_evidence.py``) holds no change to
    its ``owned_files``. A lanes fixture that moves a work package into review or approves it
    therefore needs that commit. The lane branch is created at the recorded planning commit when
    absent; the commit is written with git plumbing, so no checkout or index of *repo_root*
    changes. *path* must match the work package's ``owned_files``. Returns the new lane tip.
    """
    from specify_cli.lanes.persistence import require_lanes_json

    manifest = require_lanes_json(feature_dir)
    assert manifest.planning_commit_sha, "lanes.json must record planning_commit_sha (write it once the repository has a commit)"
    branch = lane_created_branch(manifest, lane_id)

    def git(*args: str, env: dict[str, str] | None = None, stdin: str | None = None) -> str:
        proc = subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True, env=env, input=stdin)
        return proc.stdout.strip()

    exists = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], capture_output=True, text=True, check=False)
    parent = exists.stdout.strip() if exists.returncode == 0 else manifest.planning_commit_sha
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        git("read-tree", parent, env=env)
        blob = git("hash-object", "-w", "--stdin", stdin=f"# implementation of {path}\n")
        git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
        tree = git("write-tree", env=env)
    tip = git("commit-tree", tree, "-p", parent, "-m", f"feat: implement {path}")
    git("update-ref", f"refs/heads/{branch}", tip)
    return tip
