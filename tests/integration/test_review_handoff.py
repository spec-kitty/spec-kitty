"""Integration tests for external reviewer handoff (WP03).

Tests that:
- _validate_ready_for_review() passes when only benign dirty files are present
- _validate_ready_for_review() blocks when blocking dirty files are present
- --force bypasses all validation
- review() surfaces an in-repo writable feedback path in its output
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review
from specify_cli.status.store import append_event
from specify_cli.status.models import StatusEvent, Lane
from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Shared fixture: minimal git repo + software-dev mission + worktree
# ---------------------------------------------------------------------------

@pytest.fixture
def review_handoff_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """Create a git repo with a mission and a worktree ready for review.

    Returns:
        (repo_root, worktree_path, mission_slug)
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialise git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    # .kittify marker
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("# Config\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    mission_slug = "066-review-handoff-test"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    # WP task file
    task_file = tasks_dir / "WP01-test-handoff.md"
    task_file.write_text(
        "---\nwork_package_id: WP01\ntitle: Test Handoff\nagent: test\nshell_pid: ''\n---\n\n# WP01\n\n## Activity Log\n\n- 2025-01-01T00:00:00Z – system – lane=planned\n",
        encoding="utf-8",
    )

    # Seed status events: planned -> in_progress
    for lane_val in ("planned", "in_progress"):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-WP01-{lane_val}",
                mission_slug=mission_slug,
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
    subprocess.run(["git", "commit", "-m", "Add mission and task"], cwd=repo, check=True, capture_output=True)

    # Create worktree with implementation commit
    worktree_dir = lane_worktree_path(repo, mission_slug)
    subprocess.run(
        ["git", "worktree", "add", "-b", lane_branch_name(mission_slug), str(worktree_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (worktree_dir / "implementation.py").write_text("# Implementation\n")
    subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat(WP01): implement"], cwd=worktree_dir, check=True, capture_output=True)

    return repo, worktree_dir, mission_slug


# ---------------------------------------------------------------------------
# Test 9: Only benign dirty files — validation PASSES
# ---------------------------------------------------------------------------

@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_validate_with_only_benign_dirtiness_passes(
    _mock_mission: Mock,
    review_handoff_repo: tuple[Path, Path, str],
):
    """Benign dirty files (status artifacts, other WPs' task files) must NOT block review."""
    repo_root, worktree, mission_slug = review_handoff_repo
    feature_dir = repo_root / "kitty-specs" / mission_slug

    # Make benign files dirty: status.events.jsonl and another WP's task file
    (feature_dir / "status.events.jsonl").write_text('{"benign": true}\n')
    tasks_dir = feature_dir / "tasks"
    (tasks_dir / "WP02-other-package.md").write_text("---\nwork_package_id: WP02\n---\n# WP02\n")

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
    )

    assert is_valid is True, f"Expected valid but got guidance: {guidance}"
    assert guidance == []


# ---------------------------------------------------------------------------
# Test 10: Blocking dirty files — validation FAILS with guidance
# ---------------------------------------------------------------------------

@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_validate_with_blocking_dirtiness_fails(
    _mock_mission: Mock,
    review_handoff_repo: tuple[Path, Path, str],
):
    """Non-planning source files that are dirty must block review with actionable guidance."""
    repo_root, worktree, mission_slug = review_handoff_repo
    feature_dir = repo_root / "kitty-specs" / mission_slug

    # Make a non-planning file dirty (source code — this IS blocking)
    # WP task files are planning artifacts and benign; use a different file type
    random_file = feature_dir / "some-source-file.py"
    random_file.write_text("# uncommitted source code\n")

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
    )

    assert is_valid is False
    guidance_text = "\n".join(guidance).lower()
    assert "blocking" in guidance_text or "commit" in guidance_text


# ---------------------------------------------------------------------------
# Test 11: --force bypasses all validation
# ---------------------------------------------------------------------------

@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_validate_with_force_bypasses_all(
    _mock_mission: Mock,
    review_handoff_repo: tuple[Path, Path, str],
):
    """--force must return (True, []) unconditionally, regardless of dirty state."""
    repo_root, worktree, mission_slug = review_handoff_repo
    feature_dir = repo_root / "kitty-specs" / mission_slug

    # Make everything dirty — should be ignored with force=True
    (feature_dir / "status.events.jsonl").write_text("dirty\n")
    (feature_dir / "tasks" / "WP01-test-handoff.md").write_text("dirty\n")
    (worktree / "uncommitted.py").write_text("dirty\n")

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=True,
    )

    assert is_valid is True
    assert guidance == []


# ---------------------------------------------------------------------------
# Test 12: Review prompt includes in-repo feedback path
# ---------------------------------------------------------------------------

def test_review_prompt_includes_in_repo_path(
    review_handoff_repo: tuple[Path, Path, str],
):
    """The review prompt must surface a kitty-specs/ in-repo feedback path.

    We call _validate_ready_for_review() and then directly inspect that the
    workflow generates an in-repo path under kitty-specs/.  The path is
    constructed by the workflow.review() function and is testable by examining
    the sub-artifact directory creation logic.

    This test validates T015 by directly exercising the real path-construction
    seam in isolation (the full workflow.review() requires a live git
    event-log with for_review status, making it impractical to call via CLI
    in a simple integration test). #3243: the seam is the shared
    ``next_review_feedback_source_path`` derivation — the same max+1 cycle
    numbering the rejection writer allocates with — so what is asserted here
    is the production derivation, not a re-implementation of it (the former
    inline ``len(glob(...)) + 1`` simulation had drifted from production and
    kept passing while asserting stale logic).
    """
    from specify_cli.review.cycle import next_review_feedback_source_path

    repo_root, worktree, mission_slug = review_handoff_repo
    wp_slug = "WP01-test-handoff"

    # The sub-artifact dir workflow.review() resolves (PRIMARY partition):
    # sub_artifact_dir = main_repo_root / "kitty-specs" / mission_slug / "tasks" / wp_slug
    sub_artifact_dir = repo_root / "kitty-specs" / mission_slug / "tasks" / wp_slug
    sub_artifact_dir.mkdir(parents=True, exist_ok=True)

    review_feedback_path = next_review_feedback_source_path(sub_artifact_dir)

    # Assertions
    # 1. The path is within kitty-specs/ (in-repo, not /tmp)
    assert "kitty-specs" in str(review_feedback_path)
    assert str(review_feedback_path).startswith(str(repo_root))

    # 2. The path uses the WP slug (kebab-case), not just the WP ID
    assert wp_slug in str(review_feedback_path)

    # 3. The path follows review-feedback-N.md naming — the reviewer-authored
    # feedback filename, deliberately NOT the tool-authored review-cycle-N.md
    # (#3430: advertising review-cycle-N.md printed a rejection command the
    # provenance guard refuses).
    assert review_feedback_path.name == "review-feedback-1.md"

    # 4. Next cycle increments when a prior review cycle artifact exists —
    # numbered by max+1, so the advertised number always matches the number
    # the rejection writer will allocate (#3243).
    (sub_artifact_dir / "review-cycle-1.md").write_text("# Cycle 1 feedback\n")
    assert (
        next_review_feedback_source_path(sub_artifact_dir).name
        == "review-feedback-2.md"
    )

    # 5. The path is under kitty-specs/, not a standalone temp file
    # (On CI, repo_root itself may be under /tmp, so we check the relative structure)
    relative = str(review_feedback_path.relative_to(repo_root))
    assert relative.startswith("kitty-specs/")
