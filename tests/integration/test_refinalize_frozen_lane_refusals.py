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
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands.agent import mission_finalize
from specify_cli.frontmatter import read_frontmatter, write_frontmatter
from specify_cli.lanes.frozen_membership import remedy_for
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import emit_status_transition
from tests.integration.refinalize_frozen_lanes_support import (
    EVENTS,
    WP_FILES,
    FinalizeResult,
    Mission,
    add_wp03,
    amend_overlap,
    commit,
    commit_amendment,
    finalize,
    git,
    lane_topology,
    setup_mission,
    snapshot,
    spy_writers,
    start_wp,
    wrap_everywhere,
    write_wp,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FROZEN = "LANE_MEMBERSHIP_FROZEN"


@dataclass
class _Untouched:
    """SC-003 + FR-005 evidence around one refused run."""

    mission: Mission
    before: dict[str, bytes] = field(default_factory=dict)
    head: str = ""

    def assert_untouched(self) -> None:
        assert snapshot(self.mission) == self.before, "a refused re-finalize must not change any planning or status file"
        assert git(self.mission.repo, "rev-parse", "HEAD") == self.head, "a refused re-finalize must not commit"


def _refuse(mission: Mission, monkeypatch: pytest.MonkeyPatch, *extra: str, frozen: bool = True) -> FinalizeResult:
    """Run a re-finalize expected to refuse; assert it wrote and committed nothing."""
    guard = _Untouched(mission, snapshot(mission), git(mission.repo, "rev-parse", "HEAD"))
    spy = spy_writers(monkeypatch)

    result = finalize(mission.slug, *extra)

    assert result.exit_code == 1, f"expected a refusal; output:\n{result.output}"
    if frozen:
        assert result.payload.get("error_code") == _FROZEN, result.payload
        assert str(result.payload.get("next_step") or "").strip(), result.payload
    assert spy.status_writes_to(mission.feature_dir) == [], "the refusal must come before any status event is written"
    assert spy.lanes_writes_to(mission.feature_dir) == [], "the refusal must come before lanes.json is written"
    guard.assert_untouched()
    return result


def _conflict(result: FinalizeResult, reason: str) -> dict[str, Any]:
    conflicts: list[dict[str, Any]] = [c for c in result.payload.get("conflicts") or [] if c.get("reason") == reason]
    assert len(conflicts) == 1, result.payload
    return conflicts[0]


def _set_up_two_started_collision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP01", commit_work=True, in_progress=True)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    amend_overlap(mission, joiner="WP01", owner="WP02")
    add_wp03(mission)
    commit_amendment(mission)
    return mission


def _wp_file(mission: Mission, wp_id: str) -> Path:
    return mission.feature_dir / "tasks" / WP_FILES[wp_id]


def _remove_wp02(mission: Mission) -> dict[Path, bytes]:
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


def _events(mission: Mission) -> Iterator[dict[str, Any]]:
    for line in (mission.feature_dir / EVENTS).read_text(encoding="utf-8").splitlines():
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

    result = finalize(mission.slug, json_output=False)

    assert result.exit_code == 1, result.output
    assert "Cannot re-finalize: started work packages would change lane." in result.output
    assert "started_lanes_collapsed: WP01 (lane-a), WP02 (lane-b)" in result.output
    # The console wraps long lines: compare the flattened text so the whole error and the whole remedy are pinned.
    flat = " ".join(result.output.split())
    assert "Error: Cannot re-finalize: started work packages would change lane. " in flat
    assert f"Remedy: {remedy_for('started_lanes_collapsed', ['WP01', 'WP02'])}" in flat


def test_started_wp_changing_kind_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    plan_path = str((mission.feature_dir / "plan.md").relative_to(mission.repo))
    meta, body = read_frontmatter(_wp_file(mission, "WP02"))
    meta["execution_mode"] = "planning_artifact"
    meta["owned_files"] = [plan_path]
    meta["authoritative_surface"] = plan_path
    write_frontmatter(_wp_file(mission, "WP02"), meta, body)
    commit_amendment(mission)

    result = _refuse(mission, monkeypatch)

    assert result.payload.get("reason") == "started_wp_kind_changed"
    conflict = _conflict(result, "started_wp_kind_changed")
    assert conflict["wp_ids"] == ["WP02"]
    assert conflict["recorded_lanes"] == ["lane-b"]


def _seed_started_then_append(mission: Mission, line: str) -> None:
    start_wp(mission, "WP02", commit_work=False, in_progress=False)
    with (mission.feature_dir / EVENTS).open("a", encoding="utf-8") as log:
        log.write(line)
    commit_amendment(mission)


def test_malformed_status_log_refuses_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS5, fail-closed half: a corrupt line refuses with nothing written.

    The planning-side WP read (``read_wp_frontmatter`` resolves runtime fields
    from the same log) already fails closed on a corrupt line, ahead of the
    preflight, with its existing store error. That text is kept unchanged
    (C-003); the preflight's own ``status_unreadable`` refusal is pinned below.
    """
    mission = setup_mission(tmp_path, monkeypatch)
    _seed_started_then_append(mission, "{corrupt\n")

    result = _refuse(mission, monkeypatch, frozen=False)

    assert "Invalid JSON on line" in str(result.payload.get("error")), result.payload


def test_unreadable_status_log_refuses_status_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS5: when the preflight cannot read the status history it refuses ``status_unreadable``."""
    from specify_cli.status import StoreError

    mission = setup_mission(tmp_path, monkeypatch)
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
    mission = setup_mission(tmp_path, monkeypatch)
    for name in (EVENTS, "status.json"):
        (mission.feature_dir / name).unlink(missing_ok=True)
    commit_amendment(mission)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]


