"""Every claim path records the claiming agent; an API move to ``planned`` releases it (#5781, #7644).

Driven through the real ``orchestrator-api`` and ``agent status`` Typer apps. Before #5781 the
orchestrator claims wrote the raw ``--policy`` dictionary as the claim event's
``policy_metadata`` (no ``agent`` key), so the reduced snapshot showed no owner and the host
``move-task`` ownership guard never applied. ``agent status emit --to claimed`` wrote no sidecar
at all. Before #7644 ``orchestrator-api transition --to planned`` left the previous claim holder
in the ``agent``/``shell_pid`` slots, where ``move-task --to planned`` releases them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app as status_app
from specify_cli.orchestrator_api.commands import app
from specify_cli.status import reduce
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import Lane, TransitionRequest
from specify_cli.status.store import read_event_stream, read_events
from tests.agent.test_orchestrator_commands_integration import _make_mission, _valid_policy_json
from tests.integration.coord_topology_fixture import FlatTopologyContext, flat_topology_mission

# Re-exported so pytest discovers the flat-topology fixture in this directory.
__all__ = ["flat_topology_mission"]

pytestmark = pytest.mark.git_repo

runner = CliRunner()

_SLUG = "099-test-mission"


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


def _invoke(repo_root: Path, *args: str) -> dict[str, Any]:
    with patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo_root):
        result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    envelope: dict[str, Any] = json.loads(result.output)
    assert envelope["success"] is True, envelope
    return envelope


def _wp01(mission_dir: Path) -> dict[str, Any]:
    stream = read_event_stream(mission_dir)
    state: dict[str, Any] = reduce(stream.transitions, stream.annotations).work_packages["WP01"]
    return state


def _claim_event_metadata(mission_dir: Path) -> dict[str, Any]:
    claims = [e for e in read_events(mission_dir) if e.wp_id == "WP01" and Lane(e.to_lane) == Lane.CLAIMED]
    assert claims, "no claim event recorded"
    metadata: dict[str, Any] = dict(claims[-1].policy_metadata or {})
    return metadata


def test_start_implementation_records_the_claiming_agent(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    _invoke(repo_root, "start-implementation", "--mission", _SLUG, "--wp", "WP01", "--actor", "claude", "--policy", _valid_policy_json())

    assert _wp01(mission_dir)["agent"] == "claude"
    metadata = _claim_event_metadata(mission_dir)
    assert metadata["agent"] == "claude"
    # The orchestrator policy still rides the claim event beside the agent.
    assert metadata["orchestrator_id"] == "test-orch"
    # There is no live shell behind an API claim: no pid is fabricated.
    assert "shell_pid" not in metadata


def test_transition_to_claimed_records_the_claiming_agent(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    _invoke(repo_root, "transition", "--mission", _SLUG, "--wp", "WP01", "--to", "claimed", "--actor", "claude", "--policy", _valid_policy_json())

    assert _wp01(mission_dir)["agent"] == "claude"
    assert _claim_event_metadata(mission_dir)["agent"] == "claude"


def test_status_emit_to_claimed_records_the_claiming_agent(tmp_path: Path) -> None:
    _repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    repo_root = mission_dir.parent.parent

    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo_root),
        patch("specify_cli.cli.commands.agent.status.get_main_repo_root", return_value=repo_root),
    ):
        result = runner.invoke(status_app, ["emit", "WP01", "--to", "claimed", "--actor", "claude", "--mission", _SLUG])

    assert result.exit_code == 0, result.output
    assert _wp01(mission_dir)["agent"] == "claude"
    assert _claim_event_metadata(mission_dir)["agent"] == "claude"


def _host_shaped_claim(mission_dir: Path, agent: str) -> None:
    """The claim a host ``agent action implement`` writes: the agent and a live shell pid."""
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission_dir,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane="claimed",
            actor=agent,
            policy_metadata={"agent": agent, "shell_pid": 4242},
        )
    )
    emit_status_transition(
        TransitionRequest(feature_dir=mission_dir, mission_slug=_SLUG, wp_id="WP01", to_lane="in_progress", actor=agent, workspace_context="worktree:x")
    )


def test_transition_to_planned_releases_the_claim_and_keeps_the_implementer_of_record(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    _host_shaped_claim(mission_dir, "claude")
    assert _wp01(mission_dir)["agent"] == "claude"
    assert _wp01(mission_dir)["shell_pid"] == 4242

    _invoke(repo_root, "transition", "--mission", _SLUG, "--wp", "WP01", "--to", "planned", "--actor", "orch", "--note", "rolled back")

    state = _wp01(mission_dir)
    assert state["lane"] == "planned"
    assert not state.get("agent")
    assert not state.get("shell_pid")
    assert not state.get("shell_pid_created_at")
    # #4786: the release never erases who implemented the WP.
    assert state.get("implementer_of_record") == "claude"


def test_after_an_api_rollback_another_implementer_claims_unforced(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    _host_shaped_claim(mission_dir, "claude")
    _invoke(repo_root, "transition", "--mission", _SLUG, "--wp", "WP01", "--to", "planned", "--actor", "orch", "--note", "rolled back")

    _invoke(repo_root, "start-implementation", "--mission", _SLUG, "--wp", "WP01", "--actor", "codex", "--policy", _valid_policy_json())

    state = _wp01(mission_dir)
    assert state["lane"] == "in_progress"
    assert state["actor"] == "codex"
    assert state["implementer_of_record"] == "codex"
    # The new claim event records its agent through the shared sidecar.
    assert _claim_event_metadata(mission_dir)["agent"] == "codex"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#7794: spec_kitty_events.diary.reduce_parsed folds every annotation after every transition, "
        "so the rollback's claim release also clears the slots the LATER claim set. Same for move-task."
    ),
)
def test_after_an_api_rollback_the_new_claim_holds_the_agent_slot(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    _host_shaped_claim(mission_dir, "claude")
    _invoke(repo_root, "transition", "--mission", _SLUG, "--wp", "WP01", "--to", "planned", "--actor", "orch", "--note", "rolled back")

    _invoke(repo_root, "start-implementation", "--mission", _SLUG, "--wp", "WP01", "--actor", "codex", "--policy", _valid_policy_json())

    assert _wp01(mission_dir)["agent"] == "codex"


def test_a_policy_agent_key_cannot_name_the_claimant(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    policy = {**json.loads(_valid_policy_json()), "agent": "spoof"}

    _invoke(repo_root, "start-implementation", "--mission", _SLUG, "--wp", "WP01", "--actor", "claude", "--policy", json.dumps(policy))

    assert _wp01(mission_dir)["agent"] == "claude"
    assert _claim_event_metadata(mission_dir)["agent"] == "claude"


# ---------------------------------------------------------------------------
# Host re-claim after an API rollback, on a real git Mission (WP prompt, review B2)
# ---------------------------------------------------------------------------


def _host_implement(ctx: FlatTopologyContext, agent: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", "agent", "action", "implement", "WP01", "--agent", agent, "--mission", ctx.slug],
        cwd=ctx.repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit_all(ctx: FlatTopologyContext, message: str) -> None:
    subprocess.run(["git", "-C", str(ctx.repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(ctx.repo), "commit", "-qm", message, "--allow-empty"], check=True, capture_output=True)


def _host_claimed_then_api_rolled_back(ctx: FlatTopologyContext) -> None:
    """``claude`` claims through host implement; an orchestrator then rolls WP01 back to planned."""
    from specify_cli.analysis_report import write_analysis_report

    seed = {
        "event_id": "01M04SEEDPLANNEDGENESIS001",
        "mission_slug": ctx.slug,
        "wp_id": "WP01",
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "finalize-tasks",
        "force": False,
        "execution_mode": "direct_repo",
    }
    ctx.status_events_path.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    feature_dir = ctx.primary_feature_dir
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    write_analysis_report(feature_dir=feature_dir, repo_root=ctx.repo, body="# Analysis\n\nPASS\n", analyzer_agent="test")
    _commit_all(ctx, "fixture: planned WP01 with a recorded analysis")

    first = _host_implement(ctx, "claude")
    assert first.returncode == 0, first.stdout + first.stderr
    _invoke(ctx.repo, "transition", "--mission", ctx.slug, "--wp", "WP01", "--to", "planned", "--actor", "orch", "--note", "rolled back")
    _commit_all(ctx, "fixture: API rollback")


def test_after_an_api_rollback_host_implement_claims_unforced(flat_topology_mission: FlatTopologyContext) -> None:
    ctx = flat_topology_mission
    _host_claimed_then_api_rolled_back(ctx)
    released = _wp01(ctx.primary_feature_dir)
    assert not released.get("agent")
    assert not released.get("shell_pid")

    second = _host_implement(ctx, "codex")

    assert second.returncode == 0, second.stdout + second.stderr
    state = _wp01(ctx.primary_feature_dir)
    assert state["lane"] == "in_progress"
    assert state["implementer_of_record"] == "codex"
    assert _claim_event_metadata(ctx.primary_feature_dir)["agent"] == "codex"
    reclaim = [e for e in read_events(ctx.primary_feature_dir) if e.wp_id == "WP01" and Lane(e.to_lane) == Lane.CLAIMED][-1]
    assert reclaim.force is False


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "#7794, a regression on this path from the #7644 release: before it, an API rollback released nothing "
        "(the old holder stayed bound) and a host re-claim set agent/shell_pid; now the release folds after the "
        "later host claim and clears them, as it already did after move-task --to planned"
    ),
)
def test_after_an_api_rollback_the_host_re_claim_holds_the_live_claim_slots(flat_topology_mission: FlatTopologyContext) -> None:
    ctx = flat_topology_mission
    _host_claimed_then_api_rolled_back(ctx)

    second = _host_implement(ctx, "codex")

    assert second.returncode == 0, second.stdout + second.stderr
    state = _wp01(ctx.primary_feature_dir)
    assert state["agent"] == "codex"
    assert state["shell_pid"]


def test_an_api_claimed_wp_meets_the_host_ownership_guard(flat_topology_mission: FlatTopologyContext) -> None:
    """The point of claim parity (#5781, operator ruling R28): an API claim names an owner, so a
    host ``move-task`` by a different tool is refused like it is for a host-claimed WP."""
    ctx = flat_topology_mission
    feature_dir = ctx.primary_feature_dir
    seed = {
        "event_id": "01M04SEEDPLANNEDGENESIS001",
        "mission_slug": ctx.slug,
        "wp_id": "WP01",
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "finalize-tasks",
        "force": False,
        "execution_mode": "direct_repo",
    }
    ctx.status_events_path.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    _commit_all(ctx, "fixture: planned WP01")
    _invoke(ctx.repo, "transition", "--mission", ctx.slug, "--wp", "WP01", "--to", "claimed", "--actor", "claude", "--policy", _valid_policy_json())
    assert _wp01(feature_dir)["agent"] == "claude"
    _commit_all(ctx, "fixture: API claim")

    moved = subprocess.run(
        [sys.executable, "-m", "specify_cli", "agent", "tasks", "move-task", "WP01", "--to", "blocked", "--agent", "codex", "--mission", ctx.slug, "--note", "x"],
        cwd=ctx.repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert moved.returncode != 0, moved.stdout + moved.stderr
    assert "claude" in (moved.stdout + moved.stderr)
    assert _wp01(feature_dir)["lane"] == "claimed"
