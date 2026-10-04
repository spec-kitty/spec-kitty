"""#5573 — a re-finalize must never move a started work package to another lane.

End-to-end reproduction through the real ``agent mission finalize-tasks``
command (Typer ``mission_app``, in-process), with real git, real status events
and a real allocated lane worktree.

Starting state for every test: a ``lanes`` mission whose first finalize gives
lane-a = [WP01] (``a.py``) and lane-b = [WP02] (``b.py``). A WP is "started"
when it is allocated and its status left ``planned``. The amendment then
forces an overlap and re-runs finalize-tasks.

* US1 AS1 / SC-001: a planned WP joining a started WP's lane must follow the
  started WP's recorded lane (lane-b), not the lowest lane id.
* US1 AS2: the same holds for a WP that is only ``claimed``.
* US1 AS3 (positive control): when the started WP already sits on lane-a, the
  merged lane is lane-a. This passes before the fix too.
* US2 AS1 / FR-005 / FR-006 / SC-003: two started lanes forced together refuse
  with ``LANE_MEMBERSHIP_FROZEN`` before writing anything; a same-fixture
  positive control proves the same WP03 addition succeeds without the collision.
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.frontmatter import read_frontmatter, write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes import persistence as lanes_persistence
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import emit_status_transition
from specify_cli.status import store as status_store
from tests._factories import make_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "lane-preservation"
# Not a protected branch: a lanes mission has no coordination worktree, so its
# bookkeeping on a protected target such as ``main`` is refused.
_TARGET = "qa-main"
_PLANNING_LANE = "lane-planning"
_EVENTS = "status.events.jsonl"
_WP_FILES = {"WP01": "WP01.md", "WP02": "WP02.md", "WP03": "WP03.md"}

runner = CliRunner()


@dataclass
class _Mission:
    repo: Path
    slug: str
    feature_dir: Path
    manifest: LanesManifest


@dataclass
class _Started:
    worktree: Path
    branch: str


@dataclass
class _FinalizeResult:
    exit_code: int
    payload: dict[str, Any]
    output: str


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _first_json_object(text: str) -> dict[str, Any]:
    """The first JSON object in ``text`` (advisories may surround it)."""
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            data, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(data, dict):
            return data
        index = text.find("{", index + 1)
    raise AssertionError(f"no JSON object in finalize-tasks output:\n{text}")


def _finalize(mission_slug: str) -> _FinalizeResult:
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    result = runner.invoke(mission_app, ["finalize-tasks", "--mission", mission_slug, "--json"])
    return _FinalizeResult(result.exit_code, _first_json_object(result.output), result.output)


def _code_lanes(manifest: LanesManifest) -> list[ExecutionLane]:
    return sorted((lane for lane in manifest.lanes if lane.lane_id != _PLANNING_LANE), key=lambda lane: lane.lane_id)


def _topology(manifest: LanesManifest) -> list[tuple[str, tuple[str, ...]]]:
    return [(lane.lane_id, tuple(lane.wp_ids)) for lane in _code_lanes(manifest)]


def _write_wp(feature_dir: Path, wp_id: str, owned: list[str], requirement: str, dependencies: list[str]) -> None:
    number = int(wp_id[2:])
    write_frontmatter(
        feature_dir / "tasks" / _WP_FILES[wp_id],
        {
            "work_package_id": wp_id,
            "title": f"Package {number}",
            "dependencies": dependencies,
            "requirement_refs": [requirement],
            "owned_files": owned,
            "authoritative_surface": owned[0],
            "execution_mode": "code_change",
            "subtasks": [f"T{number:03}"],
        },
        f"# {wp_id}\n\n- [ ] T{number:03} Deliver the output.\n",
    )


def _setup_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Mission:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / ".gitignore").write_text(".worktrees/\n.kittify/runtime/\n", encoding="utf-8")
    for name in ("a", "b", "c"):
        (repo / f"{name}.py").write_text(f"{name} = 0\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    monkeypatch.chdir(repo)

    created = make_mission(repo, _SLUG, target_branch=_TARGET, topology=MissionTopology.LANES)
    feature_dir = created.feature_dir
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Requirements\n\n- **FR-001**: package one delivers its output.\n- **FR-002**: package two delivers its output.\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: First\n\nRequirement refs: FR-001\n\n## Work Package WP02: Second\n\nRequirement refs: FR-002\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks").mkdir(exist_ok=True)
    _write_wp(feature_dir, "WP01", ["a.py"], "FR-001", [])
    _write_wp(feature_dir, "WP02", ["b.py"], "FR-002", [])
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "planning")

    first = _finalize(created.mission_slug)
    assert first.exit_code == 0, first.output
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    assert _topology(manifest) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))], _topology(manifest)
    return _Mission(repo, created.mission_slug, feature_dir, manifest)


def _start(mission: _Mission, wp_id: str, *, commit_work: bool, in_progress: bool) -> _Started:
    """Allocate the WP's lane worktree, optionally commit work, and move its status past ``planned``."""
    worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, wp_id, mission.manifest)
    if commit_work:
        owned = read_frontmatter(mission.feature_dir / "tasks" / _WP_FILES[wp_id])[0]["owned_files"][0]
        (worktree / owned).write_text(f"{Path(owned).stem} = 42\n", encoding="utf-8")
        _git(worktree, "add", owned)
        _git(worktree, "commit", "-qm", f"implement {wp_id}")
    emit_status_transition(mission.feature_dir, mission.slug, wp_id, "claimed", "test")
    expected_lane = "claimed"
    if in_progress:
        emit_status_transition(mission.feature_dir, mission.slug, wp_id, "in_progress", "test", workspace_context=str(worktree))
        expected_lane = "in_progress"
    events = [json.loads(line) for line in (mission.feature_dir / _EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event.get("wp_id") == wp_id and event.get("to_lane") == expected_lane for event in events), (
        f"seed: {wp_id} must have a {expected_lane} event before the amendment"
    )
    return _Started(worktree, branch)


def _amend_overlap(mission: _Mission, joiner: str, owner: str) -> None:
    """``joiner`` also owns ``owner``'s file and depends on ``owner`` (frontmatter plus ``tasks.md``)."""
    assert not (mission.feature_dir / "wps.yaml").exists(), "fixture amends frontmatter; wps.yaml would be the source"
    joiner_file = mission.feature_dir / "tasks" / _WP_FILES[joiner]
    owner_file = mission.feature_dir / "tasks" / _WP_FILES[owner]
    meta, body = read_frontmatter(joiner_file)
    owner_path = read_frontmatter(owner_file)[0]["owned_files"][0]
    meta["owned_files"] = [*meta["owned_files"], owner_path]
    meta["dependencies"] = [owner]
    write_frontmatter(joiner_file, meta, body)
    tasks_md = mission.feature_dir / "tasks.md"
    text = tasks_md.read_text(encoding="utf-8")
    heading = next(line for line in text.splitlines() if line.startswith(f"## Work Package {joiner}"))
    tasks_md.write_text(text.replace(heading, f"{heading}\n\n**Dependencies**: {owner}", 1), encoding="utf-8")


def _add_wp03(mission: _Mission) -> None:
    """A new planned WP03 owning its own file (``c.py``); it collides with nothing."""
    _write_wp(mission.feature_dir, "WP03", ["c.py"], "FR-001", [])
    tasks_md = mission.feature_dir / "tasks.md"
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8") + "\n## Work Package WP03: Third\n\nRequirement refs: FR-001\n",
        encoding="utf-8",
    )