# ---------------------------------------------------------------------------
# Remedies round-trip
# ---------------------------------------------------------------------------


def test_collapsed_remedy_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US2 AS7: move the shared path into a new WP03 that depends on both; the re-finalize then succeeds."""
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP01", commit_work=True, in_progress=True)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    tasks_md = mission.feature_dir / "tasks.md"
    original = {path: path.read_bytes() for path in (tasks_md, _wp_file(mission, "WP01"))}
    amend_overlap(mission, joiner="WP01", owner="WP02")
    commit_amendment(mission)
    _refuse(mission, monkeypatch)

    for path, data in original.items():
        path.write_bytes(data)
    write_wp(mission.feature_dir, "WP03", ["b.py"], "FR-001", ["WP01", "WP02"])
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8") + "\n## Work Package WP03: Third\n\nRequirement refs: FR-001\n\n**Dependencies**: WP01, WP02\n",
        encoding="utf-8",
    )
    commit_amendment(mission)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    lanes = {wp_id: lane_id for lane_id, wp_ids in lane_topology(after) for wp_id in wp_ids}
    assert lanes["WP01"] == "lane-a", lane_topology(after)
    assert lanes["WP02"] == "lane-b", lane_topology(after)
    assert "WP03" in lanes, lane_topology(after)


def test_removed_wp_remedy_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the task file and cancel the WP: it stays present and lane-eligible, so it keeps its lane.

    Finalize eligibility reads the retired frontmatter ``lane``, not the event
    log, so an event-log cancel does not retire the WP from lane inputs.
    """
    mission = setup_mission(tmp_path, monkeypatch)
    started = start_wp(mission, "WP02", commit_work=True, in_progress=True)
    saved = _remove_wp02(mission)
    commit_amendment(mission)
    refused = _refuse(mission, monkeypatch)

    assert refused.payload.get("reason") == "started_wp_removed"
    conflict = _conflict(refused, "started_wp_removed")
    assert conflict["wp_ids"] == ["WP02"]
    assert conflict["recorded_lanes"] == ["lane-b"]
    assert "move-task WP02 --to canceled --mission" in conflict["remedy"]
    assert "without clearing" in conflict["remedy"]

    for path, data in saved.items():
        path.write_bytes(data)
    emit_status_transition(mission.feature_dir, mission.slug, "WP02", "canceled", "test", reason="retired by the amendment")
    commit_amendment(mission)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]
    assert allocate_lane_worktree(mission.repo, mission.slug, "WP02", after) == (started.worktree, started.branch)


# ---------------------------------------------------------------------------
# FR-008: history and tip evidence
# ---------------------------------------------------------------------------


