"""Regression tests for workflow review lane gating and implement prompt content."""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.coordination.types import CommitReceipt
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.lifecycle_sync import LaneAutoRebaseSyncError
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.store import append_event
from specify_cli.status.models import StatusEvent, Lane, TransitionRequest
from specify_cli.task_utils import extract_scalar, split_frontmatter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a WP into a specific lane in the event log."""
    _lane_alias = {"doing": "in_progress"}
    canonical_lane = _lane_alias.get(lane, lane)
    event = StatusEvent(
        event_id=f"test-{wp_id}-{canonical_lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(canonical_lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _write_wp_file(path: Path, wp_id: str, lane: str) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": ["T001"],
        "title": f"{wp_id} Test",
        "phase": "Phase 0",
        "lane": lane,
        "assignee": "",
        "agent": "",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "dependencies": [],
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
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z – system – lane={lane} – Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _write_current_analysis_report(feature_dir: Path, repo_root: Path) -> None:
    """Seed the analyze precondition required before implement."""
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "## WP01 Test\n\n- [x] T001 Placeholder task\n",
        encoding="utf-8",
    )
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _prompt_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            return Path(stripped[4:].strip())
    raise AssertionError(f"Prompt path not found in output: {output}")


def _mark_fake_worktree(path: Path) -> None:
    """Create the minimal marker required by workspace-resolution guards."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").write_text("gitdir: ../fake\n", encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    """Run a git subcommand in *repo_root*, raising on failure."""
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def workflow_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow.safe_commit",
        lambda **kwargs: True,
    )
    return repo_root


def test_workflow_review_rejects_planned_lane(workflow_repo: Path) -> None:
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane="planned")
    # Seed event log with planned lane so review command finds canonical state
    _seed_wp_lane(feature_dir, "WP01", "planned")

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 1
    assert "not 'for_review'" in result.stdout
    frontmatter, _, _ = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter, "lane") == "planned"


@pytest.mark.parametrize("command", ["implement", "review"])
def test_workflow_commands_do_not_print_spurious_error_for_handled_exit(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow.locate_project_root", lambda: None)

    result = CliRunner().invoke(
        workflow.app,
        [command, "WP01", "--mission", "001-test-feature", "--agent", "test-agent"],
    )

    assert result.exit_code == 1
    assert "Error: Could not locate project root" in result.stdout
    assert "Error: 1" not in result.stdout


def test_workflow_review_accepts_for_review_lane(workflow_repo: Path) -> None:
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane="for_review")
    # Seed event log with for_review lane so review command finds canonical state
    _seed_wp_lane(feature_dir, "WP01", "for_review")
    _mark_fake_worktree(lane_worktree_path(workflow_repo, mission_slug))

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 0
    # Lane is event-log-only; verify canonical state via event log
    from specify_cli.status.store import read_events
    from specify_cli.status.reducer import reduce
    events = read_events(feature_dir)
    snapshot = reduce(events)
    wp_state = snapshot.work_packages.get("WP01", {})
    assert wp_state.get("lane") in ("in_progress", "doing", "in_review"), f"Expected in_progress or in_review lane, got: {wp_state.get('lane')}"


def test_workflow_implement_moves_planned_to_doing(workflow_repo: Path) -> None:
    """Implement command should transition a planned WP to doing lane.

    Extracted from tests/legacy/specify_cli/test_workflow_auto_moves.py.
    """
    # Arrange
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane="planned")
    # Seed canonical state so implement doesn't hard-fail (no frontmatter fallback)
    _seed_wp_lane(feature_dir, "WP01", "planned")

    # Pre-create workspace so implement skips worktree creation (which needs real git)
    workspace = lane_worktree_path(workflow_repo, mission_slug)
    _mark_fake_worktree(workspace)

    # Assumption check
    frontmatter_before, _, _ = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter_before, "lane") == "planned"

    # Act
    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    from specify_cli.status import read_event_stream, reduce

    stream = read_event_stream(feature_dir)
    snapshot = reduce(stream.transitions, stream.annotations)
    assert snapshot.work_packages["WP01"]["agent"] == "test-agent"
    assert extract_scalar(
        split_frontmatter(wp_path.read_text(encoding="utf-8"))[0], "agent"
    ) == ""


