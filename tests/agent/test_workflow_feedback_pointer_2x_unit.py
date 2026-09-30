"""2.x tests for workflow implement review feedback pointer guidance."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.branch_contract import IS_2X_BRANCH
from specify_cli.cli.commands.agent import workflow, workflow_cores
from specify_cli.frontmatter import write_frontmatter
from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [
    pytest.mark.skipif(not IS_2X_BRANCH, reason="2.x-only review feedback pointer contract"),
    pytest.mark.git_repo,
]


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


def _prompt_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            return Path(stripped[4:].strip())
    raise AssertionError(f"Prompt path not found in output: {output}")


def _wp_path(repo: Path) -> Path:
    return repo / "kitty-specs" / "001-test-feature" / "tasks" / "WP01-test-task.md"


def _write_wp(
    wp_path: Path,
    *,
    lane: str,
    review_status: str,
    review_feedback: str,
    reviewed_by: str = "reviewer",
) -> None:
    wp_frontmatter = {
        "work_package_id": "WP01",
        "subtasks": ["T001"],
        "title": "Test Task",
        "phase": "Phase 1",
        "lane": lane,
        "dependencies": [],
        "assignee": "",
        "agent": "test-agent",
        "shell_pid": "",
        "review_status": review_status,
        "reviewed_by": reviewed_by,
        "review_feedback": review_feedback,
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
    wp_body = f"# WP01 Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z – system – lane={lane} – Prompt created.\n"
    write_frontmatter(wp_path, wp_frontmatter, wp_body)


def _append_event(
    feature_dir: Path,
    *,
    event_id: str,
    from_lane: Lane,
    to_lane: Lane,
    review_ref: str | None = None,
) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug="001-test-feature",
            wp_id="WP01",
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-01-01T00:00:00Z",
            actor="tester",
            force=False,
            execution_mode="worktree",
            review_ref=review_ref,
        ),
    )


@pytest.fixture()
def workflow_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)

    (repo / ".kittify").mkdir()

    mission_slug = "001-test-feature"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")

    feedback_rel = "001-test-feature/WP01/20260227T120000Z-ab12cd34.md"
    feedback_pointer = f"feedback://{feedback_rel}"
    feedback_file = _git_common_dir(repo) / "spec-kitty" / "feedback" / feedback_rel
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text("**Issue**: Fix retry handling\n", encoding="utf-8")

    _write_wp(
        _wp_path(repo),
        lane="in_progress",
        review_status="has_feedback",
        review_feedback=feedback_pointer,
    )

    workspace = repo / ".worktrees" / f"{mission_slug}-lane-a"
    workspace.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed workflow fixture"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    return repo, feedback_pointer, feedback_file


def test_implement_prompt_uses_feedback_pointer(workflow_repo: tuple[Path, str, Path]):
    repo, feedback_pointer, feedback_file = workflow_repo
    runner = CliRunner()

    result = runner.invoke(
        workflow.app,
        ["implement", "WP01", "--feature", "001-test-feature", "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    assert f"Has review feedback - read reference: {feedback_pointer}" in result.stdout

    prompt_file = _prompt_path_from_output(result.stdout)
    assert prompt_file.exists(), f"Prompt file not found: {prompt_file}"
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert f"Canonical feedback reference: {feedback_pointer}" in prompt_content
    assert f'Read it first: cat "{feedback_file}"' in prompt_content
    assert "📚 SHARED FEATURE ARTIFACTS:" in prompt_content
    assert f"Spec, plan, tasks, and status live in main repo: {repo}/kitty-specs/001-test-feature/" in prompt_content
    assert "Use this lane workspace for code/tests; do not expect shared feature artifacts here" in prompt_content


def test_resolve_feedback_pointer_handles_blank_and_legacy_missing(tmp_path: Path):
    # coord-commit-integrity WP01/T002: the dead triplicate
    # ``workflow._resolve_git_common_dir`` (zero production callers — the real
    # helper lives in ``tasks_shared.py`` with its own tests) was deleted with
    # its two subprocess-error tests. ``_resolve_review_feedback_pointer`` never
    # called it, so the former ``patch.object(workflow, "_resolve_git_common_dir")``
    # was decorative; the feedback:// case still resolves to None on a repo
    # without the artifact.
    repo = tmp_path / "repo"
    repo.mkdir()

    assert workflow_cores.resolve_review_feedback_pointer(repo, "   ") is None

    assert (
        workflow_cores.resolve_review_feedback_pointer(
            repo,
            "feedback://001-test-feature/WP01/file.md",
        )
        is None
    )

    assert workflow_cores.resolve_review_feedback_pointer(repo, "relative/path/that/does-not-exist.md") is None


def test_implement_prompt_warns_when_feedback_pointer_artifact_is_missing(workflow_repo: tuple[Path, str, Path]):
    repo, feedback_pointer, feedback_file = workflow_repo
    _write_wp(
        _wp_path(repo),
        lane="doing",
        review_status="has_feedback",
        review_feedback=feedback_pointer,
    )
    feedback_file.unlink()

    runner = CliRunner()
    result = runner.invoke(workflow.app, ["implement", "WP01", "--feature", "001-test-feature", "--agent", "test-agent"])

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "WARNING: review feedback reference is set, but the artifact is missing/unreadable." in prompt_content
    assert "Ask reviewer to re-run move-task with --review-feedback-file." in prompt_content


def test_implement_prompt_warns_when_review_status_has_feedback_without_reference(
    workflow_repo: tuple[Path, str, Path],
):
    repo, _feedback_pointer, _feedback_file = workflow_repo
    _write_wp(
        _wp_path(repo),
        lane="doing",
        review_status="has_feedback",
        review_feedback="",
    )

    runner = CliRunner()
    result = runner.invoke(workflow.app, ["implement", "WP01", "--feature", "001-test-feature", "--agent", "test-agent"])

    assert result.exit_code == 0, result.stdout
    assert "Has review feedback - but no review_feedback reference is set" in result.stdout

    prompt_file = _prompt_path_from_output(result.stdout)
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "WARNING: review_status=has_feedback but no review_feedback reference is set." in prompt_content
    assert "Ask reviewer to re-run move-task with --review-feedback-file." in prompt_content


def test_implement_fix_cycle_prefers_review_cycle_artifact_over_review_claim_token(
    workflow_repo: tuple[Path, str, Path],
):
    repo, _feedback_pointer, _feedback_file = workflow_repo
    feature_dir = repo / "kitty-specs" / "001-test-feature"
    review_cycle_dir = feature_dir / "tasks" / "WP01-test-task"
    review_cycle_path = review_cycle_dir / "review-cycle-2.md"
    review_cycle_ref = "review-cycle://001-test-feature/WP01-test-task/review-cycle-2.md"
    ReviewCycleArtifact(
        cycle_number=2,
        wp_id="WP01",
        mission_slug="001-test-feature",
        reviewer_agent="codex",
        reviewed_at="2026-04-10T06:36:14Z",
        affected_files=[AffectedFile(path="apps/cli_auth/views_authorization.py", line_range="51-88")],
        reproduction_command="pytest tests/agent -q",
        body="**Issue 1**: Persist the validated GET request server-side.\n",
    ).write(review_cycle_path)

    _append_event(feature_dir, event_id="01AAA000000000000000000001", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED)
    _append_event(feature_dir, event_id="01AAA000000000000000000002", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS)
    _append_event(feature_dir, event_id="01AAA000000000000000000003", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW)
    _append_event(
        feature_dir,
        event_id="01AAA000000000000000000004",
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.IN_PROGRESS,
        review_ref="action-review-claim",
    )
    _append_event(
        feature_dir,
        event_id="01AAA000000000000000000005",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.PLANNED,
        review_ref=review_cycle_ref,
    )

    runner = CliRunner()
    result = runner.invoke(
        workflow.app,
        ["implement", "WP01", "--feature", "001-test-feature", "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    assert "Fix mode" in result.stdout
    assert "Cycle 2" in result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "## Review Findings" in prompt_content
    assert "Persist the validated GET request server-side." in prompt_content
    assert "action-review-claim" not in prompt_content


def test_review_prompt_mentions_shared_git_common_dir_feedback_storage(workflow_repo: tuple[Path, str, Path]):
    import json as _json

    repo, feedback_pointer, _feedback_file = workflow_repo
    _write_wp(
        _wp_path(repo),
        lane="for_review",
        review_status="has_feedback",
        review_feedback=feedback_pointer,
    )

    # Seed event log so review command can read lane=for_review from canonical source
    mission_slug = "001-test-feature"
    events_file = repo / "kitty-specs" / mission_slug / "status.events.jsonl"
    _seed_event = {
        "actor": "test-agent",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01JTEST00000000000000000002",
        "evidence": None,
        "execution_mode": "direct_repo",
        "mission_slug": mission_slug,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": "for_review",
        "wp_id": "WP01",
    }
    events_file.write_text(_json.dumps(_seed_event, sort_keys=True) + "\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(workflow.app, ["review", "WP01", "--feature", "001-test-feature", "--agent", "reviewer"])

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert (
        "move-task stores feedback in shared git common-dir and writes frontmatter review_feedback pointer"
        in prompt_content
    )
    assert "📚 SHARED FEATURE ARTIFACTS:" in prompt_content
    assert f"Spec, plan, tasks, and status live in main repo: {repo}/kitty-specs/001-test-feature/" in prompt_content
    assert "Use this lane workspace for code/tests; do not expect shared feature artifacts here" in prompt_content
