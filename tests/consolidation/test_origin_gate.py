"""Rendering and wiring units of ``consolidation.origin_gate`` (#5780).

The verdict engine and policy are covered by ``tests/git/test_origin_freshness*``;
these pin what the executor-side wrapper adds: lane selection inputs, the
coordination ``local_missing`` pass-through, the refusal rendering with exit 1,
and warn-mode output. The wrapper is exercised at its own boundary (the
freshness check and the seam are replaced), never by reordering assertions.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from mission_runtime import MissionTopology
from specify_cli.consolidation import origin_gate
from specify_cli.git import origin_gate as shared_gate
from specify_cli.consolidation.state import ConsolidationState, MergeAmbiguousStateError
from specify_cli.git.origin_freshness import FreshnessState, FreshnessVerdict, MissionFreshness
from specify_cli.lanes.persistence import CorruptLanesError

pytestmark = pytest.mark.fast

_SLUG = "terminus-01M5001A"
_COORD = "kitty/mission-terminus-01M5001A"
_LANE = "kitty/mission-terminus-01M5001A-lane-a"


def _verdict(branch: str, state: FreshnessState, *, behind: int = 0) -> FreshnessVerdict:
    return FreshnessVerdict(branch=branch, remote="origin", state=state, behind=behind, remote_sha="a" * 40)


def _seam(tmp_path: Path) -> Any:
    return SimpleNamespace(repo_root=tmp_path, mission_slug=_SLUG, read_dir=lambda kind: tmp_path)


class _Console:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, text: str, **_: object) -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def console(monkeypatch: pytest.MonkeyPatch) -> _Console:
    fake = _Console()
    monkeypatch.setattr(origin_gate, "console", fake)
    return fake


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    """Boundary stubs: the freshness check result, topology, record presence and checkout holder."""
    state = SimpleNamespace(
        freshness=MissionFreshness(evidence=_verdict(_COORD, FreshnessState.UP_TO_DATE), lanes=[]),
        coordination=False,
        record=False,
        holders=[],
        calls=[],
    )

    def fake_check(repo: Path, slug: str, *, lane_branches: list[str], owned: object = None) -> MissionFreshness:
        state.calls.append(list(lane_branches))
        result: MissionFreshness = state.freshness
        return result

    monkeypatch.setattr(shared_gate, "check_mission_branches", fake_check)
    monkeypatch.setattr(origin_gate, "_lane_branches", lambda seam: [_LANE])
    monkeypatch.setattr(shared_gate, "resolve_topology", lambda repo, slug: MissionTopology.COORD if state.coordination else MissionTopology.LANES)
    monkeypatch.setattr(origin_gate, "_merge_record_may_exist", lambda seam: state.record)
    monkeypatch.setattr(shared_gate, "worktrees_with_branch_checked_out", lambda repo, branch: state.holders)
    monkeypatch.delenv("SPEC_KITTY_ORIGIN_CHECK", raising=False)
    return state


def _run(tmp_path: Path, origin_check: str | None = None) -> None:
    origin_gate.check_origin_before_status_dir(tmp_path, _seam(tmp_path), origin_check)


def test_up_to_date_checks_once_and_prints_nothing(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    _run(tmp_path)
    assert stub.calls == [[_LANE]]
    assert console.lines == []


def test_stale_status_evidence_prints_the_refusal_and_exits_one(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.BEHIND, behind=2), lanes=[])
    stub.holders = [tmp_path / "coord-wt"]
    with pytest.raises(typer.Exit) as raised:
        _run(tmp_path)
    assert raised.value.exit_code == 1
    assert console.text.startswith("ORIGIN_STATUS_STALE")
    assert f"git -C {tmp_path / 'coord-wt'} pull origin {_COORD}" in console.text


def test_stale_lane_refuses_with_the_lane_code(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.UP_TO_DATE), lanes=[_verdict(_LANE, FreshnessState.BEHIND, behind=1)])
    with pytest.raises(typer.Exit):
        _run(tmp_path)
    assert console.text.startswith("ORIGIN_LANE_STALE")


def test_unreachable_names_the_opt_out(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=FreshnessVerdict(_COORD, "origin", FreshnessState.UNREACHABLE, detail="timeout"), lanes=[])
    with pytest.raises(typer.Exit):
        _run(tmp_path)
    assert "ORIGIN_UNREACHABLE" in console.text
    assert "--origin-check warn" in console.text


def test_a_merge_record_puts_abort_first_in_the_remedy(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.BEHIND, behind=1), lanes=[])
    stub.record = True
    with pytest.raises(typer.Exit):
        _run(tmp_path)
    assert "spec-kitty consolidate --abort" in console.text


def test_coordination_evidence_only_on_the_remote_passes_through(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.LOCAL_MISSING), lanes=[])
    stub.coordination = True
    _run(tmp_path)
    assert console.lines == []


def test_non_coordination_evidence_missing_locally_refuses(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict("develop", FreshnessState.LOCAL_MISSING), lanes=[])
    stub.coordination = False
    with pytest.raises(typer.Exit):
        _run(tmp_path)
    assert "ORIGIN_STATUS_STALE" in console.text


def test_coordination_pass_through_still_refuses_a_stale_lane(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(
        evidence=_verdict(_COORD, FreshnessState.LOCAL_MISSING),
        lanes=[_verdict(_LANE, FreshnessState.DIVERGED, behind=1)],
    )
    stub.coordination = True
    with pytest.raises(typer.Exit):
        _run(tmp_path)
    assert "ORIGIN_LANE_STALE" in console.text
    assert "ORIGIN_STATUS_STALE" not in console.text


def test_warn_flag_prints_warnings_naming_the_source_and_returns(stub: SimpleNamespace, console: _Console, tmp_path: Path) -> None:
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.BEHIND, behind=3), lanes=[])
    _run(tmp_path, "warn")
    assert "ORIGIN_STATUS_STALE" in console.text
    assert "source: flag" in console.text
    assert "continuing" in console.text


def test_warn_environment_names_the_environment(stub: SimpleNamespace, console: _Console, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPEC_KITTY_ORIGIN_CHECK", "warn")
    stub.freshness = MissionFreshness(evidence=_verdict(_COORD, FreshnessState.BEHIND, behind=3), lanes=[])
    _run(tmp_path)
    assert "source: environment" in console.text


def test_unknown_environment_value_enforces_and_warns(stub: SimpleNamespace, console: _Console, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPEC_KITTY_ORIGIN_CHECK", "sometimes")
    _run(tmp_path)
    assert "sometimes" in console.text


# --- lane selection inputs ---------------------------------------------------------------


def test_lane_branches_are_empty_without_a_readable_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(origin_gate, "read_lanes_json", lambda directory: None)
    assert origin_gate._lane_branches(_seam(tmp_path)) == []

    def corrupt(directory: Path) -> None:
        raise CorruptLanesError("bad")

    monkeypatch.setattr(origin_gate, "read_lanes_json", corrupt)
    assert origin_gate._lane_branches(_seam(tmp_path)) == []


def test_lane_branches_pass_the_resume_progress_to_the_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}
    manifest = object()
    monkeypatch.setattr(origin_gate, "read_lanes_json", lambda directory: manifest)
    monkeypatch.setattr(origin_gate, "_completed_wps", lambda seam: frozenset({"WP01"}))

    def select(repo: Path, slug: str, given: object, *, completed_wps: frozenset[str]) -> list[str]:
        seen.update(manifest=given, completed=completed_wps)
        return [_LANE]

    monkeypatch.setattr(origin_gate, "approved_lane_branches", select)
    assert origin_gate._lane_branches(_seam(tmp_path)) == [_LANE]
    assert seen == {"manifest": manifest, "completed": frozenset({"WP01"})}


def _stub_identity(monkeypatch: pytest.MonkeyPatch, mission_id: str | None) -> None:
    monkeypatch.setattr(origin_gate, "resolve_mission_identity", lambda directory: SimpleNamespace(mission_id=mission_id))


def test_completed_wps_come_from_the_persisted_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_identity(monkeypatch, "01M5001A" + "0" * 18)
    record = ConsolidationState(mission_id="x", mission_slug=_SLUG, target_branch="main", wp_order=["WP01", "WP02"], completed_wps=["WP01"])
    monkeypatch.setattr(origin_gate, "load_state", lambda repo, mission_id: record)
    assert origin_gate._completed_wps(_seam(tmp_path)) == frozenset({"WP01"})


def test_completed_wps_fall_back_to_the_slug_key_and_to_empty_without_a_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_identity(monkeypatch, None)
    keys: list[object] = []

    def load(repo: Path, mission_id: object) -> None:
        keys.append(mission_id)

    monkeypatch.setattr(origin_gate, "load_state", load)
    assert origin_gate._completed_wps(_seam(tmp_path)) == frozenset()
    assert keys == [_SLUG]


def test_unreadable_record_over_selects_instead_of_failing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_identity(monkeypatch, "id")

    def ambiguous(repo: Path, mission_id: object) -> None:
        raise MergeAmbiguousStateError("two records")

    monkeypatch.setattr(origin_gate, "load_state", ambiguous)
    assert origin_gate._completed_wps(_seam(tmp_path)) == frozenset()