def test_workflow_implement_reads_canonical_status_from_main_when_run_in_sparse_lane(
    workflow_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Implement from a sparse lane must not read lane-local status events."""
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    main_wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(main_wp_path, "WP01", lane="planned")
    _seed_wp_lane(feature_dir, "WP01", "planned")

    workspace = lane_worktree_path(workflow_repo, mission_slug)
    _mark_fake_worktree(workspace)
    workspace_tasks_dir = workspace / "kitty-specs" / mission_slug / "tasks"
    workspace_tasks_dir.mkdir(parents=True)
    workspace_wp_path = workspace_tasks_dir / "WP01-test.md"
    _write_wp_file(workspace_wp_path, "WP01", lane="planned")
    assert not (workspace / "kitty-specs" / mission_slug / "status.events.jsonl").exists()

    monkeypatch.setattr(workflow, "locate_project_root", lambda: workspace)
    monkeypatch.setattr(workflow, "get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr(
        workflow,
        "_ensure_target_branch_checked_out",
        lambda _repo_root, _mission_slug: (workflow_repo, "main"),
    )

    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    from specify_cli.status import read_event_stream, reduce

    stream = read_event_stream(feature_dir)
    snapshot = reduce(stream.transitions, stream.annotations)
    assert snapshot.work_packages["WP01"]["agent"] == "test-agent"
    assert extract_scalar(
        split_frontmatter(main_wp_path.read_text(encoding="utf-8"))[0], "agent"
    ) == ""


def test_workflow_implement_uses_main_current_lane_for_rework_from_sparse_lane(
    workflow_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rework eligibility must use canonical main state, not sparse lane state."""
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    main_wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(main_wp_path, "WP01", lane="for_review")
    _seed_wp_lane(feature_dir, "WP01", "for_review")

    workspace = lane_worktree_path(workflow_repo, mission_slug)
    _mark_fake_worktree(workspace)
    workspace_tasks_dir = workspace / "kitty-specs" / mission_slug / "tasks"
    workspace_tasks_dir.mkdir(parents=True)
    workspace_wp_path = workspace_tasks_dir / "WP01-test.md"
    _write_wp_file(workspace_wp_path, "WP01", lane="planned")
    assert not (workspace / "kitty-specs" / mission_slug / "status.events.jsonl").exists()

    monkeypatch.setattr(workflow, "locate_project_root", lambda: workspace)
    monkeypatch.setattr(workflow, "get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr(
        workflow,
        "_ensure_target_branch_checked_out",
        lambda _repo_root, _mission_slug: (workflow_repo, "main"),
    )

    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    snapshot = reduce(read_events(feature_dir))
    assert snapshot.work_packages["WP01"]["lane"] == Lane.IN_PROGRESS


def test_workflow_implement_emits_rework_to_coord_status_path(
    workflow_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modern missions must read and write the same coord canonical status path."""
    mission_slug = "demo-feature-01J6XW9K"
    mid8 = "01J6XW9K"
    mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
    coord_branch = f"kitty/mission-{mission_slug}"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_id": mission_id,
                "mid8": mid8,
                "coordination_branch": coord_branch,
            }
        ),
        encoding="utf-8",
    )
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    _write_wp_file(tasks_dir / "WP01-test.md", "WP01", lane="for_review")
    # Primary canonical state stays at ``planned`` — proving the rework write lands
    # on the coord path, not primary.
    _seed_wp_lane(feature_dir, "WP01", "planned")

    # The fail-loud coord-write policy (``FallbackCoordWorktreeUnresolved`` /
    # ``_resolve_fallback_coord_worktree``) refuses to degrade a stored-COORD write
    # to a primary-uncommitted write, so the coord worktree must be a REAL,
    # materializable git worktree. Turn the fixture repo into a real git repo,
    # branch the coord ref off the seeded scaffold, and materialize the coord
    # worktree through the SAME production authority the code uses
    # (``CoordinationWorkspace.resolve``) — mirroring the canonical
    # ``_build_mission_repo(coord=True, materialize_coord=True)`` pattern.
    _git(workflow_repo, "init", "-q", "-b", "main")
    _git(workflow_repo, "config", "user.email", "workflow-lane-gate@example.invalid")
    _git(workflow_repo, "config", "user.name", "Workflow Lane Gate")
    _git(workflow_repo, "config", "commit.gpgsign", "false")
    _git(workflow_repo, "add", "-A")
    _git(workflow_repo, "commit", "-q", "-m", "seed mission scaffold")
    _git(workflow_repo, "branch", coord_branch)

    coord_worktree = CoordinationWorkspace.resolve(workflow_repo, mission_slug, mid8)
    coord_feature_dir = coord_worktree / "kitty-specs" / mission_slug
    # Diverge the coord canonical state to ``for_review`` and commit it on the coord
    # branch, so ``implement`` reads (and reworks) the coord status path.
    (coord_feature_dir / "status.events.jsonl").unlink(missing_ok=True)
    _seed_wp_lane(coord_feature_dir, "WP01", "for_review")
    _git(coord_worktree, "add", "-A")
    _git(coord_worktree, "commit", "-q", "-m", "coord: WP01 for_review")

    workspace = lane_worktree_path(workflow_repo, mission_slug)
    _mark_fake_worktree(workspace)
    (workspace / "kitty-specs" / mission_slug / "tasks").mkdir(parents=True)

    monkeypatch.setattr(workflow, "locate_project_root", lambda: workspace)
    monkeypatch.setattr(workflow, "get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", lambda _repo_root: workflow_repo)
    monkeypatch.setattr(
        workflow,
        "_ensure_target_branch_checked_out",
        lambda _repo_root, _mission_slug: (workflow_repo, "main"),
    )
    monkeypatch.setattr(workflow, "_commit_workflow_change", lambda **_kwargs: None)

    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout

    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    coord_events = [event for event in read_events(coord_feature_dir) if event.wp_id == "WP01"]
    assert coord_events[-1].from_lane == Lane.FOR_REVIEW
    assert coord_events[-1].to_lane == Lane.IN_PROGRESS
    assert coord_events[-1].force is True

    primary_snapshot = reduce(read_events(feature_dir))
    assert primary_snapshot.work_packages["WP01"]["lane"] == Lane.PLANNED


def test_commit_workflow_change_syncs_lane_after_coord_commit(
    workflow_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow._reset_workflow_receipts()
    mission_slug = "demo-feature-01J6XW9K"
    mid8 = "01J6XW9K"
    mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
    coord_branch = f"kitty/mission-{mission_slug}"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_id": mission_id,
                "mid8": mid8,
                "coordination_branch": coord_branch,
            }
        ),
        encoding="utf-8",
    )
    event_path = feature_dir / "status.events.jsonl"
    event_path.write_text("", encoding="utf-8")

    calls: list[str] = []

    def fake_commit(**_kwargs: object) -> None:
        calls.append("commit")

    def fake_sync(**kwargs: object) -> None:
        calls.append("sync")
        assert kwargs["coord_branch"] == coord_branch
        assert kwargs["wp_id"] == "WP01"

    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", fake_commit)
    monkeypatch.setattr(workflow, "_sync_lane_after_coordination_commit", fake_sync)

    workflow._commit_workflow_change(
        repo_root=workflow_repo,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        target_branch="main",
        paths=[event_path],
        message="chore: Start WP01 implementation [agent]",
        operation="planned -> claimed for WP01",
        wp_id="WP01",
        pre_emit_event_size=0,
        pre_emit_status_bytes=None,
        auto_rebase_lane_after_commit=True,
    )

    assert calls == ["commit", "sync"]


def test_commit_workflow_change_reverts_coord_commit_on_lane_sync_refusal(
    workflow_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow._reset_workflow_receipts()
    mission_slug = "demo-feature-01J6XW9K"
    mid8 = "01J6XW9K"
    mission_id = "01J6XW9KABCDEFGHJKMNPQRSTV"
    coord_branch = f"kitty/mission-{mission_slug}"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_id": mission_id,
                "mid8": mid8,
                "coordination_branch": coord_branch,
            }
        ),
        encoding="utf-8",
    )
    event_path = feature_dir / "status.events.jsonl"
    event_path.write_text("before\n", encoding="utf-8")
    status_path = feature_dir / "status.json"
    status_path.write_text('{"lane":"planned"}\n', encoding="utf-8")
    receipt = CommitReceipt(
        commit_sha="abc123",
        committed_at=now_utc(),
        destination_ref=coord_branch,
        worktree_root=workflow_repo / ".worktrees" / f"{mission_slug}-{mid8}-coord",
        event_ids=("evt-1",),
    )
    calls: list[str] = []

    def fake_commit(**_kwargs: object) -> CommitReceipt:
        calls.append("commit")
        event_path.write_text("before\nafter\n", encoding="utf-8")
        status_path.write_text('{"lane":"claimed"}\n', encoding="utf-8")
        workflow._record_receipt(
            coord_branch,
            "chore: Start WP01 implementation [agent]",
            "committed",
            sha=receipt.commit_sha,
            wp_id="WP01",
        )
        return receipt

    def fake_sync(**_kwargs: object) -> None:
        calls.append("sync")
        raise LaneAutoRebaseSyncError(
            lane_id="lane-a",
            lane_branch=f"{coord_branch}-lane-a",
            lane_worktree_path=workflow_repo / ".worktrees" / f"{mission_slug}-lane-a",
            coordination_branch=coord_branch,
            coordination_head=receipt.commit_sha,
            halt_reason="manual conflict",
        )

    def fake_revert(actual_receipt: CommitReceipt) -> None:
        calls.append("revert")
        assert actual_receipt is receipt

    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", fake_commit)
    monkeypatch.setattr(workflow, "_sync_lane_after_coordination_commit", fake_sync)
    monkeypatch.setattr(workflow, "_revert_coordination_commit", fake_revert)

    with pytest.raises(typer.Exit):
        workflow._commit_workflow_change(
            repo_root=workflow_repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            target_branch="main",
            paths=[event_path],
            message="chore: Start WP01 implementation [agent]",
            operation="planned -> claimed for WP01",
            wp_id="WP01",
            pre_emit_event_size=len("before\n"),
            pre_emit_status_bytes=b'{"lane":"planned"}\n',
            auto_rebase_lane_after_commit=True,
        )

    assert calls == ["commit", "sync", "revert"]
    assert workflow._WORKFLOW_COMMIT_RECEIPTS[-1]["outcome"] == "refused"
    assert event_path.read_text(encoding="utf-8") == "before\n"
    assert status_path.read_text(encoding="utf-8") == '{"lane":"planned"}\n'


def test_workflow_review_tracks_reviewer_agent_name(workflow_repo: Path) -> None:
    """Review command records the reviewer in canonical runtime state.

    Extracted from tests/legacy/specify_cli/test_workflow_auto_moves.py.
    """
    # Arrange
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane="for_review")
    # Seed event log with for_review lane so review command finds canonical state
    _seed_wp_lane(feature_dir, "WP01", "for_review")
    _mark_fake_worktree(lane_worktree_path(workflow_repo, mission_slug))

    # Assumption check
    frontmatter_before, _, _ = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter_before, "agent") == ""

    # Act
    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", mission_slug, "--agent", "claude"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    from specify_cli.status import read_event_stream, reduce

    stream = read_event_stream(feature_dir)
    snapshot = reduce(stream.transitions, stream.annotations)
    assert snapshot.work_packages["WP01"]["agent"] == "claude"
    frontmatter, _, _ = split_frontmatter(wp_path.read_text(encoding="utf-8"))
    assert extract_scalar(frontmatter, "agent") == ""


def test_workflow_review_uses_existing_canonical_event_lane(workflow_repo: Path) -> None:
    """Review should read the existing canonical event lane before claiming the WP."""
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane="for_review")
    _mark_fake_worktree(lane_worktree_path(workflow_repo, mission_slug))

    emit_status_transition(TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id="WP01",
        to_lane="for_review",
        actor="system",
        force=True,
        reason="seed canonical lane",
        repo_root=workflow_repo,
    ))

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 0, result.stdout
    # Lane is event-log-only; verify canonical state via event log
    from specify_cli.status.store import read_events
    from specify_cli.status.reducer import reduce
    events = read_events(feature_dir)
    snapshot = reduce(events)
    wp_state = snapshot.work_packages.get("WP01", {})
    assert wp_state.get("lane") in ("in_progress", "doing", "in_review"), f"Expected in_progress or in_review lane, got: {wp_state.get('lane')}"


def _setup_implement_fixture(workflow_repo: Path, *, lane: str = "planned") -> tuple[Path, str]:
    """Shared setup for implement prompt-content tests.

    Returns (wp_path, mission_slug).
    """
    mission_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    _write_current_analysis_report(feature_dir, workflow_repo)
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane=lane)
    # Seed canonical state so implement doesn't hard-fail (no frontmatter fallback)
    _seed_wp_lane(feature_dir, "WP01", lane)
    # Pre-create workspace so implement skips real git worktree creation
    workspace = lane_worktree_path(workflow_repo, mission_slug)
    _mark_fake_worktree(workspace)
    return wp_path, mission_slug


def _setup_review_fixture(workflow_repo: Path, *, lane: str = "for_review") -> tuple[Path, str]:
    """Shared setup for review prompt-content tests.

    Returns (wp_path, feature_slug).
    """
    feature_slug = "001-test-feature"
    feature_dir = workflow_repo / "kitty-specs" / feature_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", lane=lane)
    _seed_wp_lane(feature_dir, "WP01", lane)
    workspace = lane_worktree_path(workflow_repo, feature_slug)
    _mark_fake_worktree(workspace)
    return wp_path, feature_slug


def test_implement_prompt_includes_when_youre_done_header(workflow_repo: Path) -> None:
    """Implement prompt file must include the 'WHEN YOU'RE DONE:' section header.

    Extracted from tests/legacy/unit/agent/test_workflow_instructions.py.
    """
    # Arrange
    wp_path, mission_slug = _setup_implement_fixture(workflow_repo)

    # Act
    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    assert prompt_file.exists(), f"Prompt file not written: {prompt_file}"
    content = prompt_file.read_text(encoding="utf-8")
    assert "WHEN YOU'RE DONE:" in content
    assert "1. **Commit your implementation files:**" in content
    assert "git add" in content
    assert "git commit" in content
    assert "feat(WP01):" in content or "fix(WP01):" in content
    assert "git log -1" in content


def test_implement_prompt_includes_commit_message_conventions(workflow_repo: Path) -> None:
    """Implement prompt file must document commit message type conventions.

    Extracted from tests/legacy/unit/agent/test_workflow_instructions.py.
    """
    # Arrange
    wp_path, mission_slug = _setup_implement_fixture(workflow_repo)

    # Act
    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    assert "feat(" in content or "fix(" in content
    assert "chore:" in content or "chore(" in content
    assert "docs:" in content or "docs(" in content


def test_implement_prompt_has_numbered_steps(workflow_repo: Path) -> None:
    """Implement prompt file must include numbered steps 1, 2, 3.

    Extracted from tests/legacy/unit/agent/test_workflow_instructions.py.
    """
    # Arrange
    wp_path, mission_slug = _setup_implement_fixture(workflow_repo)

    # Act
    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
    )

    # Assert
    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    assert "1. **Commit your implementation files:**" in content
    assert "2." in content
    assert "3." in content


def test_implement_prompt_points_to_shared_mission_artifacts(workflow_repo: Path) -> None:
    _wp_path, feature_slug = _setup_implement_fixture(workflow_repo)

    result = CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", feature_slug, "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    assert "📚 SHARED MISSION ARTIFACTS:" in content
    assert f"Spec, plan, and tasks are visible from the primary checkout: {workflow_repo}/kitty-specs/{feature_slug}/" in content
    assert "Status authority resolves through the coordination worktree for modern missions." in content
    assert "Use this lane workspace for code/tests; do not expect shared mission artifacts here" in content


def test_review_prompt_points_to_shared_mission_artifacts(workflow_repo: Path) -> None:
    _wp_path, feature_slug = _setup_review_fixture(workflow_repo)

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", feature_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    assert "📚 SHARED MISSION ARTIFACTS:" in content
    assert f"Spec, plan, and tasks are visible from the primary checkout: {workflow_repo}/kitty-specs/{feature_slug}/" in content
    assert "Status authority resolves through the coordination worktree for modern missions." in content
    assert "Use this lane workspace for code/tests; do not expect shared mission artifacts here" in content


def test_review_prompt_includes_mission_review_antipattern_checklist(workflow_repo: Path) -> None:
    _wp_path, feature_slug = _setup_review_fixture(workflow_repo)

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", feature_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    assert "Anti-pattern checklist (WP-level cheap version of mission-review)" in content
    assert "PASS / FAIL / N/A" in content
    assert "Dead code" in content
    assert "Synthetic-fixture test" in content
    assert "Silent empty return" in content
    assert "FR coverage" in content
    assert "Frozen surface" in content
    assert "Locked decision" in content
    assert "Shared-file ownership" in content
    assert "Production fragility" in content


def test_review_prompt_numbers_feedback_path_by_writer_max_plus_one_on_gap(
    workflow_repo: Path,
) -> None:
    """#3243: the advertised feedback path follows the writer's max+1 allocation.

    Drives the real ``review`` command (not the seam in isolation) with a
    numbering gap on disk — ``review-cycle-1.md`` + ``review-cycle-3.md`` — so
    the count of artifacts (2) diverges from the max parsed cycle (3). The
    prompt must advertise ``review-feedback-4.md`` (max+1, the number the
    rejection writer would allocate), never ``review-feedback-3.md``
    (len(glob)+1, the pre-#3243 count derivation this test exists to keep
    retired at the call site).
    """
    _wp_path, feature_slug = _setup_review_fixture(workflow_repo)
    sub_artifact_dir = workflow_repo / "kitty-specs" / feature_slug / "tasks" / "WP01-test"
    sub_artifact_dir.mkdir(parents=True, exist_ok=True)
    (sub_artifact_dir / "review-cycle-1.md").write_text("cycle 1\n", encoding="utf-8")
    (sub_artifact_dir / "review-cycle-3.md").write_text("cycle 3\n", encoding="utf-8")

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", feature_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 0, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    content = prompt_file.read_text(encoding="utf-8")
    advertised = sub_artifact_dir / "review-feedback-4.md"
    assert f"{advertised}" in content
    # The count-based derivation (len(glob) + 1 = 3) is exactly the
    # pre-#3243 off-by-one this PR retires; it must not come back.
    assert "review-feedback-3.md" not in content


def test_review_prompt_fails_closed_on_unparseable_cycle_sibling(
    workflow_repo: Path,
) -> None:
    """#3243: an unparseable review-cycle sibling makes ``review`` exit 1.

    The old count derivation globbed and counted blindly, so
    ``review-cycle-final.md`` merely inflated the count and the prompt still
    advertised a path the rejection writer would refuse — the #3430 "printed
    command not runnable as printed" shape. The prompt must instead fail
    closed here (typer.Exit(1)) with a repair message naming the sibling and
    telling the operator the WP is already claimed for review and that
    re-running the same command resumes it.
    """
    _wp_path, feature_slug = _setup_review_fixture(workflow_repo)
    sub_artifact_dir = workflow_repo / "kitty-specs" / feature_slug / "tasks" / "WP01-test"
    sub_artifact_dir.mkdir(parents=True, exist_ok=True)
    (sub_artifact_dir / "review-cycle-1.md").write_text("cycle 1\n", encoding="utf-8")
    (sub_artifact_dir / "review-cycle-final.md").write_text("not parseable\n", encoding="utf-8")

    result = CliRunner().invoke(
        workflow.app,
        ["review", "WP01", "--mission", feature_slug, "--agent", "test-reviewer"],
    )

    assert result.exit_code == 1, result.stdout
    assert "Error: cannot determine the next review-cycle number for WP01" in result.stdout
    assert "review-cycle-final.md" in result.stdout
    assert "WP01 is already claimed for review" in result.stdout
    assert "re-run this same review command to resume" in result.stdout
