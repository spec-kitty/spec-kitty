"""Pre-review identity comes from PRIMARY metadata, independently of status."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands.agent.tasks_move_task import (
    _MoveTaskState,
    _mt_resolve_active_gate_bindings,
)
from tests._owned_fixtures import mint_test_fact
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.missions._read_path_resolver import coord_feature_dir
from specify_cli.review.gate_bindings import GateCoverage, resolve_gate_bindings_for_transition
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event
from tests._factories import provision_test_charter
from tests.lane_test_utils import write_mission_meta

pytestmark = [pytest.mark.git_repo]
_MISSION = "pre-review-identity"
_EDGE = "in_progress->for_review"


def _mission(root: Path, *, coord: bool, mission_type: str = "software-dev") -> tuple[Path, Path]:
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "topic"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base", "--allow-empty"],
        cwd=root,
        check=True,
    )
    primary = root / "kitty-specs" / _MISSION
    primary.mkdir(parents=True)
    meta_path = write_mission_meta(primary, mission_type=mission_type)
    meta = json.loads(meta_path.read_text())
    meta.update(topology="coord" if coord else "single_branch", target_branch="topic")
    status = primary
    if coord:
        meta["coordination_branch"] = "kitty/mission-pre-review-identity"
        status = coord_feature_dir(root, _MISSION, meta["mid8"])
        subprocess.run(
            ["git", "worktree", "add", "-q", "-b", meta["coordination_branch"], str(status.parents[1])],
            cwd=root,
            check=True,
        )
        status.mkdir(parents=True)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    append_event(
        status,
        StatusEvent(
            event_id="test-WP01-in-progress",
            mission_slug=_MISSION,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )
    provision_test_charter(root)
    return primary, status


def _state(root: Path, status: Path) -> _MoveTaskState:
    return _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=_MISSION,
        agent="testbot",
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=False,
        json_output=True,
        main_repo_root=root,
        repo_root=root,
        mission_slug=_MISSION,
        feature_dir=status,
        mt_feature_dir=status,
        old_lane=Lane.IN_PROGRESS,
        target_lane=Lane.FOR_REVIEW,
    )


@pytest.mark.parametrize("coord", [True, False], ids=["coord", "flat"])
def test_identity_selects_actual_active_gate_without_moving_status(tmp_path: Path, coord: bool) -> None:
    root = tmp_path / "repo"
    primary, status = _mission(root, coord=coord)
    st = _state(root, status)
    before = (status / "status.events.jsonl").read_bytes()
    assert not hasattr(st, "mission_type")
    assert placement_seam(root, _MISSION).read_dir(MissionArtifactKind.PRIMARY_METADATA) == primary
    assert placement_seam(root, _MISSION).read_dir(MissionArtifactKind.STATUS_STATE) == status
    assert (status / "meta.json").exists() is (not coord)
    expected = resolve_gate_bindings_for_transition(root, "software-dev", _EDGE)
    assert expected.coverage is GateCoverage.ACTIVE, expected.reason

    result = _mt_resolve_active_gate_bindings(st)

    assert result == expected, result.reason
    assert [binding.handler for binding in result.active] == ["spec-kitty-pre-review"]
    assert st.feature_dir == st.mt_feature_dir == status
    assert (status / "status.events.jsonl").read_bytes() == before
    assert (status / "meta.json").exists() is (not coord)


@pytest.mark.parametrize("mission_type", ["software-dev", "documentation"])
def test_coord_decoy_cannot_select_mission_type(tmp_path: Path, mission_type: str) -> None:
    root = tmp_path / "repo"
    _, status = _mission(root, coord=True, mission_type=mission_type)
    write_mission_meta(status, mission_type="research")
    expected = resolve_gate_bindings_for_transition(root, mission_type, _EDGE)
    assert expected.owning_contract_urn == f"mission_step_contract:{mission_type}/review"

    result = _mt_resolve_active_gate_bindings(_state(root, status))

    assert result == expected, result.reason


@pytest.mark.parametrize("primary_state", ["missing", "typeless", "corrupt"])
def test_invalid_primary_never_uses_valid_coord_decoy(tmp_path: Path, primary_state: str) -> None:
    root = tmp_path / "repo"
    primary, status = _mission(root, coord=True)
    write_mission_meta(status)
    meta_path = primary / "meta.json"
    if primary_state == "missing":
        meta_path.unlink()
    elif primary_state == "typeless":
        meta = json.loads(meta_path.read_text())
        del meta["mission_type"]
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
    else:
        meta_path.write_text("{broken", encoding="utf-8")
    st = _state(root, status)

    if primary_state == "corrupt":
        with pytest.raises(MissionMetaReadError):
            _mt_resolve_active_gate_bindings(st)
    else:
        result = _mt_resolve_active_gate_bindings(st)
        assert result.coverage is GateCoverage.NO_CONTRACT, result.reason
        assert result.owning_contract_urn == "mission_step_contract:/review"
        assert result.active == ()


def test_unactivated_primary_retains_no_coverage(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _, status = _mission(root, coord=True)
    (root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    result = _mt_resolve_active_gate_bindings(_state(root, status))
    assert result.coverage is GateCoverage.NOT_ACTIVATED, result.reason
    assert result.owning_contract_urn == "mission_step_contract:software-dev/review"
    assert result.active == ()


@pytest.mark.parametrize("owned_state", ["active", "unactivated", "missing", "corrupt"])
def test_owned_identity_and_activation_stay_on_selected_root(tmp_path: Path, owned_state: str) -> None:
    root = tmp_path / "primary"
    _mission(root, coord=False, mission_type="documentation")
    owned_root = tmp_path / "owned"
    primary, status = _mission(owned_root, coord=False)
    st = _state(root, status)
    st.owned = mint_test_fact(repository_root=root, owned_root=owned_root, mission_dir=primary, mission_slug=_MISSION, write_branch="topic")
    if owned_state == "unactivated":
        (owned_root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    elif owned_state == "missing":
        (primary / "meta.json").unlink()
    elif owned_state == "corrupt":
        (primary / "meta.json").write_text("{broken", encoding="utf-8")
    before = (status / "status.events.jsonl").read_bytes()

    if owned_state == "corrupt":
        with pytest.raises(MissionMetaReadError):
            _mt_resolve_active_gate_bindings(st)
    else:
        result = _mt_resolve_active_gate_bindings(st)
        expected_type = "" if owned_state == "missing" else "software-dev"
        expected = resolve_gate_bindings_for_transition(owned_root, expected_type, _EDGE)
        assert result == expected, result.reason
        assert (
            result.coverage
            is {
                "active": GateCoverage.ACTIVE,
                "unactivated": GateCoverage.NOT_ACTIVATED,
                "missing": GateCoverage.NO_CONTRACT,
            }[owned_state]
        )
    assert st.feature_dir == st.mt_feature_dir == status
    assert (status / "status.events.jsonl").read_bytes() == before
