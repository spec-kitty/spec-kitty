"""Integration tests for fix-mode detection and rejection cycle (WP02).

Tests the interaction between:
- ReviewCycleArtifact persistence (WP01)
- _has_prior_rejection() detection helper (WP02)
- Mode switching in the implement action (WP02)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.artifacts import AffectedFile, ReviewCycleArtifact
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_EVENT_COUNTER: int = 0


def _prompt_path_from_output(output: str) -> Path:
    """Extract the prompt file path from the CLI's ``cat <path>`` hint.

    The prompt is written under the shared, per-repo namespace (WP02 /
    FR-003), not a hardcoded flat ``/tmp`` path — parse it from the printed
    instruction instead of assuming the location.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            return Path(stripped[4:].strip())
    raise AssertionError(f"Prompt path not found in output: {output}")


def _make_event(
    *,
    event_id: str = "01HXYZ0123456789ABCDEFGHJK",
    wp_id: str = "WP01",
    from_lane: Lane = Lane.PLANNED,
    to_lane: Lane = Lane.CLAIMED,
    review_ref: str | None = None,
    mission_slug: str = "066-test-mission",
) -> StatusEvent:
    global _EVENT_COUNTER  # noqa: PLW0603
    _EVENT_COUNTER += 1
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-04-06T12:00:{_EVENT_COUNTER:02d}Z",
        actor="claude",
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
    )


def _make_artifact(
    tmp_path: Path,
    wp_slug: str = "WP01-some-title",
    cycle: int = 1,
    **kwargs: object,
) -> tuple[Path, ReviewCycleArtifact]:
    """Write a review-cycle artifact and return (sub_artifact_dir, artifact)."""
    sub_dir = tmp_path / "kitty-specs" / "066-test-mission" / "tasks" / wp_slug
    sub_dir.mkdir(parents=True, exist_ok=True)

    defaults: dict = {
        "cycle_number": cycle,
        "wp_id": "WP01",
        "mission_slug": "066-test-mission",
        "reviewer_agent": "claude",
        "reviewed_at": "2026-04-06T12:00:00Z",
        "affected_files": [AffectedFile(path="src/foo.py", line_range="1-10")],
        "reproduction_command": "pytest tests/ -x",
        "body": "## Issues\n\nPlease fix.",
    }
    defaults.update(kwargs)
    artifact = ReviewCycleArtifact(**defaults)  # type: ignore[arg-type]
    artifact.write(sub_dir / f"review-cycle-{cycle}.md")
    return sub_dir, artifact


def _write_wp_file(
    tmp_path: Path,
    wp_slug: str = "WP01-some-title",
    mission_slug: str = "066-test-mission",
) -> Path:
    """Write a stub WP markdown file in the tasks directory."""
    tasks_dir = tmp_path / "kitty-specs" / mission_slug / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{wp_slug}.md"
    wp_file.write_text("---\nwork_package_id: WP01\n---\n\n# WP01\n", encoding="utf-8")
    return wp_file


def _write_cli_wp(wp_path: Path) -> None:
    write_frontmatter(
        wp_path,
        {
            "work_package_id": "WP01",
            "subtasks": ["T001"],
            "title": "Test Task",
            "phase": "Phase 1",
            "lane": "planned",
            "dependencies": [],
            "assignee": "",
            "agent": "unknown",
            "shell_pid": "",
            "review_status": "none",
            "review_feedback": "",
            "history": [],
        },
        "# WP01 Prompt\n",
    )


# ---------------------------------------------------------------------------
# T009: _has_prior_rejection helper tests
# ---------------------------------------------------------------------------

