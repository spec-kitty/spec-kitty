"""Tests for WP04: workflow.py canonical status cleanup.

Verifies:
- implement body note does NOT contain lane=
- review body note does NOT contain lane=
- implement hard-fails when no canonical state for WP
- review hard-fails when no canonical state for WP
- implement succeeds when canonical state exists
- review succeeds when canonical state exists
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.cli.commands.agent import workflow
from specify_cli.analysis_report import write_analysis_report
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status.models import StatusEvent, Lane, actor_identity_str
from specify_cli.status.store import read_events
from tests._support.status_seed import seed_status_event
from specify_cli.task_utils import split_frontmatter

pytestmark = pytest.mark.fast


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str, *, actor: str = "test") -> None:
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
        actor=actor,
        force=True,
        execution_mode="worktree",
    )
    seed_status_event(feature_dir, event)


def _write_wp_file(path: Path, wp_id: str, lane: str) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": ["T001"],
        "title": f"{wp_id} Test",
        "phase": "Phase 0",
        "lane": lane,
        "execution_mode": "code_change",
        "owned_files": [f"src/{wp_id.lower()}/**"],
        "authoritative_surface": f"src/{wp_id.lower()}/",
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
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z - system - Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _write_current_analysis_report(feature_dir: Path, repo_root: Path) -> None:
    """Write a current analysis report for implement success-path fixtures."""
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    if not (feature_dir / "tasks.md").exists():
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _mint_fake_worktree(repo_root: Path, workspace: Path) -> None:
    """Mark a fixture workspace as a git worktree (#1833 husk guard).

    Tests in this module fabricate lane workspaces without running
    ``git worktree add``; the fall-through-is-failure guards now require a
    ``.git`` entry, so plant the gitfile marker the real command would create.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = repo_root / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")


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


# ---------------------------------------------------------------------------
# T011: implement body note does NOT contain lane=
# ---------------------------------------------------------------------------


class TestImplementBodyNoteLaneFree:
    """Implement history entries must not contain lane= segments."""

    def test_implement_body_note_no_lane_from_planned(self, workflow_repo: Path) -> None:
        """When implementing from planned, body note should not contain lane=."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="planned")
        # Seed canonical state so implement doesn't hard-fail
        _seed_wp_lane(feature_dir, "WP01", "planned")
        _write_current_analysis_report(feature_dir, workflow_repo)

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 0, result.stdout
        content = wp_path.read_text(encoding="utf-8")
        _, body, _ = split_frontmatter(content)
        # WP-file history/activity-log writes are retired (#2816): implement records
        # the agent in the event log, NOT the WP body — so no `test-agent` history
        # row and (trivially) no `lane=` segment are ever appended to the body.
        assert "test-agent" not in body, f"WP body carries a retired history row: {body}"
        assert "lane=" not in body, f"WP body carries a retired lane= segment: {body}"
        # Attribution moved to the event log — the runtime transition records the agent.
        assert any(
            e.wp_id == "WP01" and actor_identity_str(e.actor) == "test-agent"
            for e in read_events(feature_dir)
        ), "expected an event-log transition attributed to test-agent"

    def test_implement_body_note_no_lane_from_doing(self, workflow_repo: Path) -> None:
        """When re-entering doing, body note should not contain lane=."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="doing")
        # Seed canonical state as in_progress (= doing)
        _seed_wp_lane(feature_dir, "WP01", "doing", actor="test-agent")
        _write_current_analysis_report(feature_dir, workflow_repo)

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 0, result.stdout
        content = wp_path.read_text(encoding="utf-8")
        _, body, _ = split_frontmatter(content)
        # WP-file history/activity-log writes are retired (#2816): no `test-agent`
        # history row and (trivially) no `lane=` segment reach the WP body.
        assert "test-agent" not in body, f"WP body carries a retired history row: {body}"
        assert "lane=" not in body, f"WP body carries a retired lane= segment: {body}"
        # Attribution lives in the event log — the WP was seeded in_progress by test-agent.
        assert any(
            e.wp_id == "WP01" and e.actor == "test-agent" for e in read_events(feature_dir)
        ), "expected an event-log transition attributed to test-agent"


# ---------------------------------------------------------------------------
# T012: review body note does NOT contain lane=
# ---------------------------------------------------------------------------


class TestReviewBodyNoteLaneFree:
    """Review history entries must not contain lane= segments."""

    def test_review_body_note_no_lane(self, workflow_repo: Path) -> None:
        """Review body note should not contain lane= segment."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="for_review")
        # Seed canonical state
        _seed_wp_lane(feature_dir, "WP01", "for_review")

        # #1833: review no longer warn-and-continues past a failed worktree
        # creation; pre-create the lane workspace with a .git marker.
        _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, mission_slug))

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code == 0, result.stdout
        content = wp_path.read_text(encoding="utf-8")
        _, body, _ = split_frontmatter(content)
        # WP-file history/activity-log writes are retired (#2816): review records the
        # reviewer in the event log, NOT the WP body — no `test-reviewer` history row
        # and (trivially) no `lane=` segment reach the body.
        assert "test-reviewer" not in body, f"WP body carries a retired history row: {body}"
        assert "lane=" not in body, f"WP body carries a retired lane= segment: {body}"


# ---------------------------------------------------------------------------
# T013: implement hard-fails when no canonical state
# ---------------------------------------------------------------------------


class TestImplementHardFailNoCanonical:
    """Implement must raise RuntimeError when WP has no canonical status."""

    def test_implement_hardfails_no_events(self, workflow_repo: Path) -> None:
        """Implement should fail when event log has no state for WP."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="planned")
        # NO event seeding -- WP has no canonical state

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code != 0, f"Expected failure, got exit_code=0: {result.stdout}"
        assert "no canonical status" in (result.stdout + str(result.exception or "")).lower(), f"Expected 'no canonical status' in output, got: {result.stdout}"
        assert "finalize-tasks" in (result.stdout + str(result.exception or "")), f"Expected finalize-tasks guidance in output, got: {result.stdout}"

    def test_implement_hardfails_events_exist_but_not_for_wp(self, workflow_repo: Path) -> None:
        """Implement should fail when event log has events for other WPs but not this one."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="planned")
        # Seed events for WP02 only — WP01 has no canonical state
        _seed_wp_lane(feature_dir, "WP02", "planned")

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code != 0, f"Expected failure, got exit_code=0: {result.stdout}"
        assert "no canonical status" in (result.stdout + str(result.exception or "")).lower()

    def test_implement_succeeds_with_canonical_state(self, workflow_repo: Path) -> None:
        """Implement should succeed when WP has canonical state in event log."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="planned")
        # Seed canonical state
        _seed_wp_lane(feature_dir, "WP01", "planned")
        _write_current_analysis_report(feature_dir, workflow_repo)

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP01", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 0, f"Expected success: {result.stdout}"

    def test_implement_uses_main_status_when_env_root_points_at_lane_worktree(
        self,
        workflow_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A lane-scoped SPECIFY_REPO_ROOT must not make implement read lane-local status."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        _write_wp_file(tasks_dir / "WP01-test.md", "WP01", lane="planned")
        _seed_wp_lane(feature_dir, "WP01", "planned")
        _write_current_analysis_report(feature_dir, workflow_repo)

        workspace = lane_worktree_path(workflow_repo, mission_slug)
        _mint_fake_worktree(workflow_repo, workspace)
        (workspace / ".kittify").mkdir()
        (workspace / "kitty-specs" / mission_slug).mkdir(parents=True)
        monkeypatch.setenv("SPECIFY_REPO_ROOT", str(workspace))
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


# ---------------------------------------------------------------------------
# T014: review hard-fails when no canonical state
# ---------------------------------------------------------------------------


class TestReviewHardFailNoCanonical:
    """Review must raise RuntimeError when WP has no canonical status."""

    def test_review_hardfails_no_events(self, workflow_repo: Path) -> None:
        """Review should fail when event log has no state for WP."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="for_review")
        # NO event seeding -- WP has no canonical state

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code != 0, f"Expected failure, got exit_code=0: {result.stdout}"
        assert "no canonical status" in (result.stdout + str(result.exception or "")).lower(), f"Expected 'no canonical status' in output, got: {result.stdout}"
        assert "finalize-tasks" in (result.stdout + str(result.exception or "")), f"Expected finalize-tasks guidance in output, got: {result.stdout}"

    def test_review_hardfails_events_exist_but_not_for_wp(self, workflow_repo: Path) -> None:
        """Review should fail when event log has events for other WPs but not this one."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="for_review")
        # Seed events for WP02 only
        _seed_wp_lane(feature_dir, "WP02", "for_review")

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code != 0, f"Expected failure, got exit_code=0: {result.stdout}"
        assert "no canonical status" in (result.stdout + str(result.exception or "")).lower()

    def test_review_succeeds_with_canonical_state(self, workflow_repo: Path) -> None:
        """Review should succeed when WP has canonical state in event log."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="for_review")
        # Seed canonical state
        _seed_wp_lane(feature_dir, "WP01", "for_review")

        # #1833: review no longer warn-and-continues past a failed worktree
        # creation; pre-create the lane workspace with a .git marker.
        _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, mission_slug))

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code == 0, f"Expected success: {result.stdout}"

    def test_review_rejects_plain_in_progress_wp_without_review_claim(self, workflow_repo: Path) -> None:
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
        wp_path = tasks_dir / "WP01-test.md"
        _write_wp_file(wp_path, "WP01", lane="doing")
        _seed_wp_lane(feature_dir, "WP01", "doing")

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP01", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code != 0
        assert "still being implemented" in result.stdout


class TestPlanningArtifactWorkflowPrompt:
    """Planning-artifact WPs should guide agents to the repository root."""

    def test_implement_prompt_uses_repo_root_for_planning_artifact(self, workflow_repo: Path) -> None:
        mission_slug = "077-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text(
            "## WP01 Code\n\n- [x] T001 Placeholder task\n\n## WP02 Planning\n\n- [x] T002 Placeholder task\n",
            encoding="utf-8",
        )
        _write_wp_file(tasks_dir / "WP01-code.md", "WP01", lane="planned")
        (tasks_dir / "WP02-planning.md").write_text(
            "---\n"
            "work_package_id: WP02\n"
            "title: WP02 Planning\n"
            "dependencies: []\n"
            "execution_mode: planning_artifact\n"
            "owned_files:\n"
            f"  - kitty-specs/{mission_slug}/**\n"
            f"authoritative_surface: kitty-specs/{mission_slug}/\n"
            "---\n"
            "# WP02 Planning Prompt\n",
            encoding="utf-8",
        )
        _seed_wp_lane(feature_dir, "WP02", "planned")
        _write_current_analysis_report(feature_dir, workflow_repo)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP02", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 0, result.stdout
        prompt_path = Path(next(line.split("cat ", 1)[1].strip() for line in result.stdout.splitlines() if line.strip().startswith("cat ")))
        prompt = prompt_path.read_text(encoding="utf-8")

        assert f"Workspace: {workflow_repo}" in prompt
        assert "Workspace contract: lane lane-planning" in prompt
        assert f"cd {workflow_repo}" in prompt
        assert "workspace_kind\": \"repo_root" in prompt
        assert "<!-- WORKTREE_TOPOLOGY -->" in prompt
        assert "runs in the repository root planning workspace" in prompt

    def test_planning_artifact_implement_claim_emits_direct_repo_status_event(self, workflow_repo: Path) -> None:
        mission_slug = "077-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text(
            "## WP02 Planning\n\n- [x] T002 Placeholder task\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02-planning.md").write_text(
            "---\n"
            "work_package_id: WP02\n"
            "title: WP02 Planning\n"
            "dependencies: []\n"
            "execution_mode: planning_artifact\n"
            "owned_files:\n"
            f"  - kitty-specs/{mission_slug}/**\n"
            f"authoritative_surface: kitty-specs/{mission_slug}/\n"
            "---\n"
            "# WP02 Planning Prompt\n",
            encoding="utf-8",
        )
        _seed_wp_lane(feature_dir, "WP02", "planned")
        _write_current_analysis_report(feature_dir, workflow_repo)

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP02", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 0, result.stdout
        latest = [event for event in read_events(feature_dir) if event.wp_id == "WP02"][-1]
        assert latest.execution_mode == "direct_repo"

    def test_review_prompt_reports_unavailable_diff_without_claim_commit_for_planning_artifact(self, workflow_repo: Path) -> None:
        mission_slug = "077-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text(
            "## WP02 Planning\n\n- [x] T002 Placeholder task\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02-planning.md").write_text(
            "---\n"
            "work_package_id: WP02\n"
            "title: WP02 Planning\n"
            "dependencies: []\n"
            "execution_mode: planning_artifact\n"
            "owned_files:\n"
            f"  - kitty-specs/{mission_slug}/**\n"
            f"authoritative_surface: kitty-specs/{mission_slug}/\n"
            "---\n"
            "# WP02 Planning Prompt\n",
            encoding="utf-8",
        )
        _seed_wp_lane(feature_dir, "WP02", "for_review")

        result = CliRunner().invoke(
            workflow.app,
            ["review", "WP02", "--mission", mission_slug, "--agent", "test-reviewer"],
        )

        assert result.exit_code == 0, result.stdout
        prompt_path = Path(next(line.split("cat ", 1)[1].strip() for line in result.stdout.splitlines() if line.strip().startswith("cat ")))
        prompt = prompt_path.read_text(encoding="utf-8")

        assert "Review commands unavailable: no deterministic implementation claim commit found for this WP." in prompt


# ---------------------------------------------------------------------------
# Dependency gate on the `agent action implement` verb (explicit WP, existing
# workspace). Mirrors the orchestrator-api start-implementation twin.
# ---------------------------------------------------------------------------


class TestImplementDependencyGate:
    """workflow.py `implement` dependency gate: block fresh dep-blocked claims,
    resume already-in_progress WPs without re-gating."""

    def _scaffold_dependent_pair(self, feature_dir: Path, wp02_dep: str = "WP01") -> None:
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"), predicted_surfaces=("workflow",))
        (feature_dir / "tasks.md").write_text(
            "## WP01 Test\n\n- [x] T001 Placeholder task\n\n## WP02 Test\n\n- [x] T002 Placeholder task\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP01-test.md").write_text(
            "---\n"
            "work_package_id: WP01\n"
            "subtasks: [T001]\n"
            "title: WP01 Test\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01 Prompt\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02-test.md").write_text(
            "---\n"
            "work_package_id: WP02\n"
            "subtasks: [T002]\n"
            "title: WP02 Test\n"
            f"dependencies: [{wp02_dep}]\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp02/**\n"
            "authoritative_surface: src/wp02/\n"
            "---\n# WP02 Prompt\n",
            encoding="utf-8",
        )

    def test_implement_blocks_dep_unsatisfied_planned_wp_with_existing_workspace(
        self, workflow_repo: Path
    ) -> None:
        """Explicit dep-blocked planned WP is rejected at the workflow.py gate even
        when its workspace already exists (so top_level_implement is not called)."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        self._scaffold_dependent_pair(feature_dir)
        # WP01 is only in_progress (not approved/done); WP02 stays planned.
        _seed_wp_lane(feature_dir, "WP01", "in_progress")
        _seed_wp_lane(feature_dir, "WP02", "planned")
        # Workspace already resolves so creation is skipped and the gate is reached.
        _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, mission_slug))

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP02", "--mission", mission_slug, "--agent", "test-agent"],
        )

        assert result.exit_code == 1, result.stdout
        assert "dependencies_not_satisfied" in result.stdout
        assert "all dependencies must be approved or done" in result.stdout

    def test_implement_resumes_in_progress_wp_with_unsatisfied_dependency(
        self, workflow_repo: Path
    ) -> None:
        """An already in_progress WP resumes without re-gating, even if its
        dependency later regressed out of approved/done."""
        mission_slug = "060-test-feature"
        feature_dir = workflow_repo / "kitty-specs" / mission_slug
        self._scaffold_dependent_pair(feature_dir)
        # WP01 reverted to in_progress (unsatisfied); WP02 was already started.
        _seed_wp_lane(feature_dir, "WP01", "in_progress")
        _seed_wp_lane(feature_dir, "WP02", "in_progress", actor="test-agent")
        _write_current_analysis_report(feature_dir, workflow_repo)
        _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, mission_slug))

        result = CliRunner().invoke(
            workflow.app,
            ["implement", "WP02", "--mission", mission_slug, "--agent", "test-agent"],
        )

        # Gate skipped (WP02 is in_progress) -> resume succeeds, no dependency error.
        assert result.exit_code == 0, result.stdout
        assert "dependencies_not_satisfied" not in result.stdout
