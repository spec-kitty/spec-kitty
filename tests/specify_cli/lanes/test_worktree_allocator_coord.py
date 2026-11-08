"""Coordination-branch-aware behaviour of :mod:`worktree_allocator`.

Covers the WP04 contract (#1348):

* New-topology missions (``meta.json`` has ``coordination_branch``):
  lane branches are parented on the coordination branch, and lane
  worktrees receive the status-files sparse-checkout exclusion.
* Missions without ``coordination_branch``: allocator falls back to the
  manifest's ``mission_branch``. A stamped ``lanes`` Mission still gets the
  status exclusion (FR-040); a genuinely-legacy one (no stored topology)
  keeps its lane status files, because it writes status from the lane.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


HUMAN_SLUG = "demo-feature"
# Post-WP03 mission_slug carries the mid8 suffix verbatim. Mirrors
# mission_creation.py's mission_slug_formatted construction.
MISSION_SLUG = "demo-feature-01J6XW9K"
MISSION_ID = "01J6XW9KABCDEFGHJKMNPQRSTV"  # full ULID, mid8 = "01J6XW9K"
MID8 = "01J6XW9K"
# Mission directory equals mission_slug (which itself already carries
# the mid8 suffix in the post-WP03 format).
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LEGACY_MISSION_SLUG = HUMAN_SLUG
LEGACY_MISSION_BRANCH = f"kitty/mission-{LEGACY_MISSION_SLUG}"
MISSION_DIR_NEW = MISSION_SLUG


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_manifest(
    *,
    mission_branch: str,
    mission_id: str,
    lane_id: str = "lane-a",
    wp_ids: tuple[str, ...] = ("WP01",),
) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[ExecutionLane(
            lane_id=lane_id,
            wp_ids=wp_ids,
            write_scope=(),
            predicted_surfaces=(),
            depends_on_lanes=(),
            parallel_group=0,
        )],
        computed_at=now_utc_iso(),
        computed_from="test",
    )


@pytest.fixture
def new_topology_repo(tmp_path: Path) -> Path:
    """Tmp repo with coordination branch + meta.json carrying it.

    Mimics post-WP03 mission state on disk.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    spec_dir = repo / "kitty-specs" / MISSION_DIR_NEW
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n")
    (spec_dir / "status.events.jsonl").write_text(
        '{"actor":"test","wp_id":"WP01"}\n'
    )
    (spec_dir / "status.json").write_text("{}\n")
    (spec_dir / "meta.json").write_text(json.dumps({
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "coordination_branch": COORD_BRANCH,
    }))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", COORD_BRANCH)
    return repo


