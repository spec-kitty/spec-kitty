"""A finalized software-dev board without ``lanes.json`` is a structured block (ruling plan.next.missing_lanes_fold).

Mission ``next-lifecycle-integrity-01M77BWP`` wrap-up fold. A finalized board whose WP step
needs a workspace resolves it through ``lanes.json``; with the manifest deleted the board
dispatch raised an uncaught ``MissingLanesError`` (exit 1, empty stdout). Advancing ``next``
now answers ``kind=blocked`` ``LANES_MANIFEST_MISSING`` carrying the error's own message and
the one runnable remedy: ``finalize-tasks`` before execution has begun, ``doctor
mission-state --fix`` once any WP has left ``planned``. Where the never-rewind gate applies
(no run, an untouched run, a stale planning run) the answer starts or advances no run and
records only the CLI's one ``MissionNextInvoked`` row.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from runtime.next.decision import DecisionKind
from specify_cli.status.models import Lane
from tests.next.test_finished_board_gate_7553 import (
    _board,
    _bridge,
    _commit,
    _gated_bridge_call,
    _gated_cli_call,
    _run_position,
    _seed_run_at,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

_LANES_MISSING = "LANES_MANIFEST_MISSING"


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture stages no charter; the preflight is not what these cells exercise."""
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    passed = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort", lambda *_a, **_k: passed)
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only", lambda *_a, **_k: passed)


def _drop_lanes(repo: Path, feature_dir: Path) -> None:
    (feature_dir / "lanes.json").unlink()
    _commit(repo, "lose lanes.json")


def _finalize_command(slug: str) -> str:
    return f"spec-kitty agent mission finalize-tasks --mission {slug}"


def _doctor_command(slug: str) -> str:
    return f"spec-kitty doctor mission-state --fix --mission {slug}"


def _assert_lanes_missing(payload: dict[str, object], command: str) -> None:
    assert payload["kind"] == DecisionKind.blocked, payload
    assert payload["error_code"] == _LANES_MISSING, payload
    assert payload["next_command"] == command, payload
    reason = str(payload["reason"])
    assert "lanes.json is required" in reason, payload
    assert "finalize-tasks" in reason and "doctor mission-state --fix" in reason, payload


def test_first_contact_without_lanes_is_blocked_with_the_finalize_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    _drop_lanes(repo, feature_dir)

    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_lanes_missing(payload, _finalize_command(slug))
    assert payload["mission_state"] == "implement", payload


def test_execution_begun_without_lanes_is_blocked_with_the_doctor_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.PLANNED})
    _drop_lanes(repo, feature_dir)

    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_lanes_missing(payload, _doctor_command(slug))


def test_review_dispatch_without_lanes_is_blocked(tmp_path: Path) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.FOR_REVIEW})
    _drop_lanes(repo, feature_dir)

    decision = _gated_bridge_call(repo, slug)

    _assert_lanes_missing(decision.to_dict(), _doctor_command(slug))
    assert decision.mission_state == "review"
    assert decision.suppress_step_pairing is True


@pytest.mark.parametrize("stale_step", ["specify", "plan"])
def test_stale_planning_run_without_lanes_is_blocked_and_left_unchanged(stale_step: str, tmp_path: Path) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    run_dir = _seed_run_at(repo, slug, stale_step)
    position = _run_position(run_dir)
    _drop_lanes(repo, feature_dir)

    decision = _gated_bridge_call(repo, slug, "failed")

    _assert_lanes_missing(decision.to_dict(), _finalize_command(slug))
    assert decision.run_id is not None
    assert _run_position(run_dir) == position


def test_front_phase_without_lanes_is_blocked_when_the_gate_does_not_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The front phase's own catch: a gate that falls through still never raises the error out."""
    from runtime.next import runtime_bridge as bridge

    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    _drop_lanes(repo, feature_dir)
    monkeypatch.setattr(bridge, "_dn_never_rewind_gate", lambda *_a, **_k: None)

    decision = _bridge(repo, slug)

    _assert_lanes_missing(decision.to_dict(), _finalize_command(slug))
    assert decision.suppress_step_pairing is True


def test_execution_has_begun_reads_any_lane_past_planned() -> None:
    from runtime.next import runtime_bridge as bridge
    from runtime.next.board_status import BoardStatus

    def board(*lanes: Lane) -> BoardStatus:
        return BoardStatus(lanes={f"WP0{i}": lane for i, lane in enumerate(lanes)}, wp_states={}, has_log=True, weighted_percentage=None, source="path")

    assert bridge._board_execution_has_begun(board(Lane.PLANNED, Lane.PLANNED)) is False
    assert bridge._board_execution_has_begun(board()) is False
    assert bridge._board_execution_has_begun(board(Lane.PLANNED, Lane.CANCELED)) is True
    assert bridge._board_execution_has_begun(cast("BoardStatus", None)) is False


def test_stale_planning_run_with_corrupt_lanes_is_a_named_block(tmp_path: Path) -> None:
    """G2: the gate falls through on a corrupt manifest; the front phase answers it, never a traceback."""
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    run_dir = _seed_run_at(repo, slug, "specify")
    position = _run_position(run_dir)
    (feature_dir / "lanes.json").write_text("{not json", encoding="utf-8")
    _commit(repo, "corrupt lanes.json")

    decision = _bridge(repo, slug)

    assert decision.kind == DecisionKind.blocked, decision.to_dict()
    assert "cannot be dispatched" in str(decision.reason), decision.to_dict()
    assert f"spec-kitty agent tasks status --mission {slug}" in str(decision.reason)
    assert decision.error_code != _LANES_MISSING
    assert _run_position(run_dir) == position


@pytest.mark.parametrize("error", ["corrupt-lanes", "unassigned-wp", "unreadable-file", "no-context"])
def test_front_phase_names_every_unresolvable_dispatch(error: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next import runtime_bridge as bridge
    from runtime.next import runtime_bridge_decision_mapping as mapping
    from tests.next.test_finished_board_gate_7553 import _unresolvable_error

    repo, slug, _ = _board(tmp_path, {"WP01": Lane.PLANNED})

    def _unresolvable(*_a: object, **_k: object) -> None:
        raise _unresolvable_error(error)

    monkeypatch.setattr(mapping, "_board_step_action", _unresolvable)
    monkeypatch.setattr(mapping, "_resolve_wp_board_action", _unresolvable)
    monkeypatch.setattr(bridge, "_dn_never_rewind_gate", lambda *_a, **_k: None)

    decision = _bridge(repo, slug)

    assert decision.kind == DecisionKind.blocked, decision.to_dict()
    assert "cannot be dispatched" in str(decision.reason), decision.to_dict()
