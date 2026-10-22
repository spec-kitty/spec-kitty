"""Runtime CLI guard family routing regressions for #3407/#3627."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next.runtime_bridge import _check_cli_guards
from runtime.next.runtime_bridge_cores import (
    _GUARD_TABLES,
    _evaluate_plan_guards,
    UnregisteredMissionFamilyError,
    evaluate_guards_strict,
)
from runtime.next.runtime_bridge_io import gather_artifact_presence
from specify_cli.mission import get_mission_type
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

WP_BLOCK_REVIEW_MESSAGE = "Not all work packages are approved or done"
CUSTOM_UNREGISTERED_FAMILY = "custom-onboarding-mission"
BUILT_IN_MISSION_TYPES = ("research", "documentation", "software-dev", "plan")


def _write_meta(feature_dir: Path, mission_type: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": mission_type}), encoding="utf-8")


def _seed_wp(feature_dir: Path, wp_id: str, lane: str) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\nlane: {lane}\ntitle: {wp_id} task\n---\n# {wp_id}\n",
        encoding="utf-8",
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{lane}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def test_check_cli_guards_routes_plan_review_to_plan_table(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-plan-feature"
    _write_meta(feature_dir, "plan")
    _seed_wp(feature_dir, "WP01", "planned")

    failures = _check_cli_guards("review", feature_dir)

    assert failures == []
    assert WP_BLOCK_REVIEW_MESSAGE not in failures


def test_plan_review_dispatch_reaches_real_plan_guard_entry(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-plan-feature"
    _write_meta(feature_dir, "plan")
    _seed_wp(feature_dir, "WP01", "planned")

    family = get_mission_type(feature_dir)
    snapshot = gather_artifact_presence(feature_dir, mission_family=family, step_id="review")

    assert family == "plan"
    assert evaluate_guards_strict(snapshot) == _evaluate_plan_guards(snapshot) == []


def test_software_dev_review_still_blocks_on_unapproved_wps(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-sd-feature"
    _write_meta(feature_dir, "software-dev")
    _seed_wp(feature_dir, "WP01", "planned")

    assert _check_cli_guards("review", feature_dir) == [WP_BLOCK_REVIEW_MESSAGE]


@pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES)
def test_builtin_mission_type_keys_match_guard_table(tmp_path: Path, mission_type: str) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-identity-feature"
    _write_meta(feature_dir, mission_type)

    resolved = get_mission_type(feature_dir)

    assert set(_GUARD_TABLES) == set(BUILT_IN_MISSION_TYPES)
    assert resolved == mission_type
    assert resolved in _GUARD_TABLES


def test_typeless_cli_guard_fails_closed(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-typeless-feature"
    feature_dir.mkdir(parents=True)

    assert get_mission_type(feature_dir) == ""
    with pytest.raises(UnregisteredMissionFamilyError):
        _check_cli_guards("review", feature_dir)


def _custom_wp_iteration_context(tmp_path: Path) -> rb.DecideNextContext:
    feature_dir = tmp_path / "kitty-specs" / "042-custom-mission"
    _write_meta(feature_dir, CUSTOM_UNREGISTERED_FAMILY)
    _seed_wp(feature_dir, "WP01", "approved")
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    return rb.DecideNextContext(
        agent="agent-x",
        mission_slug="042-custom-mission",
        result="success",
        repo_root=tmp_path,
        feature_dir=feature_dir,
        now="2026-08-22T00:00:00+00:00",
        mission_type=CUSTOM_UNREGISTERED_FAMILY,
        sync_emitter=cast(Any, object()),
        emitter_for_engine=cast(Any, object()),
        origin={"mission_tier": "custom", "mission_path": CUSTOM_UNREGISTERED_FAMILY},
        progress={"total_wps": 1},
        run_ref=rb.MissionRunRef(run_id="run-042", run_dir=str(run_dir), mission_key="042-custom-mission"),
        run_dir=run_dir,
        current_step_id="implement",
    )


def test_wp_iteration_guard_degrades_for_unregistered_family(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="runtime.next.runtime_bridge"):
        assert rb._dn_dependency_gate(_custom_wp_iteration_context(tmp_path)) is None

    messages = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any(CUSTOM_UNREGISTERED_FAMILY in message and "CLI guard path" in message and "empty" in message for message in messages), messages


def test_wp_iteration_guard_only_swallows_unregistered_family_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _custom_wp_iteration_context(tmp_path)

    def _raise_something_else(*_args: object, **_kwargs: object) -> list[str]:
        raise RuntimeError("unexpected guard evaluation failure")

    monkeypatch.setattr(rb, "_check_cli_guards", _raise_something_else)

    with pytest.raises(RuntimeError, match="unexpected guard evaluation failure"):
        rb._dn_dependency_gate(ctx)