def test_wp_rejected_back_to_planned_keeps_its_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    emit_status_transition(mission.feature_dir, mission.slug, "WP02", "planned", "test", reason="rejected back to planning")
    assert [e.get("to_lane") for e in _events(mission) if e.get("wp_id") == "WP02"][-1] == "planned"
    amend_overlap(mission, joiner="WP01", owner="WP02")
    commit_amendment(mission)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-b", ("WP02", "WP01"))], lane_topology(after)


def test_lane_work_tip_alone_freezes_the_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-008 fallback: WP02's lane is allocated (a work tip is recorded) but WP02 has no started event."""
    mission = setup_mission(tmp_path, monkeypatch)
    _worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP02", mission.manifest)
    tips = git(mission.repo, "for-each-ref", "--format=%(refname)", "refs/spec-kitty/lane-tip/").splitlines()
    assert f"refs/spec-kitty/lane-tip/{branch}" in tips, tips
    assert not [e for e in _events(mission) if e.get("wp_id") == "WP02" and e.get("to_lane") not in (None, "planned")]
    amend_overlap(mission, joiner="WP01", owner="WP02")
    commit_amendment(mission)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-b", ("WP02", "WP01"))], lane_topology(after)


# ---------------------------------------------------------------------------
# FR-005 ordering, skips and the FR-009 preview
# ---------------------------------------------------------------------------

_STATUS_WRITERS = ("_emit_tasks_started", "_emit_local_canonical_events", "_bootstrap_canonical_state_via_mission")


def _spy_status_writers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    for name in _STATUS_WRITERS:

        def _record(*_args: object, _name: str = name, **_kwargs: object) -> None:
            calls.append(_name)

        wrap_everywhere(monkeypatch, getattr(mission_finalize, name), _record)
    return calls


def test_refusal_precedes_every_status_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _set_up_two_started_collision(tmp_path, monkeypatch)
    calls = _spy_status_writers(monkeypatch)

    _refuse(mission, monkeypatch)

    assert calls == [], f"the preflight must refuse before any status writer runs; ran: {calls}"


def test_status_writer_spies_are_live_positive_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP01", commit_work=True, in_progress=True)
    add_wp03(mission)
    commit_amendment(mission)
    calls = _spy_status_writers(monkeypatch)

    result = finalize(mission.slug)

    assert result.exit_code == 0, result.output
    assert set(calls) == set(_STATUS_WRITERS), calls


def test_refresh_planning_commit_never_runs_the_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    commit_amendment(mission)
    calls: list[str] = []
    wrap_everywhere(monkeypatch, mission_finalize._preflight_frozen_lane_membership, lambda *_a, **_k: calls.append("preflight"))

    refresh = finalize(mission.slug, "--refresh-planning-commit")
    assert refresh.exit_code == 0, refresh.output
    assert refresh.payload.get("result") == "success", refresh.payload
    assert calls == [], "a --refresh-planning-commit run never recomputes membership"

    plain = finalize(mission.slug)
    assert plain.exit_code == 0, plain.output
    assert calls == ["preflight"], "positive control: a plain re-finalize runs the preflight once"


def test_validate_only_preview_reports_the_frozen_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-009: the preview reads back the previous manifest and honours the frozen membership."""
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP02", commit_work=True, in_progress=True)
    amend_overlap(mission, joiner="WP01", owner="WP02")
    commit_amendment(mission)
    before = snapshot(mission)

    result = finalize(mission.slug, "--validate-only")

    assert result.exit_code == 0, result.output
    preview = result.payload["validation"]["lanes_preview"]
    assert preview["lane_ids"] == ["lane-b"], preview
    assert snapshot(mission) == before


# ---------------------------------------------------------------------------
# A lane cycle caused by keeping started lane-mates together
# ---------------------------------------------------------------------------


def _set_wp(mission: Mission, wp_id: str, owned: list[str], dependencies: list[str]) -> None:
    """Set *wp_id*'s owned files and dependencies in its frontmatter and in ``tasks.md``."""
    meta, body = read_frontmatter(_wp_file(mission, wp_id))
    meta["owned_files"] = owned
    meta["authoritative_surface"] = owned[0]
    meta["dependencies"] = dependencies
    write_frontmatter(_wp_file(mission, wp_id), meta, body)
    tasks_md = mission.feature_dir / "tasks.md"
    lines = tasks_md.read_text(encoding="utf-8").split("\n")
    heading = next(index for index, line in enumerate(lines) if line.startswith(f"## Work Package {wp_id}"))
    end = next((index for index in range(heading + 1, len(lines)) if lines[index].startswith("## Work Package")), len(lines))
    section = [line for line in lines[heading + 1 : end] if not line.startswith("**Dependencies**")]
    if dependencies:
        section = ["", f"**Dependencies**: {', '.join(dependencies)}", *section]
    tasks_md.write_text("\n".join([*lines[: heading + 1], *section, *lines[end:]]), encoding="utf-8")


