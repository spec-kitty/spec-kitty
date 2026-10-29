"""#6400 (FR-008 / FR-009): mark-status, add-history and action notes write the structured actor.

Every annotation these commands append to ``status.events.jsonl`` carries the 4-key
structured actor ``{tool, role, profile, model}`` (the ``spec_kitty_events`` 11 diary
shape; spec C-006 defers ``profile_source``), never a bare string:

* ``agent tasks mark-status`` -- ``tool="user"`` and ``role="implementer"`` without
  ``--agent``; the new optional ``--agent`` (compact form accepted) names the tool.
* ``agent tasks add-history`` -- ``role`` is ``reviewer`` while the WP is ``in_review``,
  else ``implementer``.
* ``agent action implement`` (resume refresh) and ``agent action review`` (review
  re-claim) -- the same structured actor as their transitions.

Driven through the real commands. The mark-status / add-history cases run on a real
git ``lanes`` mission; the implement / review cases reuse the non-git claim harness of
``test_implement_runtime_frontmatter_claim.py`` (status emission real, git stubbed).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.review.lock import ReviewLock
from specify_cli.status import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _write_wp_and_lanes,
)
from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_CLAIM_SLUG = "structured-actor-6400-demo"


def _actor(tool: str | None, role: str, *, profile: str | None = None, model: str | None = None) -> dict[str, str | None]:
    return {"tool": tool, "role": role, "profile": profile, "model": model}


def _raw_events(feature_dir: Path) -> list[dict[str, Any]]:
    path = feature_dir / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _annotations(feature_dir: Path) -> list[dict[str, Any]]:
    return [event for event in _raw_events(feature_dir) if event.get("kind") == "annotation"]


# ---------------------------------------------------------------------------
# Real git lanes mission (mark-status, add-history).
# ---------------------------------------------------------------------------


@pytest.fixture()
def lanes_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "actor-6400-demo", MissionTopology.LANES)
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    _write_wp_and_lanes(result.feature_dir, result.mission_slug, str(meta["mission_id"]), "main")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed WP01"],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(repo)
    return repo, result.mission_slug, result.feature_dir


def _seed_lane(feature_dir: Path, lane: Lane) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-WP01-{lane}",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=lane,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _mark_status(slug: str, *extra: str) -> Any:
    return runner.invoke(
        root_app,
        ["agent", "tasks", "mark-status", "T001", "--status", "done", "--mission", slug, "--no-auto-commit", *extra],
    )


def _subtask_annotation_actor(feature_dir: Path) -> object:
    marks = [a for a in _annotations(feature_dir) if a["wp_id"] == "WP01" and (a.get("delta") or {}).get("subtasks")]
    assert marks, f"mark-status wrote no subtask annotation: {_annotations(feature_dir)!r}"
    return marks[-1]["actor"]


def test_mark_status_without_agent_records_user_implementer_actor(lanes_mission: tuple[Path, str, Path]) -> None:
    _repo, slug, feature_dir = lanes_mission

    result = _mark_status(slug)

    assert result.exit_code == 0, result.output
    assert _subtask_annotation_actor(feature_dir) == _actor("user", "implementer")


def test_mark_status_agent_names_the_tool(lanes_mission: tuple[Path, str, Path]) -> None:
    _repo, slug, feature_dir = lanes_mission

    result = _mark_status(slug, "--agent", "claude")

    assert result.exit_code == 0, result.output
    assert _subtask_annotation_actor(feature_dir) == _actor("claude", "implementer")


def test_mark_status_accepts_the_compact_agent_form(lanes_mission: tuple[Path, str, Path]) -> None:
    _repo, slug, feature_dir = lanes_mission

    result = _mark_status(slug, "--agent", "claude:opus:python-pedro")

    assert result.exit_code == 0, result.output
    assert _subtask_annotation_actor(feature_dir) == _actor("claude", "implementer", profile="python-pedro", model="opus")


def _note_actor(feature_dir: Path, note: str) -> object:
    notes = [a for a in _annotations(feature_dir) if a["wp_id"] == "WP01" and note in ((a.get("delta") or {}).get("note") or "")]
    assert notes, f"add-history wrote no note annotation: {_annotations(feature_dir)!r}"
    return notes[-1]["actor"]


@pytest.mark.parametrize(
    ("lane", "role"),
    [(Lane.IN_PROGRESS, "implementer"), (Lane.IN_REVIEW, "reviewer")],
)
def test_add_history_records_the_structured_actor_with_the_lane_role(
    lanes_mission: tuple[Path, str, Path],
    lane: Lane,
    role: str,
) -> None:
    _repo, slug, feature_dir = lanes_mission
    _seed_lane(feature_dir, lane)

    result = runner.invoke(
        root_app,
        ["agent", "tasks", "add-history", "WP01", "--note", "NOTE-6400", "--agent", "claude", "--mission", slug, "--json"],
    )

    assert result.exit_code == 0, result.output
    assert _note_actor(feature_dir, "NOTE-6400") == _actor("claude", role)


def test_add_history_explicit_agent_with_an_empty_tool_is_refused_cleanly(lanes_mission: tuple[Path, str, Path]) -> None:
    """An explicit ``--agent`` the compact parser rejects refuses before any write, with mark-status's message."""
    _repo, slug, feature_dir = lanes_mission
    _seed_lane(feature_dir, Lane.IN_PROGRESS)
    before = _raw_events(feature_dir)

    result = runner.invoke(
        root_app,
        ["agent", "tasks", "add-history", "WP01", "--note", "NOTE-6400", "--agent", ":x", "--mission", slug],
    )

    assert result.exit_code == 1, result.output
    assert "Invalid --agent value" in result.output
    assert "Traceback" not in result.output
    assert _raw_events(feature_dir) == before


