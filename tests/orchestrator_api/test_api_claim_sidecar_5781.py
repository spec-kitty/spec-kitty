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
from specify_cli.status.store import read_events
from tests.agent.test_orchestrator_commands_integration import _make_mission, _valid_policy_json

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
    state: dict[str, Any] = reduce(read_events(mission_dir)).work_packages["WP01"]
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
    assert state["agent"] == "codex"
    # The new claim carries no pid, and the old holder's pid is gone.
    assert not state.get("shell_pid")
