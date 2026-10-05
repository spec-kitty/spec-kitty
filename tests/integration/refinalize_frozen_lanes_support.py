"""Shared fixture helpers for the #5573 re-finalize tests (not a test module).

The two #5573 integration suites (``test_refinalize_keeps_started_lanes``,
the red-first reproduction, and ``test_refinalize_frozen_lane_refusals``) drive the
real ``agent mission finalize-tasks`` command over the same fixture: a
``lanes`` mission whose first finalize gives lane-a = [WP01] (``a.py``) and
lane-b = [WP02] (``b.py``). A WP is "started" when it is allocated and its
status left ``planned``.
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

__all__ = [
    "EVENTS",
    "FinalizeResult",
    "Mission",
    "PLANNING_LANE",
    "SLUG",
    "Started",
    "TARGET",
    "WP_FILES",
    "WriteSpy",
    "add_wp03",
    "amend_overlap",
    "assert_saw_overlap",
    "code_lanes",
    "commit",
    "commit_amendment",
    "finalize",
    "first_json_object",
    "git",
    "lane_topology",
    "runner",
    "setup_mission",
    "snapshot",
    "spy_writers",
    "start_wp",
    "wrap_everywhere",
    "write_wp",
]

SLUG = "lane-preservation"
# Not a protected branch: a lanes mission has no coordination worktree, so its
# bookkeeping on a protected target such as ``main`` is refused.
TARGET = "qa-main"
PLANNING_LANE = "lane-planning"
EVENTS = "status.events.jsonl"
WP_FILES = {"WP01": "WP01.md", "WP02": "WP02.md", "WP03": "WP03.md"}

runner = CliRunner()


@dataclass
class Mission:
    repo: Path
    slug: str
    feature_dir: Path
    manifest: LanesManifest


@dataclass
class Started:
    worktree: Path
    branch: str


@dataclass
class FinalizeResult:
    exit_code: int
    payload: dict[str, Any]
    output: str


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def first_json_object(text: str) -> dict[str, Any]:
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


def finalize(mission_slug: str, *extra: str, json_output: bool = True) -> FinalizeResult:
    """Run ``finalize-tasks`` in process; with *json_output*, parse its first JSON object as the payload."""
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    args = ["finalize-tasks", "--mission", mission_slug, *extra, *(["--json"] if json_output else [])]
    result = runner.invoke(mission_app, args)
    payload = first_json_object(result.output) if json_output else {}
    return FinalizeResult(result.exit_code, payload, result.output)


def commit(repo: Path, message: str) -> None:
    """Commit the staged changes with a throwaway identity (repositories without ``user.*`` config)."""
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", message)


def code_lanes(manifest: LanesManifest) -> list[ExecutionLane]:
    return sorted((lane for lane in manifest.lanes if lane.lane_id != PLANNING_LANE), key=lambda lane: lane.lane_id)


def lane_topology(manifest: LanesManifest) -> list[tuple[str, tuple[str, ...]]]:
    return [(lane.lane_id, tuple(lane.wp_ids)) for lane in code_lanes(manifest)]


def write_wp(feature_dir: Path, wp_id: str, owned: list[str], requirement: str, dependencies: list[str]) -> None:
    number = int(wp_id[2:])
    write_frontmatter(
        feature_dir / "tasks" / WP_FILES[wp_id],
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


def setup_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mission:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", TARGET)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / ".gitignore").write_text(".worktrees/\n.kittify/runtime/\n", encoding="utf-8")
    for name in ("a", "b", "c"):
        (repo / f"{name}.py").write_text(f"{name} = 0\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    monkeypatch.chdir(repo)

    created = make_mission(repo, SLUG, target_branch=TARGET, topology=MissionTopology.LANES)
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
    write_wp(feature_dir, "WP01", ["a.py"], "FR-001", [])
    write_wp(feature_dir, "WP02", ["b.py"], "FR-002", [])
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "planning")

    first = finalize(created.mission_slug)
    assert first.exit_code == 0, first.output
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    assert lane_topology(manifest) == [("lane-a", ("WP01",)), ("lane-b", ("WP02",))], lane_topology(manifest)
    return Mission(repo, created.mission_slug, feature_dir, manifest)


def start_wp(mission: Mission, wp_id: str, *, commit_work: bool, in_progress: bool) -> Started:
    """Allocate the WP's lane worktree, optionally commit work, and move its status past ``planned``."""
    worktree, branch = allocate_lane_worktree(mission.repo, mission.slug, wp_id, mission.manifest)
    if commit_work:
        owned = read_frontmatter(mission.feature_dir / "tasks" / WP_FILES[wp_id])[0]["owned_files"][0]
        (worktree / owned).write_text(f"{Path(owned).stem} = 42\n", encoding="utf-8")
        git(worktree, "add", owned)
        git(worktree, "commit", "-qm", f"implement {wp_id}")
    emit_status_transition(mission.feature_dir, mission.slug, wp_id, "claimed", "test")
    expected_lane = "claimed"
    if in_progress:
        emit_status_transition(mission.feature_dir, mission.slug, wp_id, "in_progress", "test", workspace_context=str(worktree))
        expected_lane = "in_progress"
    events = [json.loads(line) for line in (mission.feature_dir / EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event.get("wp_id") == wp_id and event.get("to_lane") == expected_lane for event in events), (
        f"seed: {wp_id} must have a {expected_lane} event before the amendment"
    )
    return Started(worktree, branch)


def amend_overlap(mission: Mission, joiner: str, owner: str) -> None:
    """``joiner`` also owns ``owner``'s file and depends on ``owner`` (frontmatter plus ``tasks.md``)."""
    assert not (mission.feature_dir / "wps.yaml").exists(), "fixture amends frontmatter; wps.yaml would be the source"
    joiner_file = mission.feature_dir / "tasks" / WP_FILES[joiner]
    owner_file = mission.feature_dir / "tasks" / WP_FILES[owner]
    meta, body = read_frontmatter(joiner_file)
    owner_path = read_frontmatter(owner_file)[0]["owned_files"][0]
    meta["owned_files"] = [*meta["owned_files"], owner_path]
    meta["dependencies"] = [owner]
    write_frontmatter(joiner_file, meta, body)
    tasks_md = mission.feature_dir / "tasks.md"
    text = tasks_md.read_text(encoding="utf-8")
    heading = next(line for line in text.splitlines() if line.startswith(f"## Work Package {joiner}"))
    tasks_md.write_text(text.replace(heading, f"{heading}\n\n**Dependencies**: {owner}", 1), encoding="utf-8")


def add_wp03(mission: Mission) -> None:
    """A new planned WP03 owning its own file (``c.py``); it collides with nothing."""
    write_wp(mission.feature_dir, "WP03", ["c.py"], "FR-001", [])
    tasks_md = mission.feature_dir / "tasks.md"
    tasks_md.write_text(
        tasks_md.read_text(encoding="utf-8") + "\n## Work Package WP03: Third\n\nRequirement refs: FR-001\n",
        encoding="utf-8",
    )


def commit_amendment(mission: Mission) -> None:
    git(mission.repo, "add", ".")
    git(mission.repo, "commit", "-qm", "record execution and planning amendment")


def assert_saw_overlap(result: FinalizeResult) -> None:
    """The re-finalize actually read the amendment (non-vacuity of the amendment)."""
    report = result.payload.get("lanes", {}).get("collapse_report", {})
    rules = {event.get("rule") for event in report.get("events", [])} | set(report.get("by_rule", {}))
    assert "write_scope_overlap" in rules, f"the re-finalize did not see the overlap amendment: {report!r}"


@dataclass
class WriteSpy:
    """Directories the real status-event and lane-manifest writers were asked to write."""

    status_dirs: list[Path] = field(default_factory=list)
    lanes_dirs: list[Path] = field(default_factory=list)

    def status_writes_to(self, feature_dir: Path) -> list[Path]:
        return [d for d in self.status_dirs if d.resolve() == feature_dir.resolve()]

    def lanes_writes_to(self, feature_dir: Path) -> list[Path]:
        return [d for d in self.lanes_dirs if d.resolve() == feature_dir.resolve()]


def wrap_everywhere(monkeypatch: pytest.MonkeyPatch, original: Callable[..., object], record: Callable[..., None]) -> None:
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


def spy_writers(monkeypatch: pytest.MonkeyPatch) -> WriteSpy:
    """Record every status-event append and every ``write_lanes_json`` call.

    The status sinks are the two physical writers of ``status.events.jsonl``:
    ``append_event`` (line append) and ``append_raw_rows_atomic`` (the atomic
    batch writer every ``append_*_atomic*`` helper delegates to).
    """
    spy = WriteSpy()

    def _record_feature_dir(feature_dir: Path, *_args: object, **_kwargs: object) -> None:
        spy.status_dirs.append(Path(feature_dir))

    def _record_events_path(path: Path, *_args: object, **_kwargs: object) -> None:
        if Path(path).name == EVENTS:
            spy.status_dirs.append(Path(path).parent)

    def _record_lanes_dir(planning_dir: Path, *_args: object, **_kwargs: object) -> None:
        spy.lanes_dirs.append(Path(planning_dir))

    wrap_everywhere(monkeypatch, status_store.append_event, _record_feature_dir)
    wrap_everywhere(monkeypatch, status_store.append_raw_rows_atomic, _record_events_path)
    wrap_everywhere(monkeypatch, lanes_persistence.write_lanes_json, _record_lanes_dir)
    return spy


def snapshot(mission: Mission) -> dict[str, bytes]:
    paths = [mission.feature_dir / name for name in ("lanes.json", EVENTS, "tasks.md", "meta.json", "wps.yaml")]
    paths += sorted((mission.feature_dir / "tasks").glob("*.md"))
    return {str(path.relative_to(mission.feature_dir)): path.read_bytes() for path in paths if path.is_file()}
