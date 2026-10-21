"""Tests for lane worktree allocator.

These tests use real git repos (not mocks) since the allocator
exercises git worktree and branch operations.
"""

import subprocess

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    DirtyWorktreeError,
    LaneNotFoundError,
    allocate_lane_worktree,
)

pytestmark = pytest.mark.git_repo


def _make_git_repo(path):
    """Create a minimal git repo with an initial commit."""
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path), capture_output=True, check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path), capture_output=True, check=True,
    )


def _make_manifest(mission_slug="010-feat", target_branch="main"):
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=("WP03",),
                write_scope=("tests/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-04-03T12:00:00+00:00",
        computed_from="test",
    )


class TestAllocateLaneWorktree:
    def test_creates_mission_branch_and_lane_worktree(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        # Rename default branch to "main" for consistency
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )

        manifest = _make_manifest()
        wt_path, branch = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)

        assert wt_path == repo / ".worktrees" / "010-feat-lane-a"
        assert wt_path.exists()
        assert branch == "kitty/mission-010-feat-lane-a"

        # Mission branch should also exist
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "refs/heads/kitty/mission-010-feat"],
            cwd=str(repo), capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_reuses_existing_clean_worktree(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )

        manifest = _make_manifest()

        # First WP creates the worktree
        wt_path1, branch1 = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)

        # Second WP in same lane reuses it
        wt_path2, branch2 = allocate_lane_worktree(repo, "010-feat", "WP02", manifest)

        assert wt_path1 == wt_path2
        assert branch1 == branch2

    def test_rejects_dirty_worktree(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )

        manifest = _make_manifest()
        wt_path, _ = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)

        # Dirty the worktree
        (wt_path / "dirty.txt").write_text("uncommitted\n")

        with pytest.raises(DirtyWorktreeError, match="uncommitted changes"):
            allocate_lane_worktree(repo, "010-feat", "WP02", manifest)

    def test_different_lanes_get_different_worktrees(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )

        manifest = _make_manifest()

        wt_a, branch_a = allocate_lane_worktree(repo, "010-feat", "WP01", manifest)
        wt_b, branch_b = allocate_lane_worktree(repo, "010-feat", "WP03", manifest)

        assert wt_a != wt_b
        assert branch_a != branch_b
        assert "lane-a" in str(wt_a)
        assert "lane-b" in str(wt_b)

    def test_wp_not_in_any_lane_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        manifest = _make_manifest()

        with pytest.raises(LaneNotFoundError, match="WP99"):
            allocate_lane_worktree(repo, "010-feat", "WP99", manifest)

    def test_mission_branch_not_recreated(self, tmp_path):
        """Mission branch is created once, not on every lane allocation."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )

        manifest = _make_manifest()

        # First lane creates mission branch
        allocate_lane_worktree(repo, "010-feat", "WP01", manifest)

        # Get mission branch commit
        result1 = subprocess.run(
            ["git", "rev-parse", "kitty/mission-010-feat"],
            cwd=str(repo), capture_output=True, text=True, check=True,
        )

        # Second lane should NOT recreate it
        allocate_lane_worktree(repo, "010-feat", "WP03", manifest)

        result2 = subprocess.run(
            ["git", "rev-parse", "kitty/mission-010-feat"],
            cwd=str(repo), capture_output=True, text=True, check=True,
        )

        assert result1.stdout.strip() == result2.stdout.strip()


class TestDefensiveHelpers:
    """Direct coverage for the allocator's defensive/recovery helpers."""

    def test_read_coordination_branch_none_when_meta_absent(self, tmp_path):
        from specify_cli.lanes.worktree_allocator import _read_coordination_branch

        assert _read_coordination_branch(tmp_path, "no-such-mission") is None

    def test_read_coordination_branch_none_on_malformed_json(self, tmp_path):
        """A meta.json that is not valid JSON must yield None, not crash."""
        from specify_cli.lanes.worktree_allocator import _read_coordination_branch

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{ this is : not json ]")
        assert _read_coordination_branch(tmp_path, "010-feat") is None

    def test_read_coordination_branch_none_when_field_missing(self, tmp_path):
        from specify_cli.lanes.worktree_allocator import _read_coordination_branch

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text('{"mission_id": "01ABC"}')
        assert _read_coordination_branch(tmp_path, "010-feat") is None

    def test_read_coordination_branch_returns_value(self, tmp_path):
        from specify_cli.lanes.worktree_allocator import _read_coordination_branch

        feature_dir = tmp_path / "kitty-specs" / "010-feat"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            '{"coordination_branch": "kitty/mission-010-feat-coord"}'
        )
        assert (
            _read_coordination_branch(tmp_path, "010-feat")
            == "kitty/mission-010-feat-coord"
        )

    def test_ensure_branch_exists_creates_missing_branch(self, tmp_path):
        """Legacy/upgrade-in-place recovery: a missing branch is recreated from
        the fallback parent rather than crashing."""
        from specify_cli.lanes.worktree_allocator import (
            _branch_exists,
            _ensure_branch_exists,
        )

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )
        assert not _branch_exists(repo, "kitty/mission-recovered")
        _ensure_branch_exists(repo, "kitty/mission-recovered", "main")
        assert _branch_exists(repo, "kitty/mission-recovered")

    def test_ensure_branch_exists_noop_when_present(self, tmp_path):
        from specify_cli.lanes.worktree_allocator import _ensure_branch_exists

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=str(repo), capture_output=True, check=True,
        )
        # main already exists — must be a no-op (no raise).
        _ensure_branch_exists(repo, "main", "main")

    def test_create_branch_from_raises_on_bad_parent(self, tmp_path):
        """Creating a branch from a non-existent parent raises a RuntimeError."""
        from specify_cli.lanes.worktree_allocator import _create_branch_from

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        with pytest.raises(RuntimeError, match="Failed to create"):
            _create_branch_from(repo, "kitty/mission-x", "no-such-parent-ref")

    def test_create_branch_from_never_reads_a_dash_name_as_an_option(self, tmp_path):
        """A ``meta.json`` branch value such as ``-f`` must not become ``git branch -f main``.

        Without ``--end-of-options`` git parses the value as the force flag and
        resets the local ``main`` to HEAD (Sonar S6350, #4304).
        """
        from specify_cli.lanes.worktree_allocator import _create_branch_from

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        subprocess.run(["git", "branch", "-M", "main"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(["git", "checkout", "-b", "work"], cwd=str(repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "work"],
            cwd=str(repo), capture_output=True, check=True,
        )

        def _main_tip() -> str:
            return subprocess.run(
                ["git", "rev-parse", "refs/heads/main"],
                cwd=str(repo), capture_output=True, text=True, check=True,
            ).stdout.strip()

        before = _main_tip()
        with pytest.raises(RuntimeError, match="Failed to create"):
            _create_branch_from(repo, "-f", "main")
        assert _main_tip() == before

    def test_validate_worktree_clean_raises_when_git_status_fails(self, tmp_path):
        """A non-git path makes ``git status`` fail → RuntimeError (not silent)."""
        from specify_cli.lanes.worktree_allocator import _validate_worktree_clean

        not_a_repo = tmp_path / "not-a-repo"
        not_a_repo.mkdir()
        with pytest.raises(RuntimeError, match="git status failed"):
            _validate_worktree_clean(not_a_repo, "lane-a")

    def test_validate_worktree_clean_raises_on_dirty_tree(self, tmp_path):
        from specify_cli.lanes.worktree_allocator import (
            DirtyWorktreeError,
            _validate_worktree_clean,
        )

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        (repo / "dirty.txt").write_text("uncommitted\n")
        with pytest.raises(DirtyWorktreeError, match="uncommitted changes"):
            _validate_worktree_clean(repo, "lane-a")