def _commit_amendment(mission: _Mission) -> None:
    _git(mission.repo, "add", ".")
    _git(mission.repo, "commit", "-qm", "record execution and planning amendment")


def _assert_saw_overlap(result: _FinalizeResult) -> None:
    """The re-finalize actually read the amendment (non-vacuity of the amendment)."""
    report = result.payload.get("lanes", {}).get("collapse_report", {})
    rules = {event.get("rule") for event in report.get("events", [])} | set(report.get("by_rule", {}))
    assert "write_scope_overlap" in rules, f"the re-finalize did not see the overlap amendment: {report!r}"


@dataclass
class _WriteSpy:
    """Directories the real status-event and lane-manifest writers were asked to write."""

    status_dirs: list[Path] = field(default_factory=list)
    lanes_dirs: list[Path] = field(default_factory=list)

    def status_writes_to(self, feature_dir: Path) -> list[Path]:
        return [d for d in self.status_dirs if d.resolve() == feature_dir.resolve()]

    def lanes_writes_to(self, feature_dir: Path) -> list[Path]:
        return [d for d in self.lanes_dirs if d.resolve() == feature_dir.resolve()]


def _wrap_everywhere(monkeypatch: pytest.MonkeyPatch, original: Callable[..., object], record: Callable[..., None]) -> None:
    """Wrap ``original`` (still calling it) under every module name bound to it.

    Callers resolve writers through ``from x import f`` aliases as well as the
    defining module, so the spy rebinds every loaded alias. The real writer
    still runs: finalize's restore-on-exit then cannot hide that it ran.
    """

    @functools.wraps(original)
    def _spy(*args: object, **kwargs: object) -> object:
        record(*args, **kwargs)
        return original(*args, **kwargs)

    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in list(namespace.items()):
            if value is original:
                monkeypatch.setattr(module, name, _spy)


