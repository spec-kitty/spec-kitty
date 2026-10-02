"""BLOCKING (WP08, post-tasks squad R-M3): reject-then-fix-mode handoff on a
coordination-routed Mission, driven through the REAL CLI entry points.

WP08 (coord-artifact-single-home-01M3V4BE) flips ``_review_cycle_wp_dir``'s
shared default to ``REVIEW_CYCLE``, moving the review-cycle write seam's
physical write into the coordination worktree. ``workflow_cores.py::
has_prior_rejection`` and ``workflow_executor.py::
implement_try_render_fix_mode_prompt`` both route through that same shared
resolver (at its default kind, no caller change needed) -- but ``workflow.py::
review`` used to hand-join a raw ``WORK_PACKAGE_TASK`` dir instead (fixed in
this WP). This test proves, end to end, that a rejection authored via the
real ``move-task --to planned --review-feedback-file`` CLI entry point is
VISIBLE to the fix-mode detector and the ``implement`` action renders the
focused fix-mode prompt from it -- never silently missing a rejection that
now lives solely on the coordination surface (the fail-open hazard the WP08
prompt names as this test's reason for being BLOCKING).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter, default_ports
from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.agent import workflow
from specify_cli.cli.commands.agent.workflow_cores import has_prior_rejection
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import TransitionRequest
from tests._factories import make_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WP_ID = "WP01"
_WP_SLUG = "WP01-fix-mode-coord"
_TARGET_BRANCH = "main"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True)


def _write_wp(feature_dir: Path) -> Path:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_path = tasks_dir / f"{_WP_SLUG}.md"
    wp_path.write_text(
        "---\n"
        f"work_package_id: {_WP_ID}\n"
        "title: WP08 fix-mode coord fixture\n"
        "execution_mode: code_change\n"
        "subtasks: []\n"
        "owned_files:\n  - src/wp08-fixture/**\n"
        "authoritative_surface: src/wp08-fixture/\n"
        "---\n\n# WP08 fix-mode fixture\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=feature_dir.parent.parent,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )
    return wp_path


def _seed_lane(repo: Path, feature_dir: Path, mission_slug: str, mission_id: str) -> None:
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=mission_id,
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch=_TARGET_BRANCH,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=(_WP_ID,),
                    write_scope=("src/wp08-fixture/**",),
                    predicted_surfaces=("src",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-10-01T00:00:00+00:00",
            computed_from="WP08 fix-mode fixture",
        ),
    )
    workspace = repo / ".worktrees" / f"{mission_slug}-lane-a"
    _git(repo, "worktree", "add", "-b", f"{mission_slug}-lane-a", str(workspace), _TARGET_BRANCH)


def _seed_for_review(repo: Path, mission_slug: str) -> None:
    status_dir = RealCoordCommitRouter().feature_write_dir(MissionHandle(repo_root=repo, mission_slug=mission_slug))
    for to_lane in ("claimed", "in_progress", "for_review"):
        request = TransitionRequest(
            feature_dir=status_dir,
            mission_slug=mission_slug,
            repo_root=repo,
            wp_id=_WP_ID,
            to_lane=to_lane,
            actor="wp08-seed",
            force=True,
            reason="seed reviewable state",
            execution_mode="worktree",
        )
        result = default_ports().coord.commit_status(request, capability=GuardCapability.STANDARD)
        assert result.event is not None and result.event.to_lane.value == to_lane


def _prompt_path_from_output(output: str) -> Path:
    """Extract the written prompt-file path from the CLI's ``cat <path>`` hint."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cat "):
            return Path(stripped[4:].strip())
    raise AssertionError(f"Prompt path not found in output: {output}")


def _reject(repo: Path, mission_slug: str) -> dict[str, Any]:
    feedback = repo.parent / f"{mission_slug}-feedback.md"
    feedback.write_text(
        "**Issue**: WP08 fix-mode coord fixture needs the missing regression test.\n",
        encoding="utf-8",
    )
    args = [
        "tasks",
        "move-task",
        _WP_ID,
        "--to",
        "planned",
        "--mission",
        mission_slug,
        "--agent",
        "reviewer-renata",
        "--reviewer",
        "reviewer-renata",
        "--json",
        "--auto-commit",
        "--review-feedback-file",
        str(feedback),
    ]
    result = CliRunner().invoke(agent_app, args, catch_exceptions=True)
    assert result.exit_code == 0, result.output
    for line in result.output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload: dict[str, Any] = json.loads(line)
            return payload
    raise AssertionError(f"no JSON payload in move-task output: {result.output!r}")


def test_implement_renders_fix_mode_from_a_coordination_surface_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLOCKING (R-M3): reject via the real ``move-task`` CLI, then run
    ``agent action implement`` -- it must render the fix-mode prompt from the
    rejection that now lives SOLELY on the coordination surface."""
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.name", "WP08 fix-mode fixture")
    _git(repo, "config", "user.email", "wp08-fix-mode@spec-kitty.test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init WP08 fix-mode fixture")

    created = make_mission(repo, "fix-mode-coord", topology=MissionTopology.COORD, target_branch=_TARGET_BRANCH)
    mission_slug = created.mission_slug
    mission_id = str(created.meta["mission_id"])
    _write_wp(created.feature_dir)
    _seed_lane(repo, created.feature_dir, mission_slug, mission_id)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed WP08 fix-mode fixture")

    monkeypatch.chdir(repo)
    _seed_for_review(repo, mission_slug)
    _reject(repo, mission_slug)

    # Pre-condition: the review-cycle artifact lives SOLELY on the
    # coordination surface -- no PRIMARY copy exists at all (WP08 single-home).
    coord_ref = placement_seam(repo, mission_slug).write_target(MissionArtifactKind.REVIEW_CYCLE).ref
    relative = f"kitty-specs/{mission_slug}/tasks/{_WP_SLUG}/review-cycle-1.md"
    coord_show = subprocess.run(["git", "-C", str(repo), "show", f"{coord_ref}:{relative}"], capture_output=True, text=True, check=False)
    assert coord_show.returncode == 0, coord_show.stderr
    assert not (repo / "kitty-specs" / mission_slug / "tasks" / _WP_SLUG / "review-cycle-1.md").exists()

    # The reader sees it too, handed only the PRIMARY feature_dir (exactly
    # what a real caller threads in -- the reader recomputes repo_root +
    # mission_slug internally and resolves the coordination surface itself).
    primary_feature_dir = repo / "kitty-specs" / mission_slug
    assert has_prior_rejection(primary_feature_dir, _WP_SLUG, _WP_ID) is True

    result = CliRunner().invoke(
        workflow.app,
        ["implement", _WP_ID, "--mission", mission_slug, "--agent", "test-agent"],
    )

    assert result.exit_code == 0, result.stdout
    assert "Fix mode" in result.stdout, result.stdout
    prompt_file = _prompt_path_from_output(result.stdout)
    prompt_content = prompt_file.read_text(encoding="utf-8")
    assert "WP08 fix-mode coord fixture needs the missing regression test." in prompt_content
