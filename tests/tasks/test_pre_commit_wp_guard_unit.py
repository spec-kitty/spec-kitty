"""Tests for lane-branch protection in the manual pre-commit workflow hook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: reads scripts/git-hooks/ not in sandbox


def test_python_hook_detects_active_wp_ownership_in_reused_lane_context(tmp_path: Path) -> None:
    from specify_cli.policy.commit_guard_hook import _detect_ownership_scope
    from specify_cli.status.models import Lane, StatusEvent
    from tests._support.status_seed import seed_status_event
    from specify_cli.workspace.context import WorkspaceContext, save_context

    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir = repo / "kitty-specs" / "001-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-old.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Old\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        "- src/old.py\n"
        "---\n\n"
        "Old body.\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP04-active.md").write_text(
        "---\n"
        "work_package_id: WP04\n"
        "title: Active\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        "- src/active.py\n"
        "---\n\n"
        "Active body.\n",
        encoding="utf-8",
    )
    save_context(
        repo,
        WorkspaceContext(
            wp_id="WP01",
            mission_slug="001-test-feature",
            worktree_path=".worktrees/001-test-feature-lane-a",
            branch_name="kitty/mission-001-test-feature-lane-a",
            base_branch="kitty/mission-001-test-feature",
            base_commit="abc123",
            dependencies=[],
            created_at="2026-01-25T12:00:00Z",
            created_by="implement-command-lane",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP01", "WP04"],
            current_wp="WP01",
        ),
    )
    for wp_id, lane in (("WP01", Lane.DONE), ("WP04", Lane.IN_PROGRESS)):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{wp_id}-{lane.value}",
                mission_slug="001-test-feature",
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at="2026-01-25T12:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )

    scope = _detect_ownership_scope(
        worktree_root=repo / ".worktrees" / "001-test-feature-lane-a",
        repo_root=repo,
        branch="kitty/mission-001-test-feature-lane-a",
    )

    assert scope.active_wp_id == "WP04"
    assert scope.owned_files == ["src/active.py"]
    assert scope.context_source == "canonical_status"


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _hook_script() -> Path:
    hook_script = Path(__file__).resolve().parents[2] / "scripts" / "git-hooks" / "pre-commit-task-workflow.sh"
    assert hook_script.exists()
    return hook_script


def test_lane_branch_hook_blocks_kitty_specs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    hook_path = _hook_script()

    subprocess.run(
        ["git", "checkout", "-b", "kitty/mission-001-test-feature-lane-a"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    blocked_file = repo / "kitty-specs" / "001-test-feature" / "tasks" / "WP01-test.md"
    blocked_file.parent.mkdir(parents=True)
    blocked_file.write_text(
        "---\n"
        "work_package_id: WP01\n"
        'shell_pid: "123"\n'
        'agent: "tester"\n'
        "---\n\n"
        "## Activity Log\n"
        "- 2026-01-01T00:00:00Z -- tester -- Started implementation\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", str(blocked_file)], cwd=repo, check=True, capture_output=True)

    result = subprocess.run(
        [str(hook_path)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "lane branches must not commit kitty-specs/" in result.stdout.lower()

def test_lane_branch_hook_allows_non_lane_branches(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    hook_path = _hook_script()

    allowed_file = repo / "kitty-specs" / "001-test-feature" / "tasks" / "WP01-test.md"
    allowed_file.parent.mkdir(parents=True)
    allowed_file.write_text(
        "---\n"
        "work_package_id: WP01\n"
        'shell_pid: "123"\n'
        'agent: "tester"\n'
        "---\n\n"
        "## Activity Log\n"
        "- 2026-01-01T00:00:00Z -- tester -- Started implementation\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", str(allowed_file)], cwd=repo, check=True, capture_output=True)

    result = subprocess.run(
        [str(hook_path)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