def _spy_writers(monkeypatch: pytest.MonkeyPatch) -> _WriteSpy:
    """Record every status-event append and every ``write_lanes_json`` call.

    The status sinks are the two physical writers of ``status.events.jsonl``:
    ``append_event`` (line append) and ``append_raw_rows_atomic`` (the atomic
    batch writer every ``append_*_atomic*`` helper delegates to).
    """
    spy = _WriteSpy()

    def _record_feature_dir(feature_dir: Path, *_args: object, **_kwargs: object) -> None:
        spy.status_dirs.append(Path(feature_dir))

    def _record_events_path(path: Path, *_args: object, **_kwargs: object) -> None:
        if Path(path).name == _EVENTS:
            spy.status_dirs.append(Path(path).parent)

    def _record_lanes_dir(planning_dir: Path, *_args: object, **_kwargs: object) -> None:
        spy.lanes_dirs.append(Path(planning_dir))

    _wrap_everywhere(monkeypatch, status_store.append_event, _record_feature_dir)
    _wrap_everywhere(monkeypatch, status_store.append_raw_rows_atomic, _record_events_path)
    _wrap_everywhere(monkeypatch, lanes_persistence.write_lanes_json, _record_lanes_dir)
    return spy


def _snapshot(mission: _Mission) -> dict[str, bytes]:
    paths = [mission.feature_dir / name for name in ("lanes.json", _EVENTS, "tasks.md", "meta.json", "wps.yaml")]
    paths += sorted((mission.feature_dir / "tasks").glob("*.md"))
    return {str(path.relative_to(mission.feature_dir)): path.read_bytes() for path in paths if path.is_file()}


def _assert_started_wp02_kept_lane_b(mission: _Mission, started: _Started, result: _FinalizeResult) -> None:
    assert result.exit_code == 0, result.output
    _assert_saw_overlap(result)
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-b", ("WP02", "WP01"))], (
        f"a planned WP joining a started WP's lane must follow the started WP's recorded lane (#5573); lanes after: {_topology(after)!r}"
    )
    worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP02", after)
    assert worktree == started.worktree
    assert branch == started.branch


def test_started_wp_keeps_its_lane_when_a_planned_wp_joins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    _assert_started_wp02_kept_lane_b(mission, started, result)
    assert (started.worktree / "b.py").read_text(encoding="utf-8") == "b = 42\n"


