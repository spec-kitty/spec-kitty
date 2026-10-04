"""Unit tests for the finalize-tasks frozen-lane preflight (#5573, WP03 T010-T013).

The finalize shell gathers the evidence WP02's pure constraint needs -- the
history-started set from the status log (fail-closed) and the recorded lane
work tips -- dry-runs ``compute_lanes`` with it before the first status write,
and renders a ``LANE_MEMBERSHIP_FROZEN`` refusal. Seams are patched on the
module that owns the lazily imported name (``specify_cli.status``,
``specify_cli.lanes.*``, ``specify_cli.coordination.surface_resolver``), never
on ``mission_finalize``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent import mission_finalize_commit as finalize_commit
from specify_cli.cli.commands.agent import mission_finalize_lanes as finalize_lanes
from specify_cli.lanes.compute import LaneMembershipFrozenError
from specify_cli.lanes.frozen_membership import REASON_PRECEDENCE, FrozenLaneMembership, MembershipConflictReason, conflict_for, remedy_for
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import StoreError, WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "frozen-preflight"
_EVENTS = "status.events.jsonl"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _lane(lane_id: str, *wp_ids: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=tuple(wp_ids), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _write_previous(planning_dir: Path, *lanes: ExecutionLane) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="qa-main",
        lanes=list(lanes),
        computed_at="2026-10-04T00:00:00+00:00",
        computed_from="dependency_graph+ownership",
    )
    write_lanes_json(planning_dir, manifest)
    return manifest


def _frontmatters(*wp_ids: str) -> dict[str, WPMetadata]:
    return {wp_id: WPMetadata(work_package_id=wp_id, title=wp_id) for wp_id in wp_ids}


def _event(wp_id: str, to_lane: str) -> SimpleNamespace:
    return SimpleNamespace(wp_id=wp_id, to_lane=to_lane)


def _code(owned: str) -> OwnershipManifest:
    return OwnershipManifest(execution_mode=WorkProductKind("code_change"), owned_files=(owned,), authoritative_surface=owned)


class _Recorder:
    """A callable that records its calls and returns (or raises) a fixed outcome."""

    def __init__(self, result: object = None, *, raises: BaseException | None = None) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self._result = result
        self._raises = raises

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.fixture
def status_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Resolve every status read to ``tmp_path / "status"`` (the coordination-aware resolver is patched)."""
    read_dir = tmp_path / "status"
    read_dir.mkdir()
    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
        lambda _repo_root, _slug: SimpleNamespace(read_dir=read_dir),
    )
    return read_dir


@pytest.fixture
def planning_dir(tmp_path: Path) -> Path:
    path = tmp_path / "kitty-specs" / _SLUG
    path.mkdir(parents=True)
    return path


def _with_events(monkeypatch: pytest.MonkeyPatch, status_dir: Path, events: Iterable[SimpleNamespace]) -> None:
    (status_dir / _EVENTS).write_text("{}\n", encoding="utf-8")
    listed = list(events)
    monkeypatch.setattr("specify_cli.status.read_events", lambda _read_dir: listed)


def _gather(planning_dir: Path, tmp_path: Path, *, present: Iterable[str] = ("WP01", "WP02"), eligible: Iterable[str] | None = None) -> FrozenLaneMembership:
    present_ids = tuple(present)
    return finalize_lanes._gather_frozen_lane_membership(
        planning_dir,
        tmp_path,
        _SLUG,
        wp_frontmatters=_frontmatters(*present_ids),
        eligible_wp_ids=frozenset(present_ids if eligible is None else eligible),
    )


def _assert_status_unreadable(excinfo: pytest.ExceptionInfo[LaneMembershipFrozenError]) -> None:
    error = excinfo.value
    assert error.error_code == "LANE_MEMBERSHIP_FROZEN"
    assert error.reason == "status_unreadable"
    assert [conflict.reason for conflict in error.conflicts] == ["status_unreadable"]
    assert error.conflicts[0].remedy == remedy_for("status_unreadable", ())
    assert error.__cause__ is not None, "the refusal must chain the underlying read failure"


# ---------------------------------------------------------------------------
# T010: _gather_frozen_lane_membership
# ---------------------------------------------------------------------------


def test_first_finalize_reads_no_status(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = _Recorder(raises=AssertionError("a first finalize must not resolve the status surface"))
    monkeypatch.setattr("specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor", resolver)
    tips = _Recorder(frozenset())
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path)

    assert frozen.is_empty
    assert resolver.calls == []
    assert tips.calls == []


def test_absent_log_means_nothing_history_started(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    monkeypatch.setattr("specify_cli.status.read_events", _Recorder(raises=AssertionError("an absent log must not be read")))
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", lambda _root: frozenset())

    frozen = _gather(planning_dir, tmp_path)

    assert not (status_dir / _EVENTS).exists()
    assert dict(frozen.bindings) == {}
    assert frozen.is_empty


def test_history_started_wps_are_bound_to_their_recorded_lanes(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "planned"), _event("WP02", "planned"), _event("WP02", "claimed")])
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", lambda _root: frozenset())

    frozen = _gather(planning_dir, tmp_path)

    assert dict(frozen.bindings) == {"WP02": "lane-b"}


def test_malformed_log_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, status_dir: Path) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    (status_dir / _EVENTS).write_text("{not json\n", encoding="utf-8")

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert isinstance(excinfo.value.__cause__, StoreError)


@pytest.mark.parametrize("failure", [UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), OSError("disk gone")])
def test_unreadable_log_refuses_status_unreadable(
    planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    (status_dir / _EVENTS).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("specify_cli.status.read_events", _Recorder(raises=failure))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert excinfo.value.__cause__ is failure


@pytest.mark.parametrize("failure", [FileNotFoundError("no status surface"), ValueError("ambiguous status surface")])
def test_unresolvable_status_surface_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    monkeypatch.setattr("specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor", _Recorder(raises=failure))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert excinfo.value.__cause__ is failure


def test_tip_listing_is_skipped_when_every_code_lane_has_a_started_member(
    planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"), _lane("lane-planning", "WP03"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress"), _event("WP02", "claimed")])
    tips = _Recorder(frozenset())
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path, present=("WP01", "WP02", "WP03"))

    assert tips.calls == [], "no code lane lacks a started member, so the tip fallback cannot change anything"
    assert dict(frozen.bindings) == {"WP01": "lane-a", "WP02": "lane-b"}


def test_tip_fallback_freezes_a_tipped_lane_without_history(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.compute import lane_created_branch

    previous = _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress")])
    tips = _Recorder(frozenset({lane_created_branch(previous, "lane-b")}))
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path)

    assert [args for args, _kwargs in tips.calls] == [(tmp_path,)]
    assert dict(frozen.bindings) == {"WP01": "lane-a", "WP02": "lane-b"}


def test_retired_wps_are_present_minus_eligible(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress"), _event("WP02", "in_progress")])
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", lambda _root: frozenset())

    frozen = _gather(planning_dir, tmp_path, present=("WP01", "WP02", "WP03"), eligible=("WP01", "WP03"))

    assert frozen.retired_wp_ids == frozenset({"WP02"})


# ---------------------------------------------------------------------------
# T011: _preflight_frozen_lane_membership
# ---------------------------------------------------------------------------


def _preflight(
    planning_dir: Path,
    tmp_path: Path,
    meta: dict[str, object] | None,
    *,
    lane_wp_manifests: dict[str, OwnershipManifest] | None = None,
    lane_wp_dependencies: dict[str, list[str]] | None = None,
) -> FrozenLaneMembership:
    return finalize_lanes._preflight_frozen_lane_membership(
        planning_dir,
        tmp_path,
        _SLUG,
        meta,
        "qa-main",
        lane_wp_manifests={"WP01": _code("a.py"), "WP02": _code("b.py")} if lane_wp_manifests is None else lane_wp_manifests,
        lane_wp_dependencies={"WP01": [], "WP02": []} if lane_wp_dependencies is None else lane_wp_dependencies,
        lane_wp_bodies={},
        wp_frontmatters=_frontmatters("WP01", "WP02"),
        eligible_wp_ids=frozenset({"WP01", "WP02"}),
    )


def test_single_branch_skips_the_evidence(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gather = _Recorder(raises=AssertionError("SINGLE_BRANCH has nothing to freeze"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", gather)

    frozen = _preflight(planning_dir, tmp_path, {"topology": "single_branch"})

    assert frozen.is_empty
    assert gather.calls == []


def test_empty_evidence_skips_the_dry_run(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership.empty()))
    compute = _Recorder(raises=AssertionError("nothing frozen: no dry run"))
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", compute)

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}).is_empty
    assert compute.calls == []


def test_missing_lane_inputs_skip_the_dry_run(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = FrozenLaneMembership(bindings={"WP01": "lane-a"})
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))
    compute = _Recorder(raises=AssertionError("the empty-input guard owns this case"))
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", compute)

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}, lane_wp_manifests={}, lane_wp_dependencies={}) == frozen
    assert compute.calls == []


def test_dry_run_threads_previous_lanes_and_frozen_and_writes_nothing(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    previous = _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    before = (planning_dir / "lanes.json").read_bytes()
    frozen = FrozenLaneMembership(bindings={"WP02": "lane-b"})
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))
    compute = _Recorder()
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", compute)

    result = _preflight(planning_dir, tmp_path, {"topology": "lanes", "mission_id": "01M444FMXXXXXXXXXXXXXXXXXX", "mission_branch": "kitty/m"})

    assert result == frozen
    assert len(compute.calls) == 1
    kwargs = compute.calls[0][1]
    assert kwargs["frozen"] == frozen
    assert kwargs["previous_lanes"] == previous
    assert kwargs["mission_id"] == "01M444FMXXXXXXXXXXXXXXXXXX"
    assert kwargs["mission_branch"] == "kitty/m"
    assert (planning_dir / "lanes.json").read_bytes() == before


def test_dry_run_frozen_refusal_propagates(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership(bindings={"WP01": "lane-a", "WP02": "lane-b"})))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _preflight(
            planning_dir,
            tmp_path,
            {"topology": "lanes"},
            lane_wp_manifests={
                "WP01": OwnershipManifest(execution_mode=WorkProductKind("code_change"), owned_files=("a.py", "b.py"), authoritative_surface="a.py"),
                "WP02": _code("b.py"),
            },
            lane_wp_dependencies={"WP01": ["WP02"], "WP02": []},
        )

    assert excinfo.value.reason == "started_lanes_collapsed"


def test_dry_run_defers_other_lane_failures_to_the_lane_write(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.compute import LaneComputationError

    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    frozen = FrozenLaneMembership(bindings={"WP01": "lane-a"})
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", _Recorder(raises=LaneComputationError("cycle")))

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}) == frozen


# ---------------------------------------------------------------------------
# T013: rendering
# ---------------------------------------------------------------------------


def _collapsed_error() -> LaneMembershipFrozenError:
    return LaneMembershipFrozenError((conflict_for("started_lanes_collapsed", {"WP01": "lane-a", "WP02": "lane-b"}),))


def test_json_envelope_carries_the_contract_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    error = _collapsed_error()

    finalize_commit._emit_finalize_error_with_revert_note(error, None, json_output=True)

    assert len(emitted) == 1
    payload = emitted[0]
    assert payload["error"] == str(error)
    assert payload["error_code"] == "LANE_MEMBERSHIP_FROZEN"
    assert payload["reason"] == "started_lanes_collapsed"
    assert payload["conflicts"] == [
        {
            "reason": "started_lanes_collapsed",
            "wp_ids": ["WP01", "WP02"],
            "recorded_lanes": ["lane-a", "lane-b"],
            "remedy": remedy_for("started_lanes_collapsed", ["WP01", "WP02"]),
        }
    ]
    assert payload["next_step"] == error.next_step


def test_console_names_each_conflict_and_its_remedy(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    printed: list[str] = []
    monkeypatch.setattr(mission_finalize, "console", SimpleNamespace(print=lambda text: printed.append(str(text))))
    error = _collapsed_error()

    finalize_commit._emit_finalize_error_with_revert_note(error, None, json_output=False)

    assert printed[0] == f"[red]Error:[/red] {error}"
    assert "  started_lanes_collapsed: WP01 (lane-a), WP02 (lane-b)" in printed
    assert f"  Remedy: {remedy_for('started_lanes_collapsed', ['WP01', 'WP02'])}" in printed


def test_console_status_unreadable_has_no_wp_list(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    printed: list[str] = []
    monkeypatch.setattr(mission_finalize, "console", SimpleNamespace(print=lambda text: printed.append(str(text))))

    finalize_commit._emit_finalize_error_with_revert_note(finalize_lanes._status_unreadable_error(), None, json_output=False)

    assert "  status_unreadable" in printed
    assert f"  Remedy: {remedy_for('status_unreadable', ())}" in printed


def test_other_errors_keep_their_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)

    finalize_commit._emit_finalize_error_with_revert_note(RuntimeError("boom"), None, json_output=True)

    assert emitted == [{"error": "boom"}]


# ---------------------------------------------------------------------------
# Remedy hygiene (contracts/lane-membership-frozen.md)
# ---------------------------------------------------------------------------

_DESTRUCTIVE = ("reset", "restore", "rm ", "--force", "delete")


@pytest.mark.parametrize("reason", REASON_PRECEDENCE)
@pytest.mark.parametrize("wp_ids", [(), ("WP02",), ("WP01", "WP02")])
def test_remedies_are_non_destructive(reason: MembershipConflictReason, wp_ids: tuple[str, ...]) -> None:
    remedy = remedy_for(reason, wp_ids)

    assert remedy.strip()
    assert [token for token in _DESTRUCTIVE if token in remedy] == []


def test_move_task_remedy_names_the_mission() -> None:
    remedy = remedy_for("started_wp_removed", ("WP02",))

    assert "move-task WP02" in remedy
    assert "--mission" in remedy
    assert "without clearing" in remedy