def _set_up_frozen_lane_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    """WP01 and WP03 started together on lane-a; the amendment chains WP01 -> WP02 (lane-b) -> WP03.

    Without the freeze the three WPs get three acyclic lanes; keeping WP01 and
    WP03 together makes lane-a -> lane-b -> lane-a.
    """
    mission = setup_mission(tmp_path, monkeypatch)
    start_wp(mission, "WP01", commit_work=True, in_progress=True)
    write_wp(mission.feature_dir, "WP03", ["c.py", "a.py"], "FR-001", ["WP01"])
    tasks_md = mission.feature_dir / "tasks.md"
    wp03_section = "\n## Work Package WP03: Third\n\nRequirement refs: FR-001\n\n**Dependencies**: WP01\n"
    tasks_md.write_text(tasks_md.read_text(encoding="utf-8") + wp03_section, encoding="utf-8")
    commit_amendment(mission)
    joined = finalize(mission.slug)
    assert joined.exit_code == 0, joined.output
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    assert ("lane-a", ("WP01", "WP03")) in lane_topology(manifest), lane_topology(manifest)
    # WP01 is not approved yet, so WP03's claim is forced past the dependency gate.
    allocate_lane_worktree(mission.repo, mission.slug, "WP03", manifest)
    emit_status_transition(mission.feature_dir, mission.slug, "WP03", "claimed", "test", force=True, reason="started beside WP01 on lane-a")
    _set_wp(mission, "WP02", ["b.py"], ["WP01"])
    _set_wp(mission, "WP03", ["c.py"], ["WP02"])
    commit_amendment(mission)
    return mission


@pytest.mark.parametrize("extra", [(), ("--validate-only",)], ids=["real-run", "validate-only"])
def test_freeze_induced_lane_cycle_refuses_before_any_status_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: tuple[str, ...]) -> None:
    mission = _set_up_frozen_lane_cycle(tmp_path, monkeypatch)
    calls = _spy_status_writers(monkeypatch)

    result = _refuse(mission, monkeypatch, *extra, frozen=False)

    assert calls == [], f"the cycle must surface before any status writer runs; ran: {calls}"
    assert result.payload.get("error_code") == "LANE_DEPENDENCY_CYCLE", result.payload
    assert result.payload.get("cycle_path") == ["lane-a", "lane-b", "lane-a"], result.payload
    assert str(result.payload.get("error", "")).startswith("Execution-lane dependency cycle detected: "), result.payload


# ---------------------------------------------------------------------------
# FR-007 / #4959: an unmaterialized coordination worktree is read from its
# committed branch, never as "nothing started"
# ---------------------------------------------------------------------------


# Each coordination test builds a real ``lanes_with_coord`` mission through the
# CLI (create, finalize, record-analysis, implement): tens of seconds apiece.
_SLOW_COORDINATION = pytest.mark.slow


