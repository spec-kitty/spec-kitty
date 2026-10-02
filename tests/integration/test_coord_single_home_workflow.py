"""End-to-end single-home invariant for coordination-routed Missions (WP21, FR-015).

Drives the **production CLI** (``python -m specify_cli`` as a subprocess, with the
lane ``src`` first on ``PYTHONPATH`` so a stale install can never answer) through
the whole lifecycle of a coordination Mission:

    create -> decision open/resolve -> tracer-append -> spec-commit -> setup-plan
    -> finalize-tasks -> record-analysis -> implement WP01 -> move-task (approved)
    -> acceptance-verdict -> accept -> consolidate

for both coordination topologies (``coord``, ``lanes_with_coord``) and both
merge-base shapes (``linear``; ``moved_merge_base``, where the target gains an
unrelated commit and the lane absorbs it before consolidation).

Before consolidation it asserts the single-home invariant:

* SC-001 -- zero COORD-classified paths committed on the target in
  ``creation_base..target``;
* SC-002 / NFR-002 -- exactly one status log on disk, carrying every decision
  event, with a logical clock that never restarts and no duplicate event id.

Consolidation must then succeed with no ``TARGET_BRANCH_CONTENT_CONFLICT``.

T119 (FR-009b): decisions are durable from a fresh clone (``agent decision verify``
clean, ``doctor decisions`` ledger state ``primary``, every decision id found),
and the decision ledger (PRIMARY partition) is committed at the ``spec-commit``
commit point.

On the "logical clock": status-log rows do not persist a clock field. The clock the
decision commands report (``event_lamport``) is the 1-based append position of the
event in the one status log (``decisions/emit.py``: "Lamport proxy"). Asserting that
the reported value equals the event's position in the single log is therefore the
non-vacuous form of "the clock never restarts": a second log, a split stream or a
re-ordered projection all break the equality.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_RESOLVED

from mission_runtime import MissionTopology
from mission_runtime.artifacts import kind_for_mission_file, kind_is_coordination_residue
from specify_cli.consolidation.forecast import TARGET_BRANCH_CONTENT_CONFLICT
from tests._factories.coord_mission import CoordMission, event_ids, index_entry_ids, make_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SRC = str(Path(__file__).resolve().parents[2] / "src")
_CLI_TIMEOUT_SECONDS = 180
_STATUS_LOG = "status.events.jsonl"
_LEDGER_INDEX = "decisions/index.json"
_AGENT = "e2e"
_LANE_ID = "a"

_HEX40 = frozenset("0123456789abcdef")

_SPEC_MD = "# Spec\n\n## Functional Requirements\n\n| ID | Requirement | Status |\n|----|-------------|--------|\n| FR-001 | It works. | Draft |\n"
_TASKS_MD = "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\nImplement the demo.\n"
_WP01_MD = (
    "---\nwork_package_id: WP01\ntitle: Demo\ndependencies: []\nrequirement_refs: [FR-001]\n"
    "subtasks: []\nowned_files: [src/demo/**]\nauthoritative_surface: src/demo/\n"
    "execution_mode: code_change\n---\n\n# WP01\n\nImplement the demo.\n"
)
_ANALYSIS_MD = (
    "---\nschema: analysis-findings/v1\nfindings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


# ---------------------------------------------------------------------------
# Parametrization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Shape:
    """How a coordination Mission is created (the production create path)."""

    topology: MissionTopology
    via: Literal["cli_topology", "cli_pr_bound"]


_SHAPES = {
    # ``--pr-bound`` on an unprotected primary defaults to ``lanes``, so ``coord``
    # is requested explicitly (the factory passes ``--topology coord --pr-bound``).
    "coord": _Shape(MissionTopology.COORD, "cli_pr_bound"),
    "lanes_with_coord": _Shape(MissionTopology.LANES_WITH_COORD, "cli_topology"),
}


@pytest.fixture(params=sorted(_SHAPES))
def shape(request: pytest.FixtureRequest) -> _Shape:
    return _SHAPES[request.param]


@pytest.fixture(params=["linear", "moved_merge_base"])
def base_mode(request: pytest.FixtureRequest) -> str:
    return str(request.param)


# ---------------------------------------------------------------------------
# Subprocess + git plumbing
# ---------------------------------------------------------------------------


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(part for part in (_SRC, env.get("PYTHONPATH")) if part)
    env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    env["NO_COLOR"] = "1"
    return env


def _cli(repo: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    """Run ``spec-kitty <args>`` from *repo* against this lane's ``src``."""
    proc = subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=repo,
        env=_cli_env(),
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT_SECONDS,
        check=False,
    )
    assert proc.returncode == expect, (
        f"spec-kitty {' '.join(args)} exited {proc.returncode} (expected {expect})\nSTDOUT:\n{proc.stdout[-2500:]}\nSTDERR:\n{proc.stderr[-1500:]}"
    )
    return proc


