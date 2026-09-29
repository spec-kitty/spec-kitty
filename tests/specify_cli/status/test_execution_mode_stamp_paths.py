"""``execution_mode`` stamp parity across every status-emit path (#5100 WP04 T016).

``ResolvedWorkspace.status_execution_mode`` is the ONE derivation every emit
site now reads (``implement.py``, ``agent/workflow.py``,
``agent/workflow_executor.py``, ``orchestrator_api/commands.py``,
``tasks_move_task.py``). Each test below drives a REAL production entry
point against a repo-root-lane (single_branch) fixture, asserting
``execution_mode == "direct_repo"``, paired with a code-lane (``lanes``
topology) control asserting ``"worktree"`` -- the non-vacuity control this
WP's design calls for.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.store import read_events
from tests.utils import _seed_canonical_wp_state, write_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_ID = "01STAMPPATHSMISSION0000001"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, mission_slug: str, *, topology: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": mission_slug,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "topology": topology,
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": mission_slug,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _repo_root_manifest(mission_slug: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=_MISSION_ID,
        mission_branch="",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _code_lane_manifest(mission_slug: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=_MISSION_ID,
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
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _build_mission(tmp_path: Path, tag: str, *, topology: str) -> tuple[Path, str, Path]:
    mission_slug = f"stamp-{tag}"
    repo = tmp_path / mission_slug
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug, topology=topology)
    write_wp(repo, mission_slug, "planned", "WP01", seed_canonical=False)
    manifest = _repo_root_manifest(mission_slug) if topology == "single_branch" else _code_lane_manifest(mission_slug)
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: seed WP01 + lanes.json")
    return repo, mission_slug, feature_dir


def _last_execution_mode(feature_dir: Path, wp_id: str) -> str:
    events = [e for e in read_events(feature_dir) if e.wp_id == wp_id]
    assert events, f"no events recorded for {wp_id}"
    return events[-1].execution_mode


# ---------------------------------------------------------------------------
# orchestrator_api: start-implementation
# ---------------------------------------------------------------------------


def _valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "test-orch",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _start_implementation(repo: Path, mission_slug: str) -> object:
    from specify_cli.orchestrator_api.commands import app

    with patch("specify_cli.orchestrator_api.commands._get_main_repo_root", return_value=repo):
        return runner.invoke(
            app,
            ["start-implementation", "--mission", mission_slug, "--wp", "WP01", "--actor", "claude", "--policy", _valid_policy_json()],
            catch_exceptions=False,
        )


@pytest.mark.parametrize(
    ("topology", "expected"),
    [("single_branch", "direct_repo"), ("lanes", "worktree")],
)
def test_orchestrator_start_implementation_stamps_execution_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str, expected: str) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)
    repo, mission_slug, feature_dir = _build_mission(tmp_path, f"start-{topology}", topology=topology)
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "planned", actor="system", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:30:00Z")

    result = _start_implementation(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert _last_execution_mode(feature_dir, "WP01") == expected


# ---------------------------------------------------------------------------
# orchestrator_api: transition
# ---------------------------------------------------------------------------


def _transition(repo: Path, mission_slug: str, *, to: str) -> object:
    from specify_cli.orchestrator_api.commands import app

    with patch("specify_cli.orchestrator_api.commands._get_main_repo_root", return_value=repo):
        return runner.invoke(
            app,
            ["transition", "--mission", mission_slug, "--wp", "WP01", "--to", to, "--actor", "claude", "--policy", _valid_policy_json()],
            catch_exceptions=False,
        )


@pytest.mark.parametrize(
    ("topology", "expected"),
    [("single_branch", "direct_repo"), ("lanes", "worktree")],
)
def test_orchestrator_transition_stamps_execution_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str, expected: str) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)
    repo, mission_slug, feature_dir = _build_mission(tmp_path, f"transition-{topology}", topology=topology)
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "claimed", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "status: claim WP01")

    result = _transition(repo, mission_slug, to="in_progress")

    assert result.exit_code == 0, result.output
    assert _last_execution_mode(feature_dir, "WP01") == expected


# ---------------------------------------------------------------------------
# agent/workflow_executor: review_resolve_wp_and_lane_gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("topology", "expected"),
    [("single_branch", "direct_repo"), ("lanes", "worktree")],
)
def test_review_resolve_wp_and_lane_gate_stamps_execution_mode(tmp_path: Path, topology: str, expected: str) -> None:
    from specify_cli.cli.commands.agent.workflow_executor import review_resolve_wp_and_lane_gate

    repo, mission_slug, feature_dir = _build_mission(tmp_path, f"review-{topology}", topology=topology)
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "for_review", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")

    ctx = review_resolve_wp_and_lane_gate(repo, repo, mission_slug, "WP01")

    assert ctx.status_execution_mode == expected


# ---------------------------------------------------------------------------
# tasks_move_task: _mt_emit_transitions (via the real ``move-task`` CLI)
# ---------------------------------------------------------------------------


def _move_task(repo: Path, mission_slug: str, *, to: str) -> object:
    from specify_cli.cli.commands.agent.tasks import app

    return runner.invoke(
        app,
        ["move-task", "WP01", "--to", to, "--mission", mission_slug, "--no-auto-commit", "--force", "--skip-pre-review-gate", "--json"],
        catch_exceptions=False,
    )


@pytest.mark.parametrize(
    ("topology", "expected"),
    [("single_branch", "direct_repo"), ("lanes", "worktree")],
)
def test_move_task_stamps_execution_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str, expected: str) -> None:
    repo, mission_slug, feature_dir = _build_mission(tmp_path, f"movetask-{topology}", topology=topology)
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "claimed", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))

    result = _move_task(repo, mission_slug, to="in_progress")

    assert result.exit_code == 0, result.output
    assert _last_execution_mode(feature_dir, "WP01") == expected
