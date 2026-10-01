"""Unit tests for git validation in move-task command.

Tests the validation that prevents moving WPs to "done" status
when there are uncommitted changes in the worktree.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner
from specify_cli.cli.commands.agent.tasks import app, _validate_ready_for_review
from specify_cli.status.store import append_event, read_events
from specify_cli.status.models import StatusEvent, Lane
from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest

pytestmark = pytest.mark.git_repo

runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_move_task_sync_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep command unit tests hermetic even when global SaaS test flag is on.

    Also sets the documented operator escape hatch for fixtures that run the
    command on a protected ``main`` fixture branch — the ONE sanctioned
    ambient waiver (``SPEC_KITTY_TEST_MODE`` no longer waives the
    protected-branch pre-check; PR #1850 guard-bypass fix).
    """
    import specify_cli.status.emit as status_emit

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)
@pytest.fixture
def git_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Create a git repository with a worktree for testing.

    Returns:
        Tuple of (repo_root, worktree_path)
    """
    repo = tmp_path / "test-repo"
    repo.mkdir()

    # Initialize git repo with explicit branch name
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

    # Create .kittify marker with a file inside (git won't track empty directories)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("# Config\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create feature directory and task file
    feature_dir = repo / "kitty-specs" / "017-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    task_file = tasks_dir / "WP01-test-task.md"
    task_content = """---
work_package_id: "WP01"
title: "Test Task"
agent: "test-agent"
shell_pid: ""
subtasks: []
---

# Work Package: WP01 - Test Task

Test content here.

## Activity Log