def _json_payload(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Decode the first JSON object in stdout (tolerates a leading banner line)."""
    text = proc.stdout
    payload, _ = json.JSONDecoder().raw_decode(text[text.index("{") :])
    assert isinstance(payload, dict), text[-500:]
    return payload


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _git_commit(repo: Path, message: str) -> None:
    _git(repo, "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid", "commit", "-q", "-m", message)


def _show_rows(repo: Path, ref: str, relpath: str) -> list[dict[str, Any]]:
    text = _git(repo, "show", f"{ref}:{relpath}")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Invariant probes (pure; each has a non-vacuity self-check below)
# ---------------------------------------------------------------------------


def _is_coord_path(path: str, mission_dir: str, topology: MissionTopology) -> bool:
    kind = kind_for_mission_file(path, mission_slug=mission_dir)
    return kind is not None and kind_is_coordination_residue(kind, topology)


def _coord_paths_touched(repo: Path, rev_range: str, mission_dir: str, topology: MissionTopology) -> list[str]:
    """Return ``"<sha> <path>"`` for every COORD-classified Mission path committed in *rev_range*."""
    out = _git(repo, "log", "--name-only", "--format=%H", rev_range, "--", "kitty-specs/")
    offenders: list[str] = []
    sha = ""
    for line in out.splitlines():
        if not line:
            continue
        if len(line) == 40 and set(line) <= _HEX40:
            sha = line
        elif _is_coord_path(line, mission_dir, topology):
            offenders.append(f"{sha[:10]} {line}")
    return offenders


def _existing_logs(candidates: Sequence[Path]) -> list[Path]:
    """Return the status-log candidates that exist on disk."""
    return [path for path in candidates if path.exists()]


def _assert_unique_event_ids(rows: Sequence[Mapping[str, Any]], where: str) -> None:
    ids = [str(row["event_id"]) for row in rows if "event_id" in row]
    duplicates = sorted({event_id for event_id in ids if ids.count(event_id) > 1})
    assert not duplicates, f"duplicate event ids in {where}: {duplicates}"


def _decision_position(rows: Sequence[Mapping[str, Any]], decision_id: str, event_type: str) -> list[int]:
    return [
        index + 1 for index, row in enumerate(rows) if row.get("event_type") == event_type and (row.get("payload") or {}).get("decision_point_id") == decision_id
    ]


def _assert_clock_matches_log(rows: Sequence[Mapping[str, Any]], clock: Sequence[tuple[str, str, int]], where: str) -> None:
    """The reported clock strictly increases and equals each event's position in *rows*."""
    values = [value for _, _, value in clock]
    assert len(values) == len({*values}) and values == sorted(values), f"clock is not strictly increasing: {values}"
    for decision_id, event_type, value in clock:
        positions = _decision_position(rows, decision_id, event_type)
        assert positions == [value], (
            f"{event_type} {decision_id}: reported clock {value}, position(s) in {where}: {positions} -- "
            "the clock restarted, the stream forked, or the event is missing"
        )


# ---------------------------------------------------------------------------
# The driven Mission
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    mission: CoordMission
    decision_ids: list[str] = field(default_factory=list)
    clock: list[tuple[str, str, int]] = field(default_factory=list)
    moved_base_sha: str | None = None

    @property
    def repo(self) -> Path:
        return self.mission.repo_root

    @property
    def handle(self) -> str:
        return self.mission.mission_dir_name

    @property
    def rel(self) -> str:
        return f"kitty-specs/{self.mission.mission_dir_name}"

    @property
    def target(self) -> str:
        return self.mission.target_branch

    @property
    def lane_branch(self) -> str:
        return f"kitty/mission-{self.handle}-lane-{_LANE_ID}"

    @property
    def lane_worktree(self) -> Path:
        return self.repo / ".worktrees" / f"{self.handle}-lane-{_LANE_ID}"

    @property
    def coord_log(self) -> Path:
        return self.mission.coord_mission_dir / _STATUS_LOG


def _clock_value(payload: Mapping[str, Any]) -> int:
    value = payload.get("event_lamport")
    assert isinstance(value, int) and value > 0, f"decision command reported no clock: {payload}"
    return value


def _decision_open(run: _Run, slot: str) -> str:
    payload = _json_payload(
        _cli(
            run.repo, "agent", "decision", "open", "--mission", run.handle, "--flow", "specify",
            "--slot-key", f"s.{slot}", "--input-key", slot, "--question", f"Question {slot}?", "--json",
        )
    )  # fmt: skip
    decision_id = str(payload["decision_id"])
    run.decision_ids.append(decision_id)
    run.clock.append((decision_id, DECISION_POINT_OPENED, _clock_value(payload)))
    return decision_id


def _decision_resolve(run: _Run, decision_id: str) -> None:
    payload = _json_payload(_cli(run.repo, "agent", "decision", "resolve", decision_id, "--mission", run.handle, "--final-answer", "yes", "--json"))
    run.clock.append((decision_id, DECISION_POINT_RESOLVED, _clock_value(payload)))


def _ledger_files(run: _Run) -> list[str]:
    """Repo-relative paths of the decision ledger (index + one DM file per decision)."""
    decisions = run.repo / run.rel / "decisions"
    return [f"{run.rel}/{_LEDGER_INDEX}", *sorted(f"{run.rel}/decisions/{p.name}" for p in decisions.glob("DM-*.md"))]


def _ledger_dirty(run: _Run) -> str:
    return _git(run.repo, "status", "--porcelain", "--", f"{run.rel}/decisions")


def _spec_commit(run: _Run, message: str, *paths: str) -> None:
    proc = _cli(run.repo, "spec-commit", "--mission", run.handle, "-m", message, *paths, "--json")
    assert _json_payload(proc)["success"] is True, proc.stdout[-1500:]


def _tip_files(run: _Run) -> set[str]:
    return set(_git(run.repo, "log", "-1", "--name-only", "--format=", run.target).splitlines())


def _assert_ledger_committed_at_tip(run: _Run, expected: Sequence[str]) -> None:
    """FR-009b: ``spec-kitty spec-commit`` is a ledger commit point -- it lands *expected* on the target."""
    assert _ledger_dirty(run) == "", f"ledger still dirty after a spec-commit: {_ledger_dirty(run)}"
    tip = _tip_files(run)
    missing = sorted(set(expected) - tip)
    assert not missing, f"ledger paths not in the target tip commit: {missing} (tip: {sorted(tip)})"


def _plant_batch_one(run: _Run) -> None:
    first = _decision_open(run, "a")
    _decision_resolve(run, first)
    _cli(
        run.repo, "agent", "tracer-append", "--mission", run.handle, "--category", "approach",
        "--entry", "e2e entry", "--actor", _AGENT, "--json",
    )  # fmt: skip
    _decision_open(run, "b")
    assert _ledger_dirty(run) != "", "decision open left no uncommitted ledger -- the commit-point check would be vacuous"
    (run.repo / run.rel / "spec.md").write_text(_SPEC_MD, encoding="utf-8")
    # status log and tracer file are COORD paths: the router sends them to the coordination surface.
    _spec_commit(run, "spec batch", f"{run.rel}/spec.md", *_ledger_files(run), f"{run.rel}/traces/approach.md", f"{run.rel}/{_STATUS_LOG}")
    _assert_ledger_committed_at_tip(run, [f"{run.rel}/spec.md", *_ledger_files(run)])


def _plan_and_tasks(run: _Run) -> None:
    _cli(run.repo, "agent", "mission", "setup-plan", "--mission", run.handle, "--json")
    _spec_commit(run, "plan", f"{run.rel}/plan.md")
    (run.repo / run.rel / "tasks").mkdir(exist_ok=True)
    (run.repo / run.rel / "tasks.md").write_text(_TASKS_MD, encoding="utf-8")
    (run.repo / run.rel / "tasks" / "WP01-demo.md").write_text(_WP01_MD, encoding="utf-8")
    _cli(run.repo, "agent", "mission", "finalize-tasks", "--mission", run.handle, "--json")
    # The analysis input lives OUTSIDE the repo: an in-repo input makes record-analysis refuse a dirty tree.
    analysis = run.repo.parent / "analysis-input.md"
    analysis.write_text(_ANALYSIS_MD, encoding="utf-8")
    _cli(run.repo, "agent", "mission", "record-analysis", "--mission", run.handle, "--input-file", str(analysis))


def _implement_wp01(run: _Run) -> None:
    _cli(run.repo, "agent", "action", "implement", "WP01", "--agent", _AGENT, "--mission", run.handle)
    lane = run.lane_worktree
    assert lane.is_dir(), f"implement did not materialize {lane}"
    (lane / "src" / "demo").mkdir(parents=True)
    (lane / "src" / "demo" / "a.py").write_text("X = 1\n", encoding="utf-8")
    _git(lane, "add", "src")
    _git_commit(lane, "feat(WP01): demo")


def _move_merge_base(run: _Run) -> None:
    """Advance the target with an unrelated commit and absorb it into the lane (merge base moves)."""
    (run.repo / "docs").mkdir(exist_ok=True)
    (run.repo / "docs" / "unrelated.md").write_text("unrelated\n", encoding="utf-8")
    _git(run.repo, "add", "docs/unrelated.md")
    _git_commit(run.repo, "docs: unrelated target-side commit")
    run.moved_base_sha = _git(run.repo, "rev-parse", run.target)
    _git(run.lane_worktree, "-c", "user.name=e2e", "-c", "user.email=e2e@example.invalid", "merge", "--no-edit", run.target)
    merge_base = _git(run.repo, "merge-base", run.target, run.lane_branch)
    assert merge_base == run.moved_base_sha != run.mission.creation_base_sha, "the merge base did not move"


def _decide_mid_flight(run: _Run) -> None:
    """A decision opened after many lane transitions: the clock must keep counting in the same log."""
    decision_id = _decision_open(run, "c")
    assert _ledger_dirty(run) != "", "mid-flight decision left no uncommitted ledger"
    _spec_commit(run, "decision c", *_ledger_files(run))
    _assert_ledger_committed_at_tip(run, [f"{run.rel}/{_LEDGER_INDEX}", f"{run.rel}/decisions/DM-{decision_id}.md"])


def _approve_wp01(run: _Run) -> None:
    for lane in ("for_review", "in_review", "approved"):
        _cli(
            run.repo, "agent", "tasks", "move-task", "WP01", "--to", lane, "--mission", run.handle,
            "--agent", _AGENT, "--force", "--note", _AGENT,
        )  # fmt: skip
    _cli(
        run.repo, "agent", "acceptance-verdict", "--mission", run.handle, "--criterion", "FR-001", "--result", "pass",
        "--verification-method", "e2e", "--actor", _AGENT, "--evidence", "e2e",
    )  # fmt: skip


def _accept_commits_uncommitted_ledger(run: _Run) -> None:
    """FR-009b / G1: ``accept`` is a ledger committer -- it lands a decision left uncommitted.

    The ledger commit points are ``spec-commit`` and ``accept`` only (``plan.scope.ledger-committers``).
    """
    decision_id = _decision_open(run, "d")
    dirty_before = _ledger_dirty(run)
    assert dirty_before != "", "mid-flight decision left no uncommitted ledger -- the accept leg would be vacuous"
    # --lenient: the Software-Dev path-convention warnings (tests/, docs/) are not under test here.
    _cli(run.repo, "accept", "--mission", run.handle, "--json", "--actor", _AGENT, "--lenient")
    _assert_ledger_committed_at_tip(run, [f"{run.rel}/{_LEDGER_INDEX}", f"{run.rel}/decisions/DM-{decision_id}.md"])


def _assert_fresh_clone_durable(run: _Run, name: str) -> None:
    """T119: a fresh clone carries the whole decision ledger, and the decision commands read it clean."""
    clone = run.repo.parent / name
    subprocess.run(["git", "clone", "-q", str(run.repo), str(clone)], check=True, capture_output=True)
    verify = _json_payload(_cli(clone, "agent", "decision", "verify", "--mission", run.handle, "--json"))
    assert verify["status"] == "clean" and verify["findings"] == [], verify
    doctor = _json_payload(_cli(clone, "doctor", "decisions", "--mission", run.handle, "--json"))
    assert doctor["ledger"]["state"] == "primary", doctor["ledger"]
    assert doctor["forked"] is False
    expected = set(run.decision_ids)
    assert expected <= set(doctor["index_decision_ids"]), (expected, doctor["index_decision_ids"])
    assert expected <= index_entry_ids(clone / run.rel / _LEDGER_INDEX)
    missing = [d for d in sorted(expected) if not (clone / run.rel / "decisions" / f"DM-{d}.md").is_file()]
    assert not missing, f"decision files absent from the fresh clone: {missing}"


# ---------------------------------------------------------------------------
# Pre- and post-consolidation assertions
# ---------------------------------------------------------------------------


def _assert_single_home(run: _Run) -> None:
    mission = run.mission
    # Non-vacuity: the run really is the requested coordination topology with a live coordination surface.
    meta = json.loads((run.repo / run.rel / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("topology") == mission.topology.value, meta.get("topology")
    assert run.coord_log.exists(), "the coordination status log does not exist: the run exercised nothing"

    # SC-001: no COORD path committed on the target before consolidation.
    offenders = _coord_paths_touched(run.repo, f"{mission.creation_base_sha}..{run.target}", run.handle, mission.topology)
    assert offenders == [], f"COORD paths committed on {run.target} before consolidation: {offenders}"

    # SC-002: exactly one status log on disk -- the coordination one.
    candidates = [run.repo / run.rel / _STATUS_LOG, run.coord_log, run.lane_worktree / run.rel / _STATUS_LOG]
    assert _existing_logs(candidates) == [run.coord_log], f"status logs on disk: {_existing_logs(candidates)}"

    rows = [json.loads(line) for line in run.coord_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    _assert_unique_event_ids(rows, "the coordination status log")
    assert len(event_ids(run.coord_log)) == len(rows)
    for decision_id in run.decision_ids:  # every decision is present in the one log
        assert _decision_position(rows, decision_id, DECISION_POINT_OPENED), f"{decision_id} not in the status log"
    _assert_clock_matches_log(rows, run.clock, "the coordination status log")
    assert len(rows) >= max(value for _, _, value in run.clock), "the log is shorter than the reported clock"


def _consolidate(run: _Run) -> str:
    dry = _cli(run.repo, "consolidate", "--mission", run.handle, "--dry-run", "--json")
    assert TARGET_BRANCH_CONTENT_CONFLICT not in dry.stdout + dry.stderr, dry.stdout[-1500:]
    real = _cli(run.repo, "consolidate", "--mission", run.handle)
    combined = real.stdout + real.stderr
    assert TARGET_BRANCH_CONTENT_CONFLICT not in combined, combined[-2500:]
    return combined


def _assert_consolidated(run: _Run) -> None:
    rel_log = f"{run.rel}/{_STATUS_LOG}"
    tree = set(_git(run.repo, "ls-tree", "-r", "--name-only", run.target).splitlines())
    assert "src/demo/a.py" in tree, "the lane's work did not reach the target"
    if run.moved_base_sha is not None:
        assert "docs/unrelated.md" in tree, "the target-side commit was lost by consolidation"
        _git(run.repo, "merge-base", "--is-ancestor", run.moved_base_sha, run.target)
    assert _git(run.repo, "branch", "--list", run.lane_branch) == "", "the lane branch survived consolidation"
    assert rel_log in tree, "the status log was not projected onto the target"

    rows = _show_rows(run.repo, run.target, rel_log)
    _assert_unique_event_ids(rows, f"{run.target}:{rel_log}")
    _assert_clock_matches_log(rows, run.clock, f"{run.target}:{rel_log}")
    assert set(run.decision_ids) <= index_entry_ids((run.repo, run.target, f"{run.rel}/{_LEDGER_INDEX}"))


# ---------------------------------------------------------------------------
# The end-to-end test
# ---------------------------------------------------------------------------


def test_coord_single_home_workflow(tmp_path: Path, shape: _Shape, base_mode: str) -> None:
    """FR-015: a coordination Mission keeps ONE home for its artifacts from create to consolidate."""
    mission = make_coord_mission(tmp_path, shape.topology, via=shape.via, slug="e2e")
    run = _Run(mission)
    (run.repo / ".git" / "info" / "exclude").write_text(".worktrees/\n.kittify/derived/\n.kittify/workspaces/\n*.lock\n")

    _plant_batch_one(run)
    _assert_fresh_clone_durable(run, "fresh-clone-batch-one")
    _plan_and_tasks(run)
    _implement_wp01(run)
    if base_mode == "moved_merge_base":
        _move_merge_base(run)
    _decide_mid_flight(run)
    _assert_fresh_clone_durable(run, "fresh-clone-mid-flight")
    _approve_wp01(run)
    _accept_commits_uncommitted_ledger(run)

    _assert_single_home(run)
    _consolidate(run)
    _assert_consolidated(run)


# ---------------------------------------------------------------------------
# Non-vacuity self-checks (T114): each probe must be able to fail
# ---------------------------------------------------------------------------

_MISSION_DIR = "demo-01ABCDEF"
_COORD_FILES = [
    "status.events.jsonl",
    "status.json",
    "acceptance-matrix.json",
    "issue-matrix.json",
    "decisions.events.jsonl",
    "traces/approach.md",
    "tasks/WP01-demo/review-cycle-1.md",
]
_PRIMARY_FILES = ["spec.md", "plan.md", "tasks.md", "meta.json", "lanes.json", "decisions/index.json", "tasks/WP01-demo.md"]


def _scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "scratch"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git_commit(repo, "base")
    return repo


def _commit_mission_file(repo: Path, name: str) -> None:
    path = repo / "kitty-specs" / _MISSION_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    _git(repo, "add", str(path.relative_to(repo)))
    _git_commit(repo, f"add {name}")


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD])
@pytest.mark.parametrize("name", _COORD_FILES)
def test_sc001_probe_flags_a_planted_coord_commit(tmp_path: Path, topology: MissionTopology, name: str) -> None:
    repo = _scratch_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit_mission_file(repo, name)
    offenders = _coord_paths_touched(repo, f"{base}..HEAD", _MISSION_DIR, topology)
    assert [o.split(" ", 1)[1] for o in offenders] == [f"kitty-specs/{_MISSION_DIR}/{name}"]


@pytest.mark.parametrize("name", _PRIMARY_FILES)
def test_sc001_probe_ignores_primary_paths(tmp_path: Path, name: str) -> None:
    repo = _scratch_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _commit_mission_file(repo, name)
    assert _coord_paths_touched(repo, f"{base}..HEAD", _MISSION_DIR, MissionTopology.COORD) == []


def test_status_log_census_flags_a_second_log(tmp_path: Path) -> None:
    root, coord = tmp_path / "root.jsonl", tmp_path / "coord.jsonl"
    coord.write_text("{}\n", encoding="utf-8")
    assert _existing_logs([root, coord]) == [coord]
    root.write_text("{}\n", encoding="utf-8")
    assert _existing_logs([root, coord]) == [root, coord]


def test_duplicate_event_id_is_detected() -> None:
    rows: list[dict[str, Any]] = [{"event_id": "A"}, {"event_id": "B"}, {"event_id": "A"}]
    _assert_unique_event_ids(rows[:2], "unique")
    with pytest.raises(AssertionError, match="duplicate event ids"):
        _assert_unique_event_ids(rows, "duplicated")


def _decision_row(decision_id: str, event_type: str) -> dict[str, Any]:
    return {"event_type": event_type, "payload": {"decision_point_id": decision_id}}


def test_clock_check_accepts_a_log_position_clock_and_rejects_a_restart() -> None:
    rows: list[dict[str, Any]] = [
        {"event_type": "MissionCreated"},
        _decision_row("D1", DECISION_POINT_OPENED),
        _decision_row("D1", DECISION_POINT_RESOLVED),
        {"event_type": "other"},
        _decision_row("D2", DECISION_POINT_OPENED),
    ]
    good = [("D1", DECISION_POINT_OPENED, 2), ("D1", DECISION_POINT_RESOLVED, 3), ("D2", DECISION_POINT_OPENED, 5)]
    _assert_clock_matches_log(rows, good, "fixture")
    restarted = [("D1", DECISION_POINT_OPENED, 2), ("D1", DECISION_POINT_RESOLVED, 3), ("D2", DECISION_POINT_OPENED, 1)]
    with pytest.raises(AssertionError, match="not strictly increasing"):
        _assert_clock_matches_log(rows, restarted, "fixture")
    forked = [("D1", DECISION_POINT_OPENED, 1)]  # a clock counted in a different log than the one read
    with pytest.raises(AssertionError, match="clock restarted"):
        _assert_clock_matches_log(rows, forked, "fixture")
    with pytest.raises(AssertionError, match="clock restarted"):
        _assert_clock_matches_log(rows[:1], good[:1], "fixture")  # the decision event is absent from the log


def test_clock_value_requires_a_reported_clock() -> None:
    assert _clock_value({"event_lamport": 7}) == 7
    for bad in ({}, {"event_lamport": None}, {"event_lamport": 0}):
        with pytest.raises(AssertionError, match="reported no clock"):
            _clock_value(bad)