@dataclass
class _CoordMission:
    mission: Mission
    coord_worktree: Path
    planning_rel: str
    coordination_branch: str


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real ``spec-kitty`` CLI from this checkout's sources (setup steps only)."""
    import specify_cli

    env = dict(os.environ, PYTHONPATH=str(Path(specify_cli.__file__).resolve().parents[1]), NO_COLOR="1")
    result = subprocess.run([sys.executable, "-m", "specify_cli", *args], cwd=repo, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, f"{args}: rc={result.returncode}\n{result.stdout[-3000:]}\n{result.stderr[-2000:]}"
    return result


def _coord_wp(wp_id: str, owned: list[str], dependencies: list[str]) -> str:
    return (
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies: {json.dumps(dependencies)}\nrequirement_refs: [FR-001]\n"
        f"subtasks: []\nowned_files: {json.dumps(owned)}\nauthoritative_surface: {owned[0]}\nexecution_mode: code_change\n---\n\n# {wp_id}\n\nDo it.\n"
    )


def _set_up_coord_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, start_wp02: bool = True) -> _CoordMission:
    """``lanes_with_coord``: lane-a = [WP01], lane-b = [WP02]; with *start_wp02*, WP02 is implemented (status on the coordination branch)."""
    from mission_runtime import MissionTopology
    from tests._factories.coord_mission import make_coord_mission

    created = make_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, via="cli_topology", slug="coordfrozen")
    repo = created.repo_root
    (repo / ".git" / "info" / "exclude").write_text(".worktrees/\n.kittify/derived/\n.kittify/workspaces/\n*.lock\n.kittify/runtime/\n", encoding="utf-8")
    rel = f"kitty-specs/{created.mission_dir_name}"
    feature_dir = repo / rel
    (repo / "src").mkdir(exist_ok=True)
    for name in ("a", "b"):
        (repo / "src" / f"{name}.py").write_text(f"{name} = 0\n", encoding="utf-8")
    git(repo, "add", "src")
    commit(repo, "src")
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n| ID | Requirement | Status |\n|----|-------------|--------|\n| FR-001 | It works. | Draft |\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\nx\n\n## Work Package WP02\n\n**Dependencies**: None\n\ny\n", encoding="utf-8"
    )
    (feature_dir / "tasks" / "WP01-a.md").write_text(_coord_wp("WP01", ["src/a.py"], []), encoding="utf-8")
    (feature_dir / "tasks" / "WP02-b.md").write_text(_coord_wp("WP02", ["src/b.py"], []), encoding="utf-8")
    git(repo, "add", rel)
    commit(repo, "planning")
    _cli(repo, "agent", "mission", "finalize-tasks", "--mission", created.mission_dir_name, "--json")
    analysis = tmp_path / "analysis.md"
    analysis.write_text(
        "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
        "# Specification Analysis Report\n\nNo blocking findings.\n",
        encoding="utf-8",
    )
    _cli(repo, "agent", "mission", "record-analysis", "--mission", created.mission_dir_name, "--input-file", str(analysis))
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    assert lane_topology(manifest) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]
    if start_wp02:
        _cli(repo, "agent", "action", "implement", "WP02", "--agent", "e2e", "--mission", created.mission_dir_name)
        lane_b = repo / ".worktrees" / f"{created.mission_dir_name}-lane-b"
        (lane_b / "src" / "b.py").write_text("b = 42\n", encoding="utf-8")
        git(lane_b, "add", "src/b.py")
        commit(lane_b, "WP02 work")
    coord_log = git(repo, "show", f"{created.coordination_branch}:{rel}/{EVENTS}")
    started_on_branch = any(
        json.loads(line).get("wp_id") == "WP02" and json.loads(line).get("to_lane") == "in_progress" for line in coord_log.splitlines() if line.strip()
    )
    assert started_on_branch is start_wp02, coord_log
    # Tips are per clone and cleared once a lane's WPs finish: without them the
    # status history on the coordination branch is the only started evidence.
    for ref in git(repo, "for-each-ref", "--format=%(refname)", "refs/spec-kitty/lane-tip/").splitlines():
        git(repo, "update-ref", "-d", ref)
    monkeypatch.chdir(repo)
    return _CoordMission(Mission(repo, created.mission_dir_name, feature_dir, manifest), created.coord_worktree_path, rel, created.coordination_branch)