- 2025-01-01T00:00:00Z – system – lane=planned – Initial creation
"""
    task_file.write_text(task_content)

    # Seed canonical status events so move_task hard-fail check passes.
    # The WP starts at "doing" (in_progress), so seed planned -> in_progress.
    for lane_val in ("planned", "in_progress"):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-WP01-{lane_val}",
                mission_slug="017-test-feature",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane_val),
                at="2025-01-01T00:00:00+00:00",
                actor="test-fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add task file"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create worktree with branch that has commits beyond main
    worktree_dir = lane_worktree_path(repo, "017-test-feature")
    subprocess.run(
        ["git", "worktree", "add", "-b", lane_branch_name("017-test-feature"), str(worktree_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Add a commit in the worktree (so branch has commits beyond main)
    (worktree_dir / "implementation.txt").write_text("Implementation work\n")
    subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add implementation"],
        cwd=worktree_dir,
        check=True,
        capture_output=True,
    )

    return repo, worktree_dir


class TestMoveTaskGitValidation:
    """Tests for git validation and merge ancestry guardrails for done transitions."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_with_uncommitted_changes_fails(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Should fail when moving to done with uncommitted changes."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Create uncommitted file in worktree
        (worktree / "uncommitted.txt").write_text("Uncommitted work\n")

        # Try to move to done (should fail)
        result = runner.invoke(
            app,
            ["move-task", "WP01", "--to", "done", "--force", "--json"],
        )

        # Verify failure
        assert result.exit_code == 1
        # Parse only the first JSON object (CLI may output multiple)
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        error_text = output["error"].lower()
        assert "uncommitted" in error_text or "changes" in error_text or "merge ancestry" in error_text

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_with_committed_changes_but_unmerged_fails(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Should fail when moving to done if branch is not merged and no override provided."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Worktree already has committed changes (from fixture)
        # Verify no uncommitted changes
        result_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result_status.stdout.strip() == ""

        # Move to done (should fail: branch has not been merged to target)
        result = runner.invoke(
            app,
            ["move-task", "WP01", "--to", "done", "--force", "--json"],
        )

        # Verify failure
        assert result.exit_code == 1
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        assert "merge ancestry" in output["error"].lower()

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_with_force_requires_override_reason_when_unmerged(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Even with --force, done transition should require explicit override reason when unmerged."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Create uncommitted file in worktree
        (worktree / "uncommitted.txt").write_text("Uncommitted work\n")

        # Move to done with --force (should still fail without explicit override reason)
        result = runner.invoke(app, ["move-task", "WP01", "--to", "done", "--force", "--json"])

        # Verify failure
        assert result.exit_code == 1
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        assert "done-override-reason" in output["error"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_with_override_reason_succeeds_when_unmerged(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Should allow done transition when unmerged only with explicit override reason."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Worktree already has committed changes (from fixture)
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "done",
                "--done-override-reason",
                "Validated manually in post-merge audit",
                "--json",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["result"] == "success"
        assert output["new_lane"] == "done"

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_for_review_persists_transition_event(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Successful move-task output requires a durable transition event."""
        repo_root, _worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        result = runner.invoke(app, ["move-task", "WP01", "--to", "for_review", "--json"])

        assert result.exit_code == 0, result.stdout
        output = json.loads(result.stdout)
        assert output["result"] == "success"
        assert output["new_lane"] == "for_review"
        assert output["event_id"]
        assert output["work_package_id"] == "WP01"
        assert output["to_lane"] == "for_review"
        assert output["status_events_path"] == str(
            repo_root / "kitty-specs" / "017-test-feature" / "status.events.jsonl"
        )

        events = read_events(repo_root / "kitty-specs" / "017-test-feature")
        assert any(
            event.wp_id == "WP01" and event.to_lane == Lane.FOR_REVIEW
            for event in events
        )

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_for_review_fails_when_event_readback_is_blocked(
        self,
        mock_slug: Mock,
        mock_root: Mock,
        git_repo_with_worktree: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """move-task must fail non-zero if the expected event is not readable."""
        repo_root, _worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        import specify_cli.status.store as status_store

        monkeypatch.setattr(
            status_store,
            "_append_serialized_atomic",
            lambda _feature_dir, _payloads: None,
        )

        result = runner.invoke(app, ["move-task", "WP01", "--to", "for_review", "--json"])

        assert result.exit_code == 1
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert output["diagnostic_code"] == "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED"
        assert output["violated_invariant"] == "STA-002"
        assert output["remediation"]
        assert output["mission_slug"] == "017-test-feature"
        assert output["work_package_id"] == "WP01"
        assert output["wp_id"] == "WP01"
        assert output["to_lane"] == "for_review"
        assert output["status_events_path"] == str(
            repo_root / "kitty-specs" / "017-test-feature" / "status.events.jsonl"
        )
        assert "persistence verification failed" in output["error"]
        assert "mission_slug=017-test-feature" in output["error"]
        assert "wp_id=WP01" in output["error"]
        assert "target_lane=" in output["error"]
        assert "status.events.jsonl" in output["error"]

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_after_branch_merged_succeeds_without_override(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Should allow done transition without override when ancestry is verified."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Merge the lane branch into main while keeping the branch ref so ancestry can be verified.
        subprocess.run(["git", "checkout", "main"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "merge", "--no-ff", lane_branch_name("017-test-feature"), "-m", "Merge lane-a"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(
            app,
            ["move-task", "WP01", "--to", "done", "--force", "--json"],
        )
        assert result.exit_code == 0, result.stdout
        output = json.loads(result.stdout)
        assert output["result"] == "success"
        assert output["new_lane"] == "done"

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_for_review_still_validates(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """With auto-commit OFF, moving to for_review still validates and blocks on
        uncommitted work (#2335: the guard defers to the operator only when
        auto-commit is disabled; with it on, deliverables are committed instead)."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Create uncommitted file in worktree
        (worktree / "uncommitted.txt").write_text("Uncommitted work\n")

        # With --no-auto-commit, the recovery commit is skipped and the guard fires.
        result = runner.invoke(
            app, ["move-task", "WP01", "--to", "for_review", "--no-auto-commit", "--json"]
        )

        # Verify failure (guard still validates when auto-commit is off)
        assert result.exit_code == 1
        # Parse only the first JSON object (CLI may output multiple)
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        assert "uncommitted" in output["error"].lower() or "changes" in output["error"].lower()

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_to_done_with_staged_but_uncommitted_fails(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Should fail when moving to done with staged but uncommitted changes."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # Create and stage a file (but don't commit)
        (worktree / "staged.txt").write_text("Staged but not committed\n")
        subprocess.run(["git", "add", "."], cwd=worktree, check=True, capture_output=True)

        # Try to move to done (should fail)
        result = runner.invoke(app, ["move-task", "WP01", "--to", "done", "--json"])

        # Verify failure
        assert result.exit_code == 1
        # Parse only the first JSON object (CLI may output multiple)
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        assert "uncommitted" in output["error"].lower() or "changes" in output["error"].lower()

    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
    def test_review_validation_allows_behind_status_only_commits(
        self, _mock_mission: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Status-only commits on planning branch should not force rebases."""
        repo_root, worktree = git_repo_with_worktree
        mission_slug = "017-test-feature"

        # Add a status/planning-only commit on main so the worktree is behind.
        wp_file = repo_root / "kitty-specs" / mission_slug / "tasks" / "WP01-test-task.md"
        content = wp_file.read_text(encoding="utf-8")
        wp_file.write_text(content + "\n<!-- status update -->\n", encoding="utf-8")
        subprocess.run(["git", "add", str(wp_file)], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: status-only planning update"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

        is_valid, guidance = _validate_ready_for_review(
            repo_root=worktree,
            mission_slug=mission_slug,
            wp_id="WP01",
            force=False,
        )

        assert is_valid is True
        assert guidance == []

    @patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
    def test_review_validation_allows_behind_config_and_status_commits(
        self, _mock_mission: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        """Config/status-only commits on planning branch should not force rebase."""
        repo_root, worktree = git_repo_with_worktree
        mission_slug = "017-test-feature"

        wp_file = repo_root / "kitty-specs" / mission_slug / "tasks" / "WP01-test-task.md"
        config_file = repo_root / ".kittify" / "config.yaml"

        wp_file.write_text(wp_file.read_text(encoding="utf-8") + "\n<!-- status update -->\n", encoding="utf-8")
        config_file.write_text(config_file.read_text(encoding="utf-8") + "sync: true\n", encoding="utf-8")

        subprocess.run(
            ["git", "add", str(wp_file), str(config_file)],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: status + config planning update"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

        is_valid, guidance = _validate_ready_for_review(
            repo_root=worktree,
            mission_slug=mission_slug,
            wp_id="WP01",
            force=False,
        )

        assert is_valid is True
        assert guidance == []

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_for_review_blocks_when_lane_branch_has_kitty_specs_commits(
        self,
        mock_slug: Mock,
        mock_root: Mock,
        git_repo_with_worktree: tuple[Path, Path],
    ):
        """for_review gate should block lane branches that committed planning artifacts."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        contaminated_file = worktree / "kitty-specs" / "017-test-feature" / "tasks" / "WP01-test-task.md"
        contaminated_file.write_text(
            contaminated_file.read_text(encoding="utf-8") + "\n<!-- accidental edit -->\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", str(contaminated_file)],
            cwd=worktree,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "accidental: planning edit in lane branch"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["move-task", "WP01", "--to", "for_review", "--json"])
        assert result.exit_code == 1
        first_line = result.stdout.strip().split("\n")[0]
        output = json.loads(first_line)
        assert "error" in output
        assert "kitty-specs" in output["error"].lower()

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_move_for_review_from_worktree_keeps_commit_history_unchanged(
        self,
        mock_slug: Mock,
        mock_root: Mock,
        git_repo_with_worktree: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Moving from a lane worktree should not add kitty-specs commits to the lane branch."""
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"
        subprocess.run(
            ["git", "checkout", "-b", "test/status-root", "main"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        monkeypatch.chdir(worktree)

        result = runner.invoke(app, ["move-task", "WP01", "--to", "for_review", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["result"] == "success"
        assert payload["new_lane"] == "for_review"

        root_head_msg = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        wp_head_msg = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        assert "Move WP01 to for_review" not in root_head_msg
        assert "Move WP01 to for_review" not in wp_head_msg
        assert "Add implementation" in wp_head_msg

        main_events = read_events(repo_root / "kitty-specs" / "017-test-feature")
        worktree_events = read_events(worktree / "kitty-specs" / "017-test-feature")
        assert any(event.wp_id == "WP01" and event.to_lane == Lane.FOR_REVIEW for event in main_events)
        assert not any(event.wp_id == "WP01" and event.to_lane == Lane.FOR_REVIEW for event in worktree_events)


class TestMoveTaskCommitsLaneDeliverables:
    """#2335 — move-task --to for_review commits uncommitted lane deliverables
    (killed-implementer recovery) instead of dead-ending on a manual commit."""

    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_for_review_auto_commits_uncommitted_deliverables(
        self, mock_slug: Mock, mock_root: Mock, git_repo_with_worktree: tuple[Path, Path]
    ):
        repo_root, worktree = git_repo_with_worktree
        mock_root.return_value = repo_root
        mock_slug.return_value = "017-test-feature"

        # A killed implementer left a finished deliverable uncommitted in the lane.
        (worktree / "deliverable.py").write_text("print('done')\n")
        assert (
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=True
            ).stdout.strip()
            != ""
        )

        # Recovery: move to for_review WITHOUT --force. Auto-commit is on by default.
        result = runner.invoke(app, ["move-task", "WP01", "--to", "for_review", "--json"])

        assert result.exit_code == 0, result.stdout
        # The deliverable was committed via the tool — worktree is clean, no manual git.
        assert (
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=True
            ).stdout.strip()
            == ""
        )
        # It landed on the lane branch as a real commit.
        head_files = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=worktree, capture_output=True, text=True, check=True,
        ).stdout
        assert "deliverable.py" in head_files
        # And the transition actually happened.
        main_events = read_events(repo_root / "kitty-specs" / "017-test-feature")
        assert any(e.wp_id == "WP01" and e.to_lane == Lane.FOR_REVIEW for e in main_events)


def test_lane_deliverable_paths_takes_status_entries(tmp_path: Path):
    """Typed status entries yield modified/untracked paths and BOTH sides of a rename."""
    from specify_cli.cli.commands.agent.tasks_move_task import _lane_deliverable_paths

    from kernel.git import GitPath, StatusEntry

    entries = [
        StatusEntry(xy=" M", path=GitPath.parse("src/app.py")),  # modified
        StatusEntry(xy="??", path=GitPath.parse("new_file.txt")),  # untracked
        StatusEntry(xy="R ", path=GitPath.parse("new.py"), orig_path=GitPath.parse("old.py")),  # rename
    ]
    paths = _lane_deliverable_paths(tmp_path, entries)
    names = {p.name for p in paths}
    assert names == {"app.py", "new_file.txt", "new.py", "old.py"}
    assert all(p.parent == tmp_path or p.is_relative_to(tmp_path) for p in paths)
