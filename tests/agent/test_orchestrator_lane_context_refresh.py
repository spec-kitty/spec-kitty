"""Regression: orchestrator-api start-implementation refreshes a reused lane's
workspace context (#3946 / F-78).

Before the fix, ``start-implementation`` allocated (or reused) the lane
worktree and advanced the canonical active WP, but never refreshed the lane's
persisted workspace context — so when a second WP was claimed into a lane that
already hosted an approved WP (lanes.json puts both in one lane), the context
kept ``current_wp`` from the earlier WP and every later lane commit printed
``ACTIVE_WP_CONTEXT_STALE``. The native ``spec-kitty implement`` flow refreshed
the context on reuse; the orchestrator path now routes through the same helper.

Drives the real CLI command against a real coordination-topology git repo:
WP01 is approved with a materialized lane worktree + workspace context (the
state a prior native ``implement`` leaves behind), then WP02 is started into
the same lane via the orchestrator API. Asserts the context follows WP02 and
the pre-commit guard's active-WP resolver emits no stale warning.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.workspace.context import WorkspaceContext, save_context

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "lane-reuse"
MID8 = "01KREUSE"
MISSION_ID = MID8 + "0" * 18
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
LANE_BRANCH = f"{COORD_BRANCH}-lane-c"

_WP_FILE = "---\nwork_package_id: {wp}\ntitle: Test {wp}\ndependencies: []\nsubtasks: []\nowned_files:\n  - src/{wp_lower}/**\n---\n\n# {wp}\n"


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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_DIRNAME,
        mission_id=MISSION_ID,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-c",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-06-20T00:00:00+00:00",
        computed_from="test",
    )


def _seed_events_on_coord(repo: Path, events: list[StatusEvent]) -> None:
    """Record status events in the mission's materialized coord worktree.

    The worktree is left in place (``.worktrees/<mission>-coord``) — the real
    mission shape — so the canonical-status read the pre-commit guard performs
    resolves the coordination surface instead of degrading to a primary
    checkout that never carried the event log.
    """
    from specify_cli.coordination.status_service import (
        EventLogWriteContract,
        append_event_log,
    )

    worktree = repo / ".worktrees" / f"{MISSION_DIRNAME}-coord"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    for event in events:
        append_event_log(
            EventLogWriteContract.coordination_transaction_append(worktree / "kitty-specs" / MISSION_DIRNAME),
            event,
        )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "seed status events")


def _event(n: int, wp_id: str, to_lane: Lane, from_lane: Lane) -> StatusEvent:
    return StatusEvent(
        event_id=f"01SEED{n:019d}",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-06-19T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


@pytest.fixture
def coord_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "topology": "lanes_with_coord",
                "coordination_branch": COORD_BRANCH,
                "target_branch": "main",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for wp in ("WP01", "WP02"):
        (feature_dir / "tasks" / f"{wp}.md").write_text(_WP_FILE.format(wp=wp, wp_lower=wp.lower()), encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 Test WP01\n\n- [x] T001 subtask for WP01\n\n## WP02 Test WP02\n\n- [x] T001 subtask for WP02\n",
        encoding="utf-8",
    )
    write_lanes_json(feature_dir, _manifest())
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", COORD_BRANCH)

    # WP01: planned straight through to approved (prior lane resident, done).
    # WP02: planned (ready to be claimed by the orchestrator).
    _seed_events_on_coord(
        repo,
        [
            _event(1, "WP01", Lane.PLANNED, Lane.GENESIS),
            _event(2, "WP01", Lane.CLAIMED, Lane.PLANNED),
            _event(3, "WP01", Lane.IN_PROGRESS, Lane.CLAIMED),
            _event(4, "WP01", Lane.FOR_REVIEW, Lane.IN_PROGRESS),
            _event(5, "WP01", Lane.IN_REVIEW, Lane.FOR_REVIEW),
            _event(6, "WP01", Lane.APPROVED, Lane.IN_REVIEW),
            _event(7, "WP02", Lane.PLANNED, Lane.GENESIS),
        ],
    )

    # The lane worktree + workspace context WP01's native implement left behind.
    _git(repo, "branch", LANE_BRANCH, COORD_BRANCH)
    lane_worktree = repo / ".worktrees" / f"{MISSION_DIRNAME}-lane-c"
    _git(repo, "worktree", "add", "-q", str(lane_worktree), LANE_BRANCH)
    (lane_worktree / "src" / "WP01").mkdir(parents=True)
    (lane_worktree / "src" / "WP01" / "impl.py").write_text("x = 1\n")
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "feat(WP01): implement")
    save_context(
        repo,
        WorkspaceContext(
            wp_id="WP01",
            mission_slug=MISSION_DIRNAME,
            worktree_path=f".worktrees/{MISSION_DIRNAME}-lane-c",
            branch_name=LANE_BRANCH,
            base_branch=COORD_BRANCH,
            base_commit=None,
            dependencies=[],
            created_at="2026-06-20T00:00:00+00:00",
            created_by="implement-command-lane",
            vcs_backend="git",
            lane_id="lane-c",
            lane_wp_ids=["WP01", "WP02"],
            current_wp="WP01",
            lane_test_env={},
        ),
    )
    return repo


def _start_implementation(repo: Path, wp: str) -> Any:
    with patch(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        return_value=repo,
    ):
        return runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                MISSION_DIRNAME,
                "--wp",
                wp,
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )


def test_start_implementation_refreshes_reused_lane_context(coord_repo: Path) -> None:
    result = _start_implementation(coord_repo, "WP02")
    assert result.exit_code == 0, result.output

    from specify_cli.workspace.context import (
        load_context,
        resolve_active_wp_for_branch,
    )

    ctx = load_context(coord_repo, f"{MISSION_DIRNAME}-lane-c")
    assert ctx is not None, "lane workspace context vanished"
    assert ctx.current_wp == "WP02", f"#3946 (F-78) regression: current_wp still {ctx.current_wp!r} after WP02 was started into the reused lane"
    assert ctx.wp_id == "WP02"

    resolved = resolve_active_wp_for_branch(coord_repo, LANE_BRANCH)
    assert resolved.wp_id == "WP02"
    stale = [w for w in resolved.warnings if "ACTIVE_WP_CONTEXT_STALE" in w]
    assert not stale, stale