def _amend_coord_overlap(coord: _CoordMission) -> None:
    feature_dir = coord.mission.feature_dir
    (feature_dir / "tasks" / "WP01-a.md").write_text(_coord_wp("WP01", ["src/a.py", "src/b.py"], ["WP02"]), encoding="utf-8")
    tasks_md = feature_dir / "tasks.md"
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8").replace("## Work Package WP01\n\n**Dependencies**: None", "## Work Package WP01\n\n**Dependencies**: WP02"),
        encoding="utf-8",
    )
    git(coord.mission.repo, "add", coord.planning_rel)
    commit(coord.mission.repo, "amend")


def _spy_preflight_materialization(monkeypatch: pytest.MonkeyPatch, coord_worktree: Path) -> list[bool]:
    """Record, after each preflight, whether the coordination worktree exists: the preflight must never materialize it."""
    seen: list[bool] = []
    original = mission_finalize._preflight_frozen_lane_membership

    def _spy(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        seen.append(coord_worktree.exists())
        return result

    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if isinstance(namespace, dict) and namespace.get("_preflight_frozen_lane_membership") is original:
            monkeypatch.setattr(module, "_preflight_frozen_lane_membership", _spy)
    return seen


@_SLOW_COORDINATION
def test_unmaterialized_coordination_worktree_reads_the_committed_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The precons breaker's ``wt_removed_tips_deleted``: WP02's started events are read from the coordination branch."""
    coord = _set_up_coord_mission(tmp_path, monkeypatch)
    git(coord.mission.repo, "worktree", "remove", "--force", str(coord.coord_worktree))
    _amend_coord_overlap(coord)
    preflight_saw_worktree = _spy_preflight_materialization(monkeypatch, coord.coord_worktree)

    result = finalize(coord.mission.slug)

    assert result.exit_code == 0, result.output
    assert preflight_saw_worktree == [False], "the preflight reads the branch read-only; it must not materialize the worktree"
    after = read_lanes_json(coord.mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-b", ("WP02", "WP01"))], lane_topology(after)


@_SLOW_COORDINATION
def test_unmaterialized_coordination_worktree_with_nothing_started_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Parity with the behaviour before #5573: nothing started, so the amendment recomputes freely."""
    coord = _set_up_coord_mission(tmp_path, monkeypatch, start_wp02=False)
    git(coord.mission.repo, "worktree", "remove", "--force", str(coord.coord_worktree))
    _amend_coord_overlap(coord)

    result = finalize(coord.mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(coord.mission.feature_dir)
    assert after is not None
    assert [(lane_id, sorted(wp_ids)) for lane_id, wp_ids in lane_topology(after)] == [("lane-a", ["WP01", "WP02"])], lane_topology(after)


@_SLOW_COORDINATION
def test_remote_only_coordination_branch_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The coordination branch lives only on a remote: the committed log cannot be read, so refuse with the fetch remedy."""
    coord = _set_up_coord_mission(tmp_path, monkeypatch)
    repo = coord.mission.repo
    # The coordination-mission factory already points ``origin`` at a bare remote.
    git(repo, "push", "-q", "origin", coord.coordination_branch)
    git(repo, "worktree", "remove", "--force", str(coord.coord_worktree))
    git(repo, "branch", "-D", coord.coordination_branch)
    _amend_coord_overlap(coord)

    result = _refuse(coord.mission, monkeypatch)

    assert result.payload.get("reason") == "status_unreadable", result.payload
    remedy = _conflict(result, "status_unreadable")["remedy"]
    assert remedy.startswith("Materialize the coordination worktree"), remedy
    assert f"git fetch origin {coord.coordination_branch}" in remedy, remedy
    assert not coord.coord_worktree.exists(), "the refusal must not materialize the coordination worktree"
    after = read_lanes_json(coord.mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))]


@_SLOW_COORDINATION
def test_materialized_coordination_worktree_keeps_the_started_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: the same scenario with the coordination worktree present succeeds; WP02 keeps lane-b."""
    coord = _set_up_coord_mission(tmp_path, monkeypatch)
    assert coord.coord_worktree.is_dir()
    _amend_coord_overlap(coord)

    result = finalize(coord.mission.slug)

    assert result.exit_code == 0, result.output
    after = read_lanes_json(coord.mission.feature_dir)
    assert after is not None
    assert lane_topology(after) == [("lane-b", ("WP02", "WP01"))], lane_topology(after)
