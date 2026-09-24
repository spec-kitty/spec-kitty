"""Behavior contract for the shared lane-allocation base seam."""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest
from kernel.clock import now_utc_iso

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    UnhonorableBaseError,
    allocate_lane_worktree,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "lane-base-seam-demo"
MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-coord"
MISSION_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LEGACY_MISSION_SLUG = "lane-base-seam-legacy"
LEGACY_MISSION_BRANCH = f"kitty/mission-{LEGACY_MISSION_SLUG}"
WP_ID = "WP06"
EXPLICIT_BASE_BRANCH = "explicit-base"
LANE_A = "lane-a"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _git_out(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0


def _branch_missing(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode != 0


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _make_manifest(
    *,
    mission_slug: str = MISSION_SLUG,
    mission_branch: str,
    depends_on_lanes: tuple[str, ...] = (),
    planning_commit_sha: str | None = None,
) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=MISSION_ID,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_A,
                wp_ids=(WP_ID,),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=depends_on_lanes,
                parallel_group=0,
            ),
        ],
        computed_at=now_utc_iso(),
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    coordination_branch: str | None,
) -> None:
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": mission_slug,
        "target_branch": "main",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta))


def _lane(depends_on_lanes: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(
        lane_id=LANE_A,
        wp_ids=(WP_ID,),
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=depends_on_lanes,
        parallel_group=0,
    )


def test_seam_is_sole_parent_computer() -> None:
    source = inspect.getsource(allocate_lane_worktree)

    assert "resolve_lane_base_or_refuse(" in source
    assert "_guard_base_honorable(" not in source
    assert "_resolve_lane_parent(" not in source
    assert "coordination_branch if" not in source
    assert "else mission_branch" not in source
    assert "else lanes_manifest.mission_branch" not in source


@pytest.mark.parametrize(
    "route_name,coordination,mission_branch,expected_parent,expected_topology",
    [
        ("FRESH_COORD", COORD_BRANCH, MISSION_BRANCH, COORD_BRANCH, "COORD"),
        ("FRESH_LEGACY", None, MISSION_BRANCH, MISSION_BRANCH, "LEGACY"),
        ("REUSE", None, MISSION_BRANCH, MISSION_BRANCH, "LEGACY"),
        (
            "CRASH_RECOVERY",
            COORD_BRANCH,
            MISSION_BRANCH,
            COORD_BRANCH,
            "COORD",
        ),
    ],
)
def test_base_none_returns_topology_parent(
    route_name: str,
    coordination: str | None,
    mission_branch: str,
    expected_parent: str,
    expected_topology: str,
) -> None:
    from specify_cli.lanes.worktree_allocator import (
        LaneAllocationRoute,
        LaneBaseDecision,
        LaneTopology,
        resolve_lane_base_or_refuse,
    )

    route = LaneAllocationRoute[route_name]
    decision = resolve_lane_base_or_refuse(
        base=None,
        route=route,
        coordination_branch=coordination,
        mission_branch=mission_branch,
        wp_id=WP_ID,
        lane=_lane(),
    )
    assert isinstance(decision, LaneBaseDecision)
    assert decision.parent_ref == expected_parent
    assert decision.base_honored is False
    assert decision.route is route
    assert decision.topology is LaneTopology[expected_topology]


def test_fresh_coord_base_none_descends_coordination_branch(
    coordination_repo: Path,
) -> None:
    manifest = _make_manifest(mission_branch=MISSION_BRANCH)
    worktree_path, branch = allocate_lane_worktree(
        repo_root=coordination_repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert _is_ancestor(coordination_repo, COORD_BRANCH, branch)


def test_fresh_legacy_base_none_descends_mission_branch(
    legacy_repo: Path,
) -> None:
    manifest = _make_manifest(
        mission_slug=LEGACY_MISSION_SLUG,
        mission_branch=LEGACY_MISSION_BRANCH,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=legacy_repo,
        mission_slug=LEGACY_MISSION_SLUG,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert _is_ancestor(legacy_repo, LEGACY_MISSION_BRANCH, branch)


def test_fresh_legacy_origin_only_lane_still_creates_real_mission_branch(
    legacy_repo: Path,
) -> None:
    """#5001 regression: #4969's origin-preference must not leak into
    ``_ensure_mission_branch``.

    When the per-WP lane branch for a FRESH_LEGACY mission exists ONLY as
    ``origin/<lane_branch>`` (approved by a teammate, dropped locally) and no
    explicit ``--base`` is given, ``decision.parent_ref`` correctly resolves
    origin-first (#4969) so the lane *worktree* roots on the teammate's tip.
    But the mission INTEGRATION branch must still be ensured from the
    topology parent (``LEGACY_MISSION_BRANCH``), never from that origin-aware
    ref. Before the fix, ``_ensure_mission_branch`` received
    ``decision.parent_ref`` (``refs/remotes/origin/<lane_branch>``) and ran
    ``git branch refs/remotes/origin/<lane_branch> main`` -- creating a
    spuriously-named local branch instead of the real mission branch.
    """
    from specify_cli.lanes.branch_naming import lane_branch_name

    repo = legacy_repo
    lane_branch = lane_branch_name(LEGACY_MISSION_SLUG, LANE_A)

    # Real bare origin; push the lane branch there, then drop the local ref
    # so it exists ONLY as origin/<lane_branch> (mirrors #4969's fixture shape).
    bare = repo.parent / "origin.git"
    _git(repo, "init", "--bare", "-q", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "checkout", "-q", "-b", lane_branch)
    (repo / "lane-work.txt").write_text("approved lane work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "approved lane work")
    _git(repo, "push", "-q", "origin", f"{lane_branch}:{lane_branch}")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", lane_branch)

    # Fixture preconditions: origin has it, local does not.
    assert not _branch_missing(repo, f"refs/remotes/origin/{lane_branch}")
    assert _branch_missing(repo, lane_branch)

    manifest = _make_manifest(
        mission_slug=LEGACY_MISSION_SLUG,
        mission_branch=LEGACY_MISSION_BRANCH,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=LEGACY_MISSION_SLUG,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()

    # (a) the real mission integration branch must exist.
    assert not _branch_missing(repo, LEGACY_MISSION_BRANCH), "the real mission integration branch was never created"

    # (b) no branch literally named after the origin ref (or any raw ref/sha)
    # was created — the exact #5001 misnaming.
    spurious = f"refs/heads/refs/remotes/origin/{lane_branch}"
    result = subprocess.run(["git", "rev-parse", "--verify", spurious], cwd=repo, capture_output=True)
    assert result.returncode != 0, f"a spurious branch literally named {spurious!r} was created"

    local_branches = set(_git_out(repo, "for-each-ref", "refs/heads", "--format=%(refname:short)").splitlines())
    assert local_branches == {"main", LEGACY_MISSION_BRANCH, branch}, (
        f"unexpected local branch set after FRESH_LEGACY allocation of an origin-only lane: {local_branches}"
    )


@pytest.mark.parametrize(
    "route_name,coordination",
    [
        ("FRESH_COORD", COORD_BRANCH),
        ("FRESH_LEGACY", None),
    ],
)
def test_honored_base_replaces_topology_parent(
    route_name: str,
    coordination: str | None,
) -> None:
    from specify_cli.lanes.worktree_allocator import (
        LaneAllocationRoute,
        resolve_lane_base_or_refuse,
    )

    decision = resolve_lane_base_or_refuse(
        base=EXPLICIT_BASE_BRANCH,
        route=LaneAllocationRoute[route_name],
        coordination_branch=coordination,
        mission_branch=MISSION_BRANCH,
        wp_id=WP_ID,
        lane=_lane(),
    )
    assert decision.parent_ref == EXPLICIT_BASE_BRANCH
    assert decision.base_honored is True


@pytest.mark.parametrize(
    "route_name,trigger",
    [
        ("REUSE", "reuse"),
        ("CRASH_RECOVERY", "crash_recovery"),
    ],
)
def test_base_on_already_created_route_refuses(
    route_name: str,
    trigger: str,
) -> None:
    from specify_cli.lanes.worktree_allocator import (
        LaneAllocationRoute,
        resolve_lane_base_or_refuse,
    )

    with pytest.raises(UnhonorableBaseError) as exc_info:
        resolve_lane_base_or_refuse(
            base=EXPLICIT_BASE_BRANCH,
            route=LaneAllocationRoute[route_name],
            coordination_branch=COORD_BRANCH,
            mission_branch=MISSION_BRANCH,
            wp_id=WP_ID,
        )
    assert exc_info.value.route == trigger
    assert exc_info.value.wp_id == WP_ID
    assert exc_info.value.base == EXPLICIT_BASE_BRANCH


def test_dependency_lane_base_refuses() -> None:
    from specify_cli.lanes.worktree_allocator import (
        LaneAllocationRoute,
        resolve_lane_base_or_refuse,
    )

    with pytest.raises(UnhonorableBaseError) as exc_info:
        resolve_lane_base_or_refuse(
            base=EXPLICIT_BASE_BRANCH,
            route=LaneAllocationRoute.FRESH_COORD,
            coordination_branch=COORD_BRANCH,
            mission_branch=MISSION_BRANCH,
            wp_id=WP_ID,
            lane=_lane(depends_on_lanes=("lane-b",)),
        )
    assert exc_info.value.route == "dependency_lane"


def test_dependency_lane_refusal_leaves_no_residual(
    coordination_repo: Path,
) -> None:
    manifest = _make_manifest(
        mission_branch=MISSION_BRANCH,
        depends_on_lanes=("lane-b",),
    )
    with pytest.raises(UnhonorableBaseError) as exc_info:
        allocate_lane_worktree(
            repo_root=coordination_repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
            base=EXPLICIT_BASE_BRANCH,
        )
    assert exc_info.value.route == "dependency_lane"

    worktree_path = coordination_repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_A}"
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_A}"
    assert not worktree_path.exists()
    assert _branch_missing(coordination_repo, lane_branch)


def test_detached_base_refusal_leaves_no_residual(
    coordination_repo: Path,
) -> None:
    repo = coordination_repo
    _git(repo, "checkout", "-q", "--orphan", "detached-root")
    (repo / "detached.txt").write_text("detached root\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "detached root commit")
    detached_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "-f", EXPLICIT_BASE_BRANCH, detached_sha)
    _git(repo, "checkout", "-q", "main")

    seed_sha = _git_out(repo, "rev-parse", "main")
    _git(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "planning-tmp")

    manifest = _make_manifest(
        mission_branch=MISSION_BRANCH,
        planning_commit_sha=planning_sha,
    )
    with pytest.raises(UnhonorableBaseError) as exc_info:
        allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
            base=EXPLICIT_BASE_BRANCH,
        )
    assert exc_info.value.route == "detached_base"

    worktree_path = repo / ".worktrees" / f"{MISSION_SLUG}-{LANE_A}"
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_A}"
    assert not worktree_path.exists()
    assert _branch_missing(repo, lane_branch)


def test_reuse_refusal_does_not_disturb_existing_lane(
    coordination_repo: Path,
) -> None:
    manifest = _make_manifest(mission_branch=MISSION_BRANCH)
    worktree_path, lane_branch = allocate_lane_worktree(
        repo_root=coordination_repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    head_before = _git_out(worktree_path, "rev-parse", "HEAD")

    with pytest.raises(UnhonorableBaseError) as exc_info:
        allocate_lane_worktree(
            repo_root=coordination_repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
            base=EXPLICIT_BASE_BRANCH,
        )
    assert exc_info.value.route == "reuse"
    assert worktree_path.exists()
    assert _git_out(worktree_path, "rev-parse", "HEAD") == head_before
    assert not _branch_missing(coordination_repo, lane_branch)


@pytest.fixture
def coordination_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(
        feature_dir,
        mission_slug=MISSION_SLUG,
        coordination_branch=COORD_BRANCH,
    )
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")

    _git(repo, "branch", COORD_BRANCH, seed_sha)
    _git(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    _git(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base.txt").write_text("explicit base work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "explicit base work")
    _git(repo, "checkout", "-q", "main")
    return repo


@pytest.fixture
def legacy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / LEGACY_MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(
        feature_dir,
        mission_slug=LEGACY_MISSION_SLUG,
        coordination_branch=None,
    )
    (feature_dir / "spec.md").write_text("# spec\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo
