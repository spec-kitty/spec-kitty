"""#5573 refusal paths of a re-finalize that would move started work (WP03 T014).

Drives the real ``agent mission finalize-tasks`` command (Typer ``mission_app``,
in-process) over WP01's fixture: a ``lanes`` mission whose first finalize gives
lane-a = [WP01] (``a.py``) and lane-b = [WP02] (``b.py``).

* US2 AS2: ``--validate-only`` refuses exactly like a real run.
* US2 AS3-AS5: a removed started WP, a started WP changing kind and a malformed
  status log each refuse with their own reason; AS6 (absent log) proceeds.
* US2 AS7 and the ``started_wp_removed`` remedy: applying the printed remedy
  makes the next re-finalize succeed with every started WP on its lane.
* FR-008: a WP rejected back to ``planned`` and a lane with only a recorded
  work tip both stay frozen.
* FR-005: the refusal precedes every status writer; ``--refresh-planning-commit``
  never runs the preflight; FR-009: the validate-only preview reports the
  frozen lane ids.
* SC-003: every refusal leaves the planning and status files byte-identical
  and HEAD unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands.agent import mission_finalize
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.frontmatter import read_frontmatter, write_frontmatter
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import emit_status_transition
from tests.integration.test_refinalize_keeps_started_lanes import (
    _EVENTS,
    _WP_FILES,
    _add_wp03,
    _amend_overlap,
    _commit_amendment,
    _FinalizeResult,
    _first_json_object,
    _git,
    _Mission,
    _setup_mission,
    _snapshot,
    _spy_writers,
    _start,
    _topology,
    _wrap_everywhere,
    _write_wp,
    runner,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FROZEN = "LANE_MEMBERSHIP_FROZEN"


def _invoke(mission_slug: str, *extra: str, json_output: bool = True) -> _FinalizeResult:
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    args = ["finalize-tasks", "--mission", mission_slug, *extra, *(["--json"] if json_output else [])]
    result = runner.invoke(mission_app, args)
    payload = _first_json_object(result.output) if json_output else {}
    return _FinalizeResult(result.exit_code, payload, result.output)


@dataclass
class _Untouched:
    """SC-003 + FR-005 evidence around one refused run."""

    mission: _Mission
    before: dict[str, bytes] = field(default_factory=dict)
    head: str = ""

    def assert_untouched(self) -> None:
        assert _snapshot(self.mission) == self.before, "a refused re-finalize must not change any planning or status file"
        assert _git(self.mission.repo, "rev-parse", "HEAD") == self.head, "a refused re-finalize must not commit"


def _refuse(mission: _Mission, monkeypatch: pytest.MonkeyPatch, *extra: str, frozen: bool = True) -> _FinalizeResult:
    """Run a re-finalize expected to refuse; assert it wrote and committed nothing."""
    guard = _Untouched(mission, _snapshot(mission), _git(mission.repo, "rev-parse", "HEAD"))
    spy = _spy_writers(monkeypatch)

    result = _invoke(mission.slug, *extra)

    assert result.exit_code == 1, f"expected a refusal; output:\n{result.output}"
    if frozen:
        assert result.payload.get("error_code") == _FROZEN, result.payload
        assert str(result.payload.get("next_step") or "").strip(), result.payload
    assert spy.status_writes_to(mission.feature_dir) == [], "the refusal must come before any status event is written"
    assert spy.lanes_writes_to(mission.feature_dir) == [], "the refusal must come before lanes.json is written"
    guard.assert_untouched()
    return result


def _conflict(result: _FinalizeResult, reason: str) -> dict[str, Any]:
    conflicts = [c for c in result.payload.get("conflicts") or [] if c.get("reason") == reason]
    assert len(conflicts) == 1, result.payload
    return conflicts[0]


def _set_up_two_started_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Mission:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _add_wp03(mission)
    _commit_amendment(mission)
    return mission


def _wp_file(mission: _Mission, wp_id: str) -> Path:
    return mission.feature_dir / "tasks" / _WP_FILES[wp_id]


def _remove_wp02(mission: _Mission) -> dict[Path, bytes]:
    """Drop WP02's task file and ``tasks.md`` section; WP01 takes over FR-002. Returns the bytes to restore."""
    tasks_md = mission.feature_dir / "tasks.md"
    saved = {path: path.read_bytes() for path in (tasks_md, _wp_file(mission, "WP02"), _wp_file(mission, "WP01"))}
    _wp_file(mission, "WP02").unlink()
    text = tasks_md.read_text(encoding="utf-8")
    tasks_md.write_text(text[: text.index("## Work Package WP02")].rstrip() + "\n", encoding="utf-8")
    meta, body = read_frontmatter(_wp_file(mission, "WP01"))
    meta["requirement_refs"] = ["FR-001", "FR-002"]
    write_frontmatter(_wp_file(mission, "WP01"), meta, body)
    return saved


def _events(mission: _Mission) -> Iterator[dict[str, Any]]:
    for line in (mission.feature_dir / _EVENTS).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


# ---------------------------------------------------------------------------
# US2: refusals
# ---------------------------------------------------------------------------


def test_validate_only_refuses_like_a_real_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _set_up_two_started_collision(tmp_path, monkeypatch)

    result = _refuse(mission, monkeypatch, "--validate-only")

    assert result.payload.get("reason") == "started_lanes_collapsed"
    conflict = _conflict(result, "started_lanes_collapsed")
    assert conflict["wp_ids"] == ["WP01", "WP02"]
    assert conflict["recorded_lanes"] == ["lane-a", "lane-b"]


def test_console_refusal_names_each_conflict_and_its_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _set_up_two_started_collision(tmp_path, monkeypatch)

    result = _invoke(mission.slug, json_output=False)

    assert result.exit_code == 1, result.output
    assert "Cannot re-finalize: started work packages would change lane." in result.output
    assert "started_lanes_collapsed: WP01 (lane-a), WP02 (lane-b)" in result.output
    assert "Remedy: Remove the overlap that forces WP01 and WP02 into one lane" in result.output


def test_removed_started_wp_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _remove_wp02(mission)
    _commit_amendment(mission)

    result = _refuse(mission, monkeypatch)

    assert result.payload.get("reason") == "started_wp_removed"
    conflict = _conflict(result, "started_wp_removed")
    assert conflict["wp_ids"] == ["WP02"]
    assert conflict["recorded_lanes"] == ["lane-b"]
    assert "move-task WP02 --to canceled --mission" in conflict["remedy"]
    assert "without clearing" in conflict["remedy"]


def test_started_wp_changing_kind_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    plan_path = str((mission.feature_dir / "plan.md").relative_to(mission.repo))
    meta, body = read_frontmatter(_wp_file(mission, "WP02"))
    meta["execution_mode"] = "planning_artifact"
    meta["owned_files"] = [plan_path]
    meta["authoritative_surface"] = plan_path
    write_frontmatter(_wp_file(mission, "WP02"), meta, body)
    _commit_amendment(mission)

    result = _refuse(mission, monkeypatch)

    assert result.payload.get("reason") == "started_wp_kind_changed"
    conflict = _conflict(result, "started_wp_kind_changed")
    assert conflict["wp_ids"] == ["WP02"]
    assert conflict["recorded_lanes"] == ["lane-b"]


def _seed_started_then_append(mission: _Mission, line: str) -> None:
    _start(mission, "WP02", commit_work=False, in_progress=False)
    with (mission.feature_dir / _EVENTS).open("a", encoding="utf-8") as log:
        log.write(line)
    _commit_amendment(mission)


def test_malformed_status_log_refuses_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS5, fail-closed half: a corrupt line refuses with nothing written.

    The planning-side WP read (``read_wp_frontmatter`` resolves runtime fields
    from the same log) already fails closed on a corrupt line, ahead of the
    preflight, with its existing store error. That text is kept unchanged
    (C-003); the preflight's own ``status_unreadable`` refusal is pinned below.
    """
    mission = _setup_mission(tmp_path, monkeypatch)
    _seed_started_then_append(mission, "{corrupt\n")

    result = _refuse(mission, monkeypatch, frozen=False)

    assert "Invalid JSON on line" in str(result.payload.get("error")), result.payload


def test_unreadable_status_log_refuses_status_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS5: when the preflight cannot read the status history it refuses ``status_unreadable``."""
    from specify_cli.status import StoreError

    mission = _setup_mission(tmp_path, monkeypatch)
    _seed_started_then_append(mission, "")

    def _unreadable(_read_dir: Path) -> list[object]:
        raise StoreError("Invalid event structure on line 3: simulated")

    monkeypatch.setattr("specify_cli.status.read_events", _unreadable)

    result = _refuse(mission, monkeypatch)

    assert result.payload.get("reason") == "status_unreadable"
    conflict = _conflict(result, "status_unreadable")
    assert conflict["wp_ids"] == []
    assert "spec-kitty agent status validate --mission" in conflict["remedy"]


def test_absent_status_log_proceeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control for AS5: no log (and no lane allocated, so no tip) means nothing started."""
    mission = _setup_mission(tmp_path, monkeypatch)
    for name in (_EVENTS, "status.json"):
        (mission.feature_dir / name).unlink(missing_ok=True)
    _commit_amendment(mission)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]


# ---------------------------------------------------------------------------
# Remedies round-trip
# ---------------------------------------------------------------------------


def test_collapsed_remedy_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS7: move the shared path into a new WP03 that depends on both; the re-finalize then succeeds."""
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    tasks_md = mission.feature_dir / "tasks.md"
    original = {path: path.read_bytes() for path in (tasks_md, _wp_file(mission, "WP01"))}
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)
    _refuse(mission, monkeypatch)

    for path, data in original.items():
        path.write_bytes(data)
    _write_wp(mission.feature_dir, "WP03", ["b.py"], "FR-001", ["WP01", "WP02"])
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8") + "\n## Work Package WP03: Third\n\nRequirement refs: FR-001\n\n**Dependencies**: WP01, WP02\n",
        encoding="utf-8",
    )
    _commit_amendment(mission)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    lanes = {wp_id: lane_id for lane_id, wp_ids in _topology(after) for wp_id in wp_ids}
    assert lanes["WP01"] == "lane-a", _topology(after)
    assert lanes["WP02"] == "lane-b", _topology(after)
    assert "WP03" in lanes, _topology(after)


def test_removed_wp_remedy_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the task file and cancel the WP: it stays present and lane-eligible, so it keeps its lane.

    Finalize eligibility reads the retired frontmatter ``lane``, not the event
    log, so an event-log cancel does not retire the WP from lane inputs.
    """
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP02", commit_work=True, in_progress=True)
    saved = _remove_wp02(mission)
    _commit_amendment(mission)
    _refuse(mission, monkeypatch)

    for path, data in saved.items():
        path.write_bytes(data)
    emit_status_transition(mission.feature_dir, mission.slug, "WP02", "canceled", "test", reason="retired by the amendment")
    _commit_amendment(mission)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]
    assert allocate_lane_worktree(mission.repo, mission.slug, "WP02", after) == (started.worktree, started.branch)


# ---------------------------------------------------------------------------
# FR-008: history and tip evidence
# ---------------------------------------------------------------------------


def test_wp_rejected_back_to_planned_keeps_its_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    emit_status_transition(mission.feature_dir, mission.slug, "WP02", "planned", "test", reason="rejected back to planning")
    assert [e.get("to_lane") for e in _events(mission) if e.get("wp_id") == "WP02"][-1] == "planned"
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-b", ("WP02", "WP01"))], _topology(after)


def test_lane_work_tip_alone_freezes_the_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-008 fallback: WP02's lane is allocated (a work tip is recorded) but WP02 has no started event."""
    mission = _setup_mission(tmp_path, monkeypatch)
    _worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP02", mission.manifest)
    tips = _git(mission.repo, "for-each-ref", "--format=%(refname)", "refs/spec-kitty/lane-tip/").splitlines()
    assert f"refs/spec-kitty/lane-tip/{branch}" in tips, tips
    assert not [e for e in _events(mission) if e.get("wp_id") == "WP02" and e.get("to_lane") not in (None, "planned")]
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-b", ("WP02", "WP01"))], _topology(after)


# ---------------------------------------------------------------------------
# FR-005 ordering, skips and the FR-009 preview
# ---------------------------------------------------------------------------

_STATUS_WRITERS = ("_emit_tasks_started", "_emit_local_canonical_events", "_bootstrap_canonical_state_via_mission")


def _spy_status_writers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    for name in _STATUS_WRITERS:

        def _record(*_args: object, _name: str = name, **_kwargs: object) -> None:
            calls.append(_name)

        _wrap_everywhere(monkeypatch, getattr(mission_finalize, name), _record)
    return calls


def test_refusal_precedes_every_status_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _set_up_two_started_collision(tmp_path, monkeypatch)
    calls = _spy_status_writers(monkeypatch)

    _refuse(mission, monkeypatch)

    assert calls == [], f"the preflight must refuse before any status writer runs; ran: {calls}"


def test_status_writer_spies_are_live_positive_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _add_wp03(mission)
    _commit_amendment(mission)
    calls = _spy_status_writers(monkeypatch)

    result = _invoke(mission.slug)

    assert result.exit_code == 0, result.output
    assert set(calls) == set(_STATUS_WRITERS), calls


def test_refresh_planning_commit_never_runs_the_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _commit_amendment(mission)
    calls: list[str] = []
    _wrap_everywhere(monkeypatch, mission_finalize._preflight_frozen_lane_membership, lambda *_a, **_k: calls.append("preflight"))

    refresh = _invoke(mission.slug, "--refresh-planning-commit")
    assert refresh.exit_code == 0, refresh.output
    assert refresh.payload.get("result") == "success", refresh.payload
    assert calls == [], "a --refresh-planning-commit run never recomputes membership"

    plain = _invoke(mission.slug)
    assert plain.exit_code == 0, plain.output
    assert calls == ["preflight"], "positive control: a plain re-finalize runs the preflight once"


def test_validate_only_preview_reports_the_frozen_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-009: the preview reads back the previous manifest and honours the frozen membership."""
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)
    before = _snapshot(mission)

    result = _invoke(mission.slug, "--validate-only")

    assert result.exit_code == 0, result.output
    preview = result.payload["validation"]["lanes_preview"]
    assert preview["lane_ids"] == ["lane-b"], preview
    assert _snapshot(mission) == before