class TestHasPriorRejection:
    """Tests for the _has_prior_rejection() detection helper."""

    def test_no_artifacts_returns_false(self, tmp_path: Path) -> None:
        """test_has_prior_rejection_no_artifacts — returns False for clean WP."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        feature_dir.mkdir(parents=True)

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False

    def test_artifacts_but_no_events_returns_false(self, tmp_path: Path) -> None:
        """Artifacts exist but no event log — returns False."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title")

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False

    def test_artifacts_and_rejection_event_returns_true(self, tmp_path: Path) -> None:
        """test_has_prior_rejection_with_artifacts_and_event — returns True after rejection."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title")

        # Emit a rejection event with a canonical review-cycle artifact reference.
        rejection_event = _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.PLANNED,
            review_ref="review-cycle://066-test-mission/WP01-some-title/review-cycle-1.md",
        )
        append_event(feature_dir, rejection_event)

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is True

    def test_rejected_then_resolved_returns_false(self, tmp_path: Path) -> None:
        """Artifact exists but the latest event is not a rejection (approved) — returns False."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title")

        # First: rejection event
        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.PLANNED,
            review_ref="review-cycle://066-test-mission/WP01-some-title/review-cycle-1.md",
        ))
        # Then: approval (for_review -> approved)
        append_event(feature_dir, _make_event(
            event_id="01BBBB0000000000000000002B",
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
        ))
        # Then: re-implementation start (not from for_review)
        append_event(feature_dir, _make_event(
            event_id="01CCCC0000000000000000003C",
            wp_id="WP01",
            from_lane=Lane.APPROVED,
            to_lane=Lane.IN_PROGRESS,
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False

    def test_only_checks_matching_wp_id(self, tmp_path: Path) -> None:
        """Rejection events for a different WP ID do not trigger fix mode."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title")

        # Rejection event for WP02 only
        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP02",  # Different WP
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_PROGRESS,
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False

    def test_no_sub_artifact_dir_returns_false(self, tmp_path: Path) -> None:
        """Sub-artifact directory does not exist — returns False without error."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        feature_dir.mkdir(parents=True)
        # No sub-artifact directory created

        result = _has_prior_rejection(feature_dir, "WP01-missing-slug", "WP01")
        assert result is False

    def test_multiple_rejections_uses_latest(self, tmp_path: Path) -> None:
        """Multiple rejection events — still returns True (latest event is rejection)."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title", cycle=2)

        # First rejection
        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.PLANNED,
            review_ref="review-cycle://066-test-mission/WP01-some-title/review-cycle-1.md",
        ))
        # Second rejection (latest)
        append_event(feature_dir, _make_event(
            event_id="01BBBB0000000000000000002B",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.PLANNED,
            review_ref="review-cycle://066-test-mission/WP01-some-title/review-cycle-2.md",
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is True

    def test_reentry_after_rejection_still_returns_true(self, tmp_path: Path) -> None:
        """Claim/in-progress events after a rejection should not clear fix mode."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title", cycle=1)

        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.PLANNED,
            review_ref="review-cycle://066-test-mission/WP01-some-title/review-cycle-1.md",
        ))
        append_event(feature_dir, _make_event(
            event_id="01BBBB0000000000000000002B",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
        ))
        append_event(feature_dir, _make_event(
            event_id="01CCCC0000000000000000003C",
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is True


# ---------------------------------------------------------------------------
# T010: End-to-end mode switch tests
# ---------------------------------------------------------------------------

class TestModeSwitchProducesFixPrompt:
    """test_mode_switch_produces_fix_prompt — create artifact + rejection event → fix prompt."""

    def test_generate_fix_prompt_output_is_compact(self, tmp_path: Path) -> None:
        """Fix prompt from a single-file artifact is compact (< 25% of 491-line WP prompt)."""
        from specify_cli.review.fix_prompt import generate_fix_prompt

        # Write source file
        src = tmp_path / "src" / "target.py"
        src.parent.mkdir(parents=True)
        src.write_text("def foo():\n    return 1\n" * 5, encoding="utf-8")

        sub_dir, artifact = _make_artifact(
            tmp_path,
            "WP01-some-title",
            affected_files=[AffectedFile(path="src/target.py", line_range="1-5")],
            body="## Issues\n\nFix the function.\n",
            reproduction_command="pytest tests/ -x",
        )

        prompt = generate_fix_prompt(
            artifact=artifact,
            worktree_path=tmp_path,

            mission_slug="066-test-mission",
            wp_id="WP01",
        )

        typical_wp_chars = 491 * 50
        assert len(prompt) < typical_wp_chars * 0.25

    def test_fix_prompt_is_self_contained(self, tmp_path: Path) -> None:
        """Fix prompt contains all required sections for the agent to act."""
        from specify_cli.review.fix_prompt import generate_fix_prompt

        src = tmp_path / "src" / "target.py"
        src.parent.mkdir(parents=True)
        src.write_text("pass\n")

        sub_dir, artifact = _make_artifact(
            tmp_path,
            "WP01-self-contained",
            body="## Findings\n\nMissing docstring.",
            affected_files=[AffectedFile(path="src/target.py", line_range="1-1")],
            reproduction_command="pytest tests/ -v",
        )

        prompt = generate_fix_prompt(
            artifact=artifact,
            worktree_path=tmp_path,
            mission_slug="066-test-mission",
            wp_id="WP01",
        )

        # Self-contained: findings, file, code, reproduction, instructions
        assert "## Review Findings" in prompt
        assert "Missing docstring." in prompt
        assert "## Affected Files" in prompt
        assert "src/target.py" in prompt
        assert "## Reproduction" in prompt
        assert "pytest tests/ -v" in prompt
        assert "## Instructions" in prompt
        assert "move-task WP01 --to for_review" in prompt


class TestModeSwitchFallsThroughOnResolved:
    """test_mode_switch_falls_through_on_resolved — artifact exists but last event is not rejection."""

    def test_no_rejection_event_means_no_fix_mode(self, tmp_path: Path) -> None:
        """When the latest WP event is NOT from for_review, _has_prior_rejection is False."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"
        _make_artifact(tmp_path, "WP01-some-title")

        # Event: claimed -> in_progress (not from for_review)
        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False

    def test_empty_artifact_dir_means_no_fix_mode(self, tmp_path: Path) -> None:
        """Empty sub-artifact dir (no .md files) means no fix mode even with rejection event."""
        from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection as _has_prior_rejection

        feature_dir = tmp_path / "kitty-specs" / "066-test-mission"

        # Create the directory but no artifact files
        empty_dir = feature_dir / "tasks" / "WP01-some-title"
        empty_dir.mkdir(parents=True)

        # Emit a rejection event
        append_event(feature_dir, _make_event(
            event_id="01AAAA0000000000000000001A",
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_PROGRESS,
        ))

        result = _has_prior_rejection(feature_dir, "WP01-some-title", "WP01")
        assert result is False


@pytest.fixture()
def workflow_cli_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    # Bypass the protected-branch guard for test fixtures on 'main'.
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")

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
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "mission_slug": mission_slug,
                "created_at": "2026-01-17T00:00:00Z",
                "friendly_name": mission_slug,
                "mission": "software-dev",
                "slug": mission_slug,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=f"mission-{mission_slug}",
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-04T10:00:00Z",
            computed_from="test",
        ),
    )
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _write_cli_wp(tasks_dir / "WP01-test-task.md")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed workflow fixture"], cwd=repo, check=True, capture_output=True)
    workspace = repo / ".worktrees" / f"{mission_slug}-lane-a"
    subprocess.run(
        ["git", "worktree", "add", "-b", f"{mission_slug}-lane-a", str(workspace), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(repo)
    return repo, feature_dir


class TestImplementReviewFeedbackHandoff:
    def test_implement_uses_review_cycle_artifact_after_review_claim(
        self,
        workflow_cli_repo: tuple[Path, Path],
    ) -> None:
        repo, feature_dir = workflow_cli_repo
        review_cycle_ref = "review-cycle://001-test-feature/WP01-test-task/review-cycle-2.md"
        ReviewCycleArtifact(
            cycle_number=2,
            wp_id="WP01",
            mission_slug="001-test-feature",
            reviewer_agent="codex",
            reviewed_at="2026-04-10T06:36:14Z",
            affected_files=[AffectedFile(path="src/example.py", line_range="1-5")],
            reproduction_command="pytest tests/integration/test_rejection_cycle.py -q",
            body="**Issue 1**: Use the canonical review artifact instead of the claim token.\n",
        ).write(feature_dir / "tasks" / "WP01-test-task" / "review-cycle-2.md")

        append_event(feature_dir, _make_event(event_id="01AAA000000000000000000001"))
        append_event(feature_dir, _make_event(event_id="01AAA000000000000000000002", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS))
        append_event(feature_dir, _make_event(event_id="01AAA000000000000000000003", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW))
        append_event(
            feature_dir,
            _make_event(
                event_id="01AAA000000000000000000004",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                review_ref="action-review-claim",
            ),
        )
        append_event(
            feature_dir,
            _make_event(
                event_id="01AAA000000000000000000005",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.PLANNED,
                review_ref=review_cycle_ref,
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            workflow.app,
            ["implement", "WP01", "--mission", "001-test-feature", "--agent", "test-agent"],
        )

        assert result.exit_code == 0, result.stdout
        assert "Fix mode" in result.stdout
        prompt_file = _prompt_path_from_output(result.stdout)
        prompt_content = prompt_file.read_text(encoding="utf-8")
        assert "## Review Findings" in prompt_content
        assert "Use the canonical review artifact instead of the claim token." in prompt_content
        assert "action-review-claim" not in prompt_content

    def test_implement_fails_when_canonical_review_artifact_is_unreadable(
        self,
        workflow_cli_repo: tuple[Path, Path],
    ) -> None:
        _repo, feature_dir = workflow_cli_repo
        review_cycle_ref = "review-cycle://001-test-feature/WP01-test-task/review-cycle-9.md"

        append_event(feature_dir, _make_event(event_id="01BBB000000000000000000001"))
        append_event(
            feature_dir,
            _make_event(
                event_id="01BBB000000000000000000002",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.PLANNED,
                review_ref=review_cycle_ref,
            ),
        )

        runner = CliRunner()
        result = runner.invoke(
            workflow.app,
            ["implement", "WP01", "--mission", "001-test-feature", "--agent", "test-agent"],
        )

        assert result.exit_code == 1, result.stdout
        assert "review feedback artifact is missing or unreadable" in result.stdout
        assert review_cycle_ref in result.stdout