# ---------------------------------------------------------------------------
# Claim harness (action implement / action review), git stubbed.
# ---------------------------------------------------------------------------


@pytest.fixture()
def claim_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = tmp_path
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "vcs:\n  type: git\nproject:\n  uuid: test-project-uuid\n  slug: test-project\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out",
        lambda repo_root, mission_slug: (repo_root, "main"),
    )
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow.safe_commit", lambda **kwargs: True)
    monkeypatch.setattr(workflow, "_commit_workflow_change", lambda **kwargs: None)
    return repo_root


def _seed_claim_mission(repo_root: Path, lane: Lane) -> Path:
    feature_dir = repo_root / "kitty-specs" / _CLAIM_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    write_frontmatter(
        tasks_dir / "WP01-test.md",
        {
            "work_package_id": "WP01",
            "subtasks": ["T001"],
            "title": "WP01 Test",
            "phase": "Phase 0",
            "execution_mode": "code_change",
            "owned_files": ["src/wp01/**"],
            "authoritative_surface": "src/wp01/",
            "assignee": "",
            "agent": "",
            "shell_pid": "",
            "review_status": "",
            "reviewed_by": "",
            "dependencies": [],
        },
        "# WP01 Prompt\n",
    )
    _seed_lane(feature_dir, lane)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )
    workspace = lane_worktree_path(repo_root, _CLAIM_SLUG)
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = repo_root / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    return feature_dir


def _invoke(command: str, *extra: str) -> Any:
    return runner.invoke(workflow.app, [command, "WP01", "--mission", _CLAIM_SLUG, *extra])


def _assert_structured(events: list[dict[str, Any]], expected: dict[str, str | None]) -> None:
    assert events, "the command appended no status event"
    for event in events:
        assert event["actor"] == expected, f"{event.get('kind', 'transition')} event carries {event['actor']!r}"


@pytest.mark.parametrize("resume_args", [("--agent", "claude"), ()], ids=["with-agent", "bare"])
def test_implement_resume_refresh_carries_the_implementer_actor(claim_repo: Path, resume_args: tuple[str, ...]) -> None:
    feature_dir = _seed_claim_mission(claim_repo, Lane.PLANNED)
    first = _invoke("implement", "--agent", "claude")
    assert first.exit_code == 0, first.stdout
    _assert_structured(_raw_events(feature_dir)[1:], _actor("claude", "implementer"))
    before = len(_raw_events(feature_dir))

    second = _invoke("implement", *resume_args)

    assert second.exit_code == 0, second.stdout
    appended = _raw_events(feature_dir)[before:]
    assert any(event.get("kind") == "annotation" for event in appended), appended
    _assert_structured(appended, _actor("claude", "implementer"))


def test_review_claim_and_reclaim_carry_the_reviewer_actor(claim_repo: Path) -> None:
    feature_dir = _seed_claim_mission(claim_repo, Lane.FOR_REVIEW)
    first = _invoke("review", "--agent", "claude-reviewer")
    assert first.exit_code == 0, first.stdout
    _assert_structured(_raw_events(feature_dir)[1:], _actor("claude-reviewer", "reviewer"))
    before = len(_raw_events(feature_dir))
    # The first review session ends; the re-claim is a fresh session on the same lane.
    ReviewLock.release(lane_worktree_path(claim_repo, _CLAIM_SLUG))

    second = _invoke("review", "--agent", "claude-reviewer")

    assert second.exit_code == 0, second.stdout
    appended = _raw_events(feature_dir)[before:]
    assert any(event.get("kind") == "annotation" for event in appended), appended
    _assert_structured(appended, _actor("claude-reviewer", "reviewer"))