@pytest.fixture
def legacy_repo(tmp_path: Path) -> Path:
    """Tmp repo with no ``coordination_branch`` field — legacy topology."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    # Legacy spec dir uses the bare slug (no mid8).
    spec_dir = repo / "kitty-specs" / LEGACY_MISSION_SLUG
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n")
    # NB: no coordination_branch field, mirroring pre-WP03 missions.
    (spec_dir / "meta.json").write_text(json.dumps({
        "mission_slug": LEGACY_MISSION_SLUG,
    }))
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def test_new_topology_parents_on_coordination_branch(
    new_topology_repo: Path,
) -> None:
    manifest = _make_manifest(
        mission_branch=COORD_BRANCH, mission_id=MISSION_ID,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=new_topology_repo,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert branch == f"kitty/mission-{MISSION_SLUG}-lane-a"

    # The lane branch must be reachable from the coordination branch.
    result = subprocess.run(
        ["git", "-C", str(new_topology_repo), "merge-base",
         "--is-ancestor", COORD_BRANCH, branch],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"lane branch {branch} should descend from {COORD_BRANCH}"
    )


def test_explicit_base_replaces_coordination_branch_parent(
    new_topology_repo: Path,
) -> None:
    """#3571 (D1/FR-001/FR-002) companion: an explicit ``base`` fully
    REPLACES ``coordination_branch`` as a fresh no-dependency lane's parent
    -- it is never layered on top of it. Work landed on the coordination
    branch AFTER the base was chosen must not leak into the lane.
    """
    repo = new_topology_repo

    # Extra coord-only work, landed on COORD_BRANCH after the fixture seed.
    _git(repo, "checkout", "-q", COORD_BRANCH)
    (repo / "coord-only.txt").write_text("coord-only work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "coord-only work")
    coord_only_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", COORD_BRANCH],
        capture_output=True, text=True,
    ).stdout.strip()
    _git(repo, "checkout", "-q", "main")

    # A divergent base branch off "main" (predates the coord-only work).
    _git(repo, "branch", "explicit-base")

    manifest = _make_manifest(mission_branch=COORD_BRANCH, mission_id=MISSION_ID)
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo, mission_slug=MISSION_SLUG, wp_id="WP01",
        lanes_manifest=manifest, base="explicit-base",
    )
    assert worktree_path.exists()

    is_ancestor_base = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", "explicit-base", branch],
        capture_output=True,
    )
    assert is_ancestor_base.returncode == 0, (
        f"lane branch {branch} should descend from the supplied base"
    )

    is_ancestor_coord_only = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", coord_only_sha, branch],
        capture_output=True,
    )
    assert is_ancestor_coord_only.returncode != 0, (
        "lane must NOT inherit coord-only work landed after --base was chosen "
        "(D1 -- base ALONE, coordination_branch not layered on)"
    )


def test_new_topology_applies_sparse_checkout(
    new_topology_repo: Path,
) -> None:
    manifest = _make_manifest(
        mission_branch=COORD_BRANCH, mission_id=MISSION_ID,
    )
    worktree_path, _ = allocate_lane_worktree(
        repo_root=new_topology_repo,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        lanes_manifest=manifest,
    )

    lane_spec_dir = worktree_path / "kitty-specs" / MISSION_DIR_NEW
    assert (lane_spec_dir / "spec.md").exists()
    assert not (lane_spec_dir / "status.events.jsonl").exists()
    assert not (lane_spec_dir / "status.json").exists()


def _sparse_checkout_flag(worktree_path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(worktree_path), "config",
         "--get", "core.sparseCheckout"],
        capture_output=True, text=True,
    ).stdout.strip()


def _stamp_legacy_meta(repo: Path, **fields: str) -> None:
    """Add *fields* to the legacy fixture's ``meta.json`` and commit a status log beside it."""
    meta_path = repo / "kitty-specs" / LEGACY_MISSION_SLUG / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta.update(fields)
    meta_path.write_text(json.dumps(meta))
    (meta_path.parent / "status.events.jsonl").write_text('{"actor":"test","wp_id":"WP01"}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "stamp topology and seed status")


def test_legacy_topology_keeps_lane_status_files(
    legacy_repo: Path,
) -> None:
    """No ``coordination_branch`` and no stored topology => a genuinely-legacy
    Mission: parent on mission_branch, and NO status exclusion.

    Such a Mission still writes its status from the lane checkout and
    ``safe_commit`` cannot stage a sparse-excluded path, so the lane keeps its
    status files (#7316 landing fold "leave a legacy Mission's lane status
    files in place"; ``lane_checkout._mission_is_genuinely_legacy``).
    """
    (legacy_repo / "kitty-specs" / LEGACY_MISSION_SLUG / "status.events.jsonl").write_text(
        '{"actor":"test","wp_id":"WP01"}\n'
    )
    _git(legacy_repo, "add", ".")
    _git(legacy_repo, "commit", "-q", "-m", "seed legacy status")
    manifest = _make_manifest(
        mission_branch=LEGACY_MISSION_BRANCH,
        mission_id="legacy",  # too short for mid8(); irrelevant on legacy path
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=legacy_repo,
        mission_slug=LEGACY_MISSION_SLUG,
        wp_id="WP01",
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    assert branch == f"kitty/mission-{LEGACY_MISSION_SLUG}-lane-a"

    assert _sparse_checkout_flag(worktree_path) != "true"
    lane_spec_dir = worktree_path / "kitty-specs" / LEGACY_MISSION_SLUG
    assert (lane_spec_dir / "spec.md").exists()
    assert (lane_spec_dir / "status.events.jsonl").exists()


def test_lanes_topology_without_coordination_branch_applies_sparse_checkout(
    legacy_repo: Path,
) -> None:
    """A stamped ``lanes`` Mission (no ``coordination_branch``) is not legacy:
    the status exclusion is registered all the same (Mission WP09, FR-040:
    every topology with code lanes, ``lanes`` included).
    """
    _stamp_legacy_meta(legacy_repo, topology="lanes")
    manifest = _make_manifest(
        mission_branch=LEGACY_MISSION_BRANCH,
        mission_id="legacy",  # too short for mid8(); no coordination branch to key
    )
    worktree_path, _ = allocate_lane_worktree(
        repo_root=legacy_repo,
        mission_slug=LEGACY_MISSION_SLUG,
        wp_id="WP01",
        lanes_manifest=manifest,
    )

    assert _sparse_checkout_flag(worktree_path) == "true"
    lane_spec_dir = worktree_path / "kitty-specs" / LEGACY_MISSION_SLUG
    assert (lane_spec_dir / "spec.md").exists()
    assert not (lane_spec_dir / "status.events.jsonl").exists()
