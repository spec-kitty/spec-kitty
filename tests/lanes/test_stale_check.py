"""Tests for stale-lane merge blocker.

Uses real git repos to test file-level overlap detection.
"""

import subprocess

import pytest

from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import _stale_remediation, check_lane_staleness

pytestmark = pytest.mark.git_repo


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=True)


def _commit(repo, filename, content, message):
    (repo / filename).parent.mkdir(parents=True, exist_ok=True)
    (repo / filename).write_text(content)
    _run(["git", "add", filename], repo)
    _run(["git", "commit", "-m", message], repo)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@test.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _commit(repo, "README.md", "init\n", "init")
    _run(["git", "branch", "-M", "main"], repo)
    return repo


def _lane(lane_id="lane-a", wp_ids=("WP01",)):
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=wp_ids,
        write_scope=("src/**",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


class TestCheckLaneStaleness:
    def test_not_stale_when_mission_unchanged(self, tmp_path):
        repo = _make_repo(tmp_path)
        # Create mission and lane branches from same point
        _run(["git", "branch", "kitty/mission-feat"], repo)
        _run(["git", "branch", "kitty/mission-feat-lane-a"], repo)

        result = check_lane_staleness(
            _lane(), "kitty/mission-feat-lane-a", "kitty/mission-feat", repo,
        )
        assert result.is_stale is False

    def test_not_stale_when_no_file_overlap(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "kitty/mission-feat"], repo)
        _run(["git", "branch", "kitty/mission-feat-lane-a"], repo)

        # Mission changes file A
        _run(["git", "checkout", "kitty/mission-feat"], repo)
        _commit(repo, "src/a.py", "mission\n", "mission change")

        # Lane changes file B
        _run(["git", "checkout", "kitty/mission-feat-lane-a"], repo)
        _commit(repo, "src/b.py", "lane\n", "lane change")

        _run(["git", "checkout", "main"], repo)

        result = check_lane_staleness(
            _lane(), "kitty/mission-feat-lane-a", "kitty/mission-feat", repo,
        )
        assert result.is_stale is False

    def test_stale_when_overlapping_files(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "kitty/mission-feat"], repo)
        _run(["git", "branch", "kitty/mission-feat-lane-a"], repo)

        # Mission changes src/views.py
        _run(["git", "checkout", "kitty/mission-feat"], repo)
        _commit(repo, "src/views.py", "mission version\n", "mission change")

        # Lane also changes src/views.py
        _run(["git", "checkout", "kitty/mission-feat-lane-a"], repo)
        _commit(repo, "src/views.py", "lane version\n", "lane change")

        _run(["git", "checkout", "main"], repo)

        result = check_lane_staleness(
            _lane(), "kitty/mission-feat-lane-a", "kitty/mission-feat", repo,
        )
        assert result.is_stale is True
        assert result.stale_files == ["src/views.py"]
        assert result.remediation is not None
        assert "git merge" in result.remediation

    def test_stale_planning_lane_remediation_has_no_worktree_path(self, tmp_path):
        """The canonical planning lane has no ``.worktrees/`` entry by design --
        remediation must not send the operator to a directory that can't exist."""
        repo = _make_repo(tmp_path)
        # lane_branch_name() returns the target branch itself for lane-planning
        # (no synthetic kitty/mission-*-lane-planning branch), so the fixture
        # branch here stands in for that target branch.
        _run(["git", "branch", "kitty/mission-feat"], repo)
        _run(["git", "branch", "target-branch"], repo)

        _run(["git", "checkout", "kitty/mission-feat"], repo)
        _commit(repo, "kitty-specs/feat/WP10.md", "mission version\n", "mission change")

        _run(["git", "checkout", "target-branch"], repo)
        _commit(repo, "kitty-specs/feat/WP10.md", "target version\n", "target change")

        _run(["git", "checkout", "main"], repo)

        result = check_lane_staleness(
            _lane(lane_id="lane-planning"),
            "target-branch",
            "kitty/mission-feat",
            repo,
        )
        assert result.is_stale is True
        assert result.remediation is not None
        assert ".worktrees/" not in result.remediation
        assert "repository-root checkout" in result.remediation
        assert "git checkout target-branch && git merge kitty/mission-feat" in result.remediation
        assert "spec-kitty agent status materialize" in result.remediation

    def test_stale_reports_only_overlapping_files(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "kitty/mission-feat"], repo)
        _run(["git", "branch", "kitty/mission-feat-lane-a"], repo)

        # Mission changes two files
        _run(["git", "checkout", "kitty/mission-feat"], repo)
        _commit(repo, "src/a.py", "m\n", "m1")
        _commit(repo, "src/b.py", "m\n", "m2")

        # Lane changes one overlapping + one unique
        _run(["git", "checkout", "kitty/mission-feat-lane-a"], repo)
        _commit(repo, "src/a.py", "l\n", "l1")
        _commit(repo, "src/c.py", "l\n", "l2")

        _run(["git", "checkout", "main"], repo)

        result = check_lane_staleness(
            _lane(), "kitty/mission-feat-lane-a", "kitty/mission-feat", repo,
        )
        assert result.is_stale is True
        assert result.stale_files == ["src/a.py"]


class TestStaleRemediation:
    """Pure-function coverage for the remediation-text branch (no git needed)."""

    def test_lane_workspace_gets_worktree_remediation(self):
        remediation = _stale_remediation(
            _lane(lane_id="lane-a"), "kitty/mission-feat-lane-a", "kitty/mission-feat",
        )
        assert "cd .worktrees/*-lane-a" in remediation
        assert "git merge kitty/mission-feat" in remediation

    def test_planning_lane_gets_repo_root_remediation(self):
        remediation = _stale_remediation(
            _lane(lane_id="lane-planning"), "main", "kitty/mission-feat",
        )
        assert ".worktrees/" not in remediation
        assert "repository-root checkout" in remediation
        assert "git checkout main && git merge kitty/mission-feat" in remediation
        assert "spec-kitty agent status materialize" in remediation

    def test_planning_lane_remediation_names_status_materialize(self):
        """A raw `git merge` on the planning lane produces a `status.json`
        conflict git cannot text-reconcile (status.json is a derived
        projection of status.events.jsonl, intentionally driver-exempt --
        see tests/architectural/test_merge_reconciliation_class_guard.py).
        The remediation must name the tool's own recovery -- `status
        materialize` rebuilds status.json from the event log deterministically
        -- followed by `git add`, instead of leaving the operator stuck on an
        unreconcilable conflict."""
        remediation = _stale_remediation(
            _lane(lane_id="lane-planning"), "main", "kitty/mission-feat",
        )
        assert "spec-kitty agent status materialize" in remediation
        assert "git add" in remediation
        # No merge driver introduced -- rebuild via the tool instead of a driver.
        assert "merge driver" not in remediation
        assert "do not hand-edit" in remediation