def test_claimed_only_wp_keeps_its_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP02", commit_work=False, in_progress=False)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    _assert_started_wp02_kept_lane_b(mission, started, result)


def test_lane_follows_the_started_wp_not_lane_id_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: WP01 started on lane-a, WP02 joins it; the merged lane is lane-a."""
    mission = _setup_mission(tmp_path, monkeypatch)
    started = _start(mission, "WP01", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP02", owner="WP01")
    _commit_amendment(mission)

    result = _finalize(mission.slug)

    assert result.exit_code == 0, result.output
    _assert_saw_overlap(result)
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    assert _topology(after) == [("lane-a", ("WP01", "WP02"))], _topology(after)
    worktree, _branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", after)
    assert worktree == started.worktree
    assert (worktree / "a.py").read_text(encoding="utf-8") == "a = 42\n"


def test_two_started_lanes_forced_together_refuse_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _amend_overlap(mission, joiner="WP01", owner="WP02")
    # A new planned WP03 gives finalize a seed event to write, so a refusal
    # raised after seeding has something to write. Byte identity alone cannot
    # catch that: finalize's restore-on-exit (#5641) puts the bytes back. The
    # writer spies observe the write itself, which the restore cannot undo.
    _add_wp03(mission)
    _commit_amendment(mission)
    before = _snapshot(mission)
    head_before = _git(mission.repo, "rev-parse", "HEAD")
    spy = _spy_writers(monkeypatch)

    result = _finalize(mission.slug)

    assert result.exit_code == 1, f"two started lanes forced into one must refuse (#5573); output:\n{result.output}"
    payload = result.payload
    assert payload.get("error_code") == "LANE_MEMBERSHIP_FROZEN", payload
    assert payload.get("reason") == "started_lanes_collapsed", payload
    conflicts = payload.get("conflicts") or []
    assert any(
        sorted(conflict.get("wp_ids", [])) == ["WP01", "WP02"] and sorted(conflict.get("recorded_lanes", [])) == ["lane-a", "lane-b"] for conflict in conflicts
    ), conflicts
    assert str(payload.get("next_step") or "").strip(), payload
    # FR-005: the refusal comes before any status or manifest write.
    assert spy.status_writes_to(mission.feature_dir) == [], "the refusal must come before any status event is written"
    assert spy.lanes_writes_to(mission.feature_dir) == [], "the refusal must come before lanes.json is written"
    assert _snapshot(mission) == before, "a refused re-finalize must not write any planning or status file"
    assert _git(mission.repo, "rev-parse", "HEAD") == head_before, "a refused re-finalize must not commit"


def test_new_wp_without_collision_is_seeded_positive_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture as the refusal test, minus the collision: WP03 is added and seeded."""
    mission = _setup_mission(tmp_path, monkeypatch)
    _start(mission, "WP01", commit_work=True, in_progress=True)
    _start(mission, "WP02", commit_work=True, in_progress=True)
    _add_wp03(mission)
    _commit_amendment(mission)
    spy = _spy_writers(monkeypatch)

    result = _finalize(mission.slug)

    assert result.exit_code == 0, result.output
    # The spies are live: the same writers do record this run's writes.
    assert spy.status_writes_to(mission.feature_dir), "the status-writer spy must see WP03's seed event"
    assert spy.lanes_writes_to(mission.feature_dir), "the lanes-writer spy must see the lanes.json write"
    events = [json.loads(line) for line in (mission.feature_dir / _EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event.get("wp_id") == "WP03" for event in events), "the positive control must seed WP03"
    after = read_lanes_json(mission.feature_dir)
    assert after is not None
    topology = dict(_topology(after))
    assert topology.get("lane-a") == ("WP01",), topology
    assert topology.get("lane-b") == ("WP02",), topology
    wp03_lanes = sorted(lane_id for lane_id, wp_ids in topology.items() if "WP03" in wp_ids)
    assert len(wp03_lanes) == 1, topology
    assert wp03_lanes[0] not in {"lane-a", "lane-b"}, topology
