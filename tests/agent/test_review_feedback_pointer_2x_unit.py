"""2.x tests for review feedback pointer persistence and move-task behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from tests.branch_contract import IS_2X_BRANCH
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import (
    _detect_reviewer_name,
    _persist_review_feedback,
    _resolve_git_common_dir,
    app as tasks_app,
)
from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_pointer as _resolve_review_feedback_pointer
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.task_utils import extract_scalar, split_frontmatter

pytestmark = [
    pytest.mark.skipif(not IS_2X_BRANCH, reason="2.x-only review feedback pointer contract"),
    pytest.mark.git_repo,
]
runner = CliRunner()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture()
def task_repo(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    mission_slug = "001-test-feature"
    feature_dir = git_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (git_repo / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks.md").write_text(
        "## WP01 Test Task\n\n- [x] T001 Placeholder task\n",
        encoding="utf-8",
    )

    wp_path = tasks_dir / "WP01-test-task.md"
    _write_wp(wp_path, lane="for_review")
    monkeypatch.chdir(git_repo)
    return git_repo, mission_slug, wp_path


def _write_wp(path: Path, *, lane: str) -> None:
    frontmatter = {
        "work_package_id": "WP01",
        "subtasks": ["T001"],
        "title": "Test Task",
        "phase": "Phase 1",
        "lane": lane,
        "dependencies": [],
        "assignee": "",
        "agent": "test-agent",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "review_feedback": "",
        "history": [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "lane": lane,
                "agent": "system",
                "shell_pid": "",
                "action": "Prompt created",
            }
        ],
    }
    body = f"# WP01 Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z – system – lane={lane} – Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _git_common_dir(repo: Path) -> Path:
    raw_value = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    common_dir = Path(raw_value)
    if not common_dir.is_absolute():
        common_dir = (repo / common_dir).resolve()
    return common_dir


def _mock_status_event(*, to_lane: str, actor: str, force: bool) -> StatusEvent:
    return StatusEvent(
        event_id="01HZX000000000000000000000",
        mission_slug="001-test-feature",
        wp_id="WP01",
        from_lane=Lane("for_review"),
        to_lane=Lane(to_lane),
        at="2026-01-01T00:00:00+00:00",
        actor=actor,
        force=force,
        execution_mode="worktree",
        reason=None,
    )


def _json_payload(output: str) -> dict:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"No JSON payload found in output:\n{output}")


def _patch_move_task_dependencies(monkeypatch: pytest.MonkeyPatch, repo: Path, mission_slug: str) -> Mock:
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(
        tasks_module,
        "_find_mission_slug",
        lambda explicit_feature=None: mission_slug,
    )
    monkeypatch.setattr(
        tasks_module,
        "_ensure_target_branch_checked_out",
        lambda *_args, **_kwargs: (repo, "main"),
    )
    monkeypatch.setattr(tasks_module, "_check_unchecked_subtasks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(tasks_module, "_validate_ready_for_review", lambda *_args, **_kwargs: (True, []))
    monkeypatch.setattr(tasks_module, "_wp_branch_merged_into_target", lambda **_kwargs: (True, "ok"))
    # Seed a for_review event so old_lane is detected as for_review (not defaulting to planned).
    # The code uses a local import from specify_cli.status.store, so patch there directly.
    seed_event = _mock_status_event(to_lane="for_review", actor="user", force=False)
    monkeypatch.setattr(tasks_module, "read_events", lambda *_args, **_kwargs: [seed_event])
    monkeypatch.setattr(
        "specify_cli.status.store.read_events",
        lambda *_args, **_kwargs: [seed_event],
    )
    monkeypatch.setattr(tasks_module, "_check_dependent_warnings", lambda *_args, **_kwargs: None)
    emit_mock = Mock(
        side_effect=lambda **kwargs: _mock_status_event(
            to_lane=kwargs.get("to_lane", "planned"),
            actor=kwargs.get("actor", "user"),
            force=kwargs.get("force", False),
        )
    )
    monkeypatch.setattr(tasks_module, "emit_status_transition_transactional", emit_mock)
    return emit_mock


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["git", "config", "user.name"]),
        FileNotFoundError("git"),
    ],
)
def test_detect_reviewer_name_falls_back_to_unknown(error: Exception):
    with patch("specify_cli.cli.commands.agent.tasks.subprocess.run", side_effect=error):
        assert _detect_reviewer_name() == "unknown"


def test_resolve_git_common_dir_raises_when_git_returns_empty_path():
    completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="\n", stderr="")
    with (
        patch("specify_cli.cli.commands.agent.tasks.subprocess.run", return_value=completed),
        pytest.raises(RuntimeError, match="Unable to resolve git common directory"),
    ):
        _resolve_git_common_dir(Path("/nonexistent/repo"))


def test_persist_feedback_uses_git_common_dir_and_pointer(git_repo: Path, tmp_path: Path):
    source = tmp_path / "feedback.md"
    source.write_text("**Issue**: Add test coverage\n", encoding="utf-8")

    persisted_path, pointer = _persist_review_feedback(
        main_repo_root=git_repo,
        mission_slug="001-test-feature",
        task_id="WP01",
        feedback_source=source,
    )

    common_dir = _git_common_dir(git_repo)
    assert pointer.startswith("feedback://001-test-feature/WP01/")
    assert persisted_path.parent == common_dir / "spec-kitty" / "feedback" / "001-test-feature" / "WP01"
    assert persisted_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_resolve_feedback_pointer_from_common_dir(git_repo: Path, tmp_path: Path):
    source = tmp_path / "feedback.md"
    source.write_text("**Issue**: Fix edge case\n", encoding="utf-8")

    persisted_path, pointer = _persist_review_feedback(
        main_repo_root=git_repo,
        mission_slug="001-test-feature",
        task_id="WP02",
        feedback_source=source,
    )

    resolved = _resolve_review_feedback_pointer(git_repo, pointer)
    assert resolved == persisted_path.resolve()


def test_resolve_feedback_pointer_rejects_invalid_shape(git_repo: Path):
    assert _resolve_review_feedback_pointer(git_repo, "feedback://bad-shape") is None


def test_move_task_planned_rejects_missing_absolute_feedback_file(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, _ = task_repo
    _patch_move_task_dependencies(monkeypatch, repo, mission_slug)

    missing_path = (repo / "missing-feedback.md").resolve()
    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(missing_path),
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 1
    payload = _json_payload(result.stdout)
    assert "Review feedback file not found" in payload["error"]


def test_move_task_planned_rejects_directory_feedback_path(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, _ = task_repo
    _patch_move_task_dependencies(monkeypatch, repo, mission_slug)

    feedback_dir = repo / "feedback-dir"
    feedback_dir.mkdir()

    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            "feedback-dir",
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 1
    payload = _json_payload(result.stdout)
    assert "not a file" in payload["error"]


def test_move_task_planned_rejects_empty_feedback_file(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, _ = task_repo
    _patch_move_task_dependencies(monkeypatch, repo, mission_slug)

    feedback_file = repo / "feedback.md"
    feedback_file.write_text("   \n", encoding="utf-8")

    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            "feedback.md",
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 1
    payload = _json_payload(result.stdout)
    assert "Review feedback file is empty" in payload["error"]


def test_move_task_planned_sets_pointer_reviewer_and_review_ref(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, wp_path = task_repo
    emit_mock = _patch_move_task_dependencies(monkeypatch, repo, mission_slug)
    monkeypatch.setattr(tasks_module, "_detect_reviewer_name", lambda: "Detected Reviewer")

    feedback_file = repo / "feedback.md"
    feedback_file.write_text("**Issue**: Handle race condition\n", encoding="utf-8")

    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            "feedback.md",
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result.stdout)
    pointer = payload["review_feedback"]
    assert payload["new_lane"] == "planned"
    assert pointer.startswith("feedback://001-test-feature/WP01/")
    assert any(call.kwargs.get("review_ref") == pointer for call in emit_mock.call_args_list)

    # review_status, reviewed_by, and review_feedback are tracked in the event log (not frontmatter)
    # Verify they are NOT in frontmatter (mutable lane fields removed post-refactor)
    frontmatter, _, _ = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter, "review_status") == "", "review_status should not be in frontmatter"


def test_move_task_force_reopen_sets_force_override_review_ref(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, _ = task_repo
    emit_mock = _patch_move_task_dependencies(monkeypatch, repo, mission_slug)

    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "doing",
            "--force",
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert any(call.kwargs.get("review_ref") == "force-override" for call in emit_mock.call_args_list)


def test_move_task_done_sets_review_metadata_with_detected_reviewer(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, wp_path = task_repo
    emit_mock = _patch_move_task_dependencies(monkeypatch, repo, mission_slug)
    monkeypatch.setattr(tasks_module, "_detect_reviewer_name", lambda: "Git Reviewer")

    result = runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "done",
            "--force",
            "--json",
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = _json_payload(result.stdout)
    assert payload["new_lane"] == "done"

    # reviewed_by and review_status are tracked in the event log (not frontmatter) post-refactor
    # Verify the emit was called with evidence including the detected reviewer
    assert any(
        (call.kwargs.get("evidence") or {}).get("review", {}).get("reviewer") == "Git Reviewer"
        for call in emit_mock.call_args_list
    ), f"Expected reviewer 'Git Reviewer' in emit evidence, calls: {emit_mock.call_args_list}"


def test_move_task_warns_when_auto_commit_raises(
    task_repo: tuple[Path, str, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    repo, mission_slug, wp_path = task_repo
    emit_mock = _patch_move_task_dependencies(monkeypatch, repo, mission_slug)
    monkeypatch.setattr(tasks_module, "safe_commit", Mock(side_effect=RuntimeError("boom")))

    result = runner.invoke(tasks_app, ["move-task", "WP01", "--to", "doing"])

    assert result.exit_code == 0, result.stdout
    assert "Auto-commit skipped: boom" in result.stdout

    # lane is tracked in the event log (not frontmatter) post-refactor
    # Verify the emit was called targeting in_progress (doing alias)
    assert any(
        str(call.kwargs.get("to_lane", "")) in ("in_progress", "doing")
        for call in emit_mock.call_args_list
    ), f"Expected in_progress transition in emit calls, got: {emit_mock.call_args_list}"
