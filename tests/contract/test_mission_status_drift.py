"""Tests of the reference drift reader of the ``mission-status`` contract (FR-008 to FR-015, FR-024; AC-DRIFT 1 to 15, 17 to 28; AC-CROSS 1, 4, 5).

Every rule has a row function that builds fixture repositories, calls the production entry point (``scan_drift``) and returns the problems it
found; a test asserts the list is empty, and the mutation table (proof kind M) swaps one reader function for its defective twin and asserts
that some row of that mutation goes red (``the mutation was not killed: <name>``). Each row is its own control: the clean input beside the plant
on the same fixture shape, so a probe that sees nothing fails. Repositories are written at run time into a temporary directory; real git is used
where git matters (a branch, a coordination worktree, a remote, the resolver) under a scratch HOME. Values a leak scan would flag are assembled
from fragments. The module reads no corpus directory: the corpus-sized cases live in the reality module.
"""

from __future__ import annotations

import ast
import builtins
import functools
import io
import json
import random
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from kernel.clock import FrozenClock, parse_iso, timedelta
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, WorktreeRegistryUnavailable
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.git.remote_probes import _reset_remote_branch_lookup_cache
from specify_cli.lanes.branch_naming import code_lane_branch_name, coord_mission_dir_name
from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
from specify_cli.status import reducer
from specify_cli.status.aggregate import CoordAuthorityUnavailable, InvalidMissionSlug, MissionMetadataUnavailable, MissionStatus
from specify_cli.status.lifecycle import is_mission_completed
from tests.contract import _mission_status_drift as drift
from tests.contract import _mission_status_memo as memo_module
from tests.contract import _mission_status_payloads as helper

pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
SCHEMA_DIR = MODULE_DIR / "schemas"
READER_FILE = Path(__file__).with_name("_mission_status_drift.py")
NOT_KILLED = "the mutation was not killed"
FAULT_NOT_FIRED = "the injected fault did not fire"
T0 = parse_iso("2026-10-06T09:00:00+00:00")
SCANNED_AT = "2026-10-06T09:00:00Z"
SLUG = "alpha"
LANE_ID = "lane-a"
LANE_BRANCH = code_lane_branch_name(SLUG, LANE_ID)
MISSION_BRANCH = f"kitty/mission-{SLUG}"
COORD_BRANCH = f"kitty/coord-{SLUG}"
LANE_PATH = ("planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done")
SNAPSHOT = "status.json"
EVENT_LOG = "status.events.jsonl"
LANES = "lanes.json"
KIND1 = "snapshot_disagrees_with_event_log"
KIND2 = "snapshot_or_event_log_missing"
KIND3 = "lane_branch_missing"
WRITE_MODES = ("w", "a", "x", "+")
UNREADABLE = "drift_scan_unreadable"
# The six fixed sentences, typed here independently of the reader (the closed pair table of FR-014).
SENTENCES: dict[tuple[str, str | None], str] = {
    (KIND1, "SNAPSHOT_DRIFT"): "The status snapshot disagrees with the event log.",
    (KIND1, "SNAPSHOT_DRIFT_PROVENANCE"): "The status snapshot differs from the event log only in provenance fields.",
    (KIND1, "SNAPSHOT_DRIFT_TERMINAL"): "The status snapshot differs from the event log and every work package is done.",
    (KIND1, "CORRUPT_JSON"): "The status snapshot is not a valid JSON object.",
    (KIND2, None): "One of the status snapshot and the event log is missing.",
    (KIND3, None): "An expected lane or Mission branch has no local branch.",
}
# A retired term is assembled from fragments, so this module never types it (AC-VERSION, bullet 5).
RETIRED = "fea" + "ture"


class UnexpectedWrite(AssertionError):
    """A write the reader attempted: the stubs of every writing function raise it."""


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as patch:
        yield helper.load_contract_tools(patch, REPO_ROOT)


@pytest.fixture(autouse=True)
def scratch_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real git runs with a scratch HOME and no system or global configuration."""
    home = tmp_path / "scratch-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))


def _titled(tree: Any, found: dict[str, dict[str, Any]]) -> None:
    if isinstance(tree, list):
        for item in tree:
            _titled(item, found)
    elif isinstance(tree, dict):
        title = tree.get("title")
        if isinstance(title, str) and isinstance(tree.get("examples"), list):
            found.setdefault(title, tree)
        for key, value in tree.items():
            if key not in {"examples", "example", "default", "enum", "const"}:
                _titled(value, found)


@dataclass
class Env:
    """One scratch area for a row: a fresh directory per repository, the contract validators and the leak tools."""

    root: Path
    tools: helper.ContractTools
    validators: Mapping[str, Draft202012Validator]
    made: int = 0

    def fresh(self) -> Path:
        self.made += 1
        directory = self.root / f"repo{self.made}"
        directory.mkdir()
        return directory

    def errors(self, title: str, instance: Any) -> list[str]:
        found = sorted(self.validators[title].iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path])
        return ["/" + "/".join(str(part) for part in error.absolute_path) + ": " + error.message[:160] for error in found]


@pytest.fixture
def env(tmp_path: Path, tools: helper.ContractTools) -> Env:
    area = tmp_path / "rows"
    area.mkdir()
    nodes: dict[str, dict[str, Any]] = {}
    _titled(tools.resolver.resolve(MODULE_DIR).tree, nodes)
    validators = {title: Draft202012Validator(nodes[title], format_checker=tools.formats.FORMAT_CHECKER) for title in ("DriftReport", "DriftRefusal")}
    return Env(area, tools, validators)


# ---------------------------------------------------------------------------
# Fixture repositories
# ---------------------------------------------------------------------------


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


def new_repo(env: Env, *, git: bool = True) -> Path:
    """A fresh repository whose ``HEAD`` points at ``main`` (unborn until ``commit``), or a plain directory when ``git`` is false."""
    repo = env.fresh()
    if git:
        _git(repo, "init", "-q")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    return repo


def commit(repo: Path, *branches: str) -> None:
    """Commit everything and create the named local branches at that commit."""
    helper.commit_all(repo)
    for branch in branches:
        _git(repo, "branch", branch)


def _stamp(minutes: int) -> str:
    return (parse_iso("2026-09-01T10:00:00+00:00") + timedelta(minutes=minutes)).isoformat()


def rows_for(plan: Mapping[str, str]) -> list[dict[str, Any]]:
    """The event rows that bring each work package of ``plan`` from genesis to its lane along the usual path."""
    rows: list[dict[str, Any]] = []
    for index, (wp_id, lane) in enumerate(plan.items()):
        number, previous = index * 10 + 1, "genesis"
        for step in LANE_PATH[: LANE_PATH.index(lane) + 1] if lane in LANE_PATH else ("planned", lane):
            rows.append(helper.transition_row(number, wp_id, previous, step, at=_stamp(number)))
            previous, number = step, number + 1
    return rows


def replay_text(mission_dir: Path) -> str:
    """The text of the snapshot the reducer gives for the Mission directory (what ``materialize`` would write)."""
    return str(reducer.materialize_to_json(reducer.materialize_snapshot(mission_dir)))


def canonical(document: Any) -> str:
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def edit_snapshot(mission_dir: Path, change: Callable[[dict[str, Any]], None]) -> None:
    document = json.loads((mission_dir / SNAPSHOT).read_text(encoding="utf-8"))
    change(document)
    (mission_dir / SNAPSHOT).write_text(canonical(document), encoding="utf-8")


def manifest(slug: str, lanes: Mapping[str, Sequence[str]], *, number: int = 1, mission_branch: str | None = None) -> dict[str, Any]:
    """A lane manifest of the current shape."""
    return {
        "version": 1,
        "mission_slug": slug,
        "mission_id": helper.fixture_ulid(number),
        "mission_branch": mission_branch or f"kitty/mission-{slug}",
        "target_branch": "main",
        "lanes": [
            {"lane_id": lane_id, "wp_ids": list(wp_ids), "write_scope": [], "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0}
            for lane_id, wp_ids in lanes.items()
        ],
        "computed_at": "2026-09-01T10:00:00+00:00",
        "computed_from": "fixture",
    }


def legacy_manifest(number: int = 1) -> dict[str, Any]:
    """A manifest of the shape that predates ``mission_slug`` (the retired key is assembled from fragments)."""
    return {"version": 1, RETIRED + "_slug": SLUG, "mission_id": helper.fixture_ulid(number), "lanes": []}


def mission(
    repo: Path,
    name: str,
    number: int,
    plan: Mapping[str, str] | None = None,
    *,
    snapshot: str | bytes | None = "replay",
    log: bool = True,
    meta: Mapping[str, Any] | None = None,
    lanes: Mapping[str, Any] | str | bytes | None = None,
    files: Mapping[str, str | bytes] | None = None,
    extra_rows: Sequence[Mapping[str, Any]] = (),
) -> Path:
    """One fixture Mission. ``snapshot`` is ``"replay"`` (a snapshot equal to the replay), text or bytes written as given, or None (no file)."""
    mission_dir = helper.write_fixture_mission(
        repo,
        name,
        meta={"mission_id": helper.fixture_ulid(number), **(meta or {})},
        rows=[*rows_for(plan or {"WP01": "planned"}), *extra_rows],
        files=files,
        lanes=lanes if isinstance(lanes, Mapping) else None,
    )
    if isinstance(lanes, str | bytes):
        (mission_dir / LANES).write_bytes(lanes if isinstance(lanes, bytes) else lanes.encode("utf-8"))
    if snapshot == "replay":
        (mission_dir / SNAPSHOT).write_text(replay_text(mission_dir), encoding="utf-8")
    elif isinstance(snapshot, bytes):
        (mission_dir / SNAPSHOT).write_bytes(snapshot)
    elif snapshot is not None:
        (mission_dir / SNAPSHOT).write_text(snapshot, encoding="utf-8")
    if not log:
        (mission_dir / EVENT_LOG).unlink()
    return mission_dir


class _Status:
    def __init__(self, read_dir: Path) -> None:
        self.read_dir = read_dir


@contextmanager
def resolver_returns(read_dir_of: Callable[[Path, str], Path]) -> Iterator[None]:
    """The coordination resolver answers the directory ``read_dir_of`` names (a patched resolver, never git)."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MissionStatus, "load", classmethod(lambda cls, repo_root, name: _Status(read_dir_of(Path(repo_root), name))))
        yield


@contextmanager
def own_dirs() -> Iterator[None]:
    with resolver_returns(lambda repo_root, name: repo_root / "kitty-specs" / name):
        yield


@contextmanager
def resolver_raises(error_of: Callable[[Path, str], Exception]) -> Iterator[None]:
    def load(cls: Any, repo_root: Path, name: str) -> Any:
        raise error_of(Path(repo_root), name)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MissionStatus, "load", classmethod(load))
        yield


def scan(env: Env, repo: Path, *, mission_id: str | None = None, memo: memo_module.ResolverMemo | None = None, **options: Any) -> drift.DriftOutcome:
    """The production entry point, with a fixed clock and a fresh memo unless one is given."""
    return drift.scan_drift(repo, memo or memo_module.ResolverMemo(), clock=FrozenClock(instant=T0), mission_id=mission_id, **options)


def expected_finding(
    kind: str,
    number: int,
    path: str,
    code: str | None,
    *,
    severity: str,
    remedy: str | None,
    comparison: Sequence[Mapping[str, Any]] = (),
    mission_id: str | None = None,
) -> dict[str, Any]:
    """The finding the contract fixes for these facts, written out in full."""
    return {
        "kind": kind,
        "severity": severity,
        "missionId": mission_id or helper.fixture_ulid(number),
        "artifactPath": path,
        "summary": SENTENCES[(kind, code)],
        "authority": "git" if kind == KIND3 else "event_log",
        "derivedSide": "lanes_json" if kind == KIND3 else "status_json",
        "laneComparison": [dict(row) for row in comparison],
        "remedy": remedy,
        "sourceCode": code,
    }


def lane_row(wp_id: str, persisted: str | None, derived: str | None) -> dict[str, Any]:
    return {"wpId": wp_id, "persistedStatusLane": persisted, "derivedStatusLane": derived}


def check(env: Env, label: str, outcome: drift.DriftOutcome, want: Sequence[Mapping[str, Any]] | int, problems: list[str]) -> None:
    """Record why ``outcome`` is not the 200 with the findings ``want``, or the refusal status ``want`` (an int)."""
    if isinstance(want, int):
        if outcome.status != want:
            problems.append(f"{label}: status {outcome.status}, expected {want}")
        return
    if outcome.status != 200:
        problems.append(f"{label}: status {outcome.status} ({outcome.body.get('code')}), expected 200")
        return
    if outcome.body["findings"] != [dict(finding) for finding in want]:
        problems.append(f"{label}: findings {outcome.body['findings']!r}, expected {list(want)!r}")
    problems += [f"{label}: {error}" for error in env.errors("DriftReport", outcome.body)]


# ---------------------------------------------------------------------------
# AC-DRIFT 1 and 2: kind 1, its variants, the corrupt snapshot and the 500s
# ---------------------------------------------------------------------------

EVERY_WP = {"WP01": "approved", "WP02": "claimed"}
ALL_DONE = {"WP01": "done"}


def _kind1_case(
    env: Env, label: str, plan: Mapping[str, str], change: Callable[[dict[str, Any]], None] | None, want: Sequence[Mapping[str, Any]], problems: list[str]
) -> None:
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, plan)
    if change is not None:
        edit_snapshot(mission_dir, change)
    check(env, label, scan(env, repo), want, problems)


def _set_lane(wp_id: str, lane: str) -> Callable[[dict[str, Any]], None]:
    def change(document: dict[str, Any]) -> None:
        document["work_packages"][wp_id]["lane"] = lane

    return change


def _set_actor(document: dict[str, Any]) -> None:
    document["work_packages"]["WP01"]["actor"] = "someone-else"


def row1_problems(env: Env) -> list[str]:
    problems: list[str] = []
    drift_error = expected_finding(
        KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT", severity="error", remedy="materialize_status", comparison=[lane_row("WP01", "planned", "approved")]
    )
    provenance = expected_finding(KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT_PROVENANCE", severity="warning", remedy=None)
    terminal = expected_finding(KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT_TERMINAL", severity="warning", remedy=None, comparison=[lane_row("WP01", "approved", "done")])
    _kind1_case(env, "WP01 planned in the snapshot, approved in the log", EVERY_WP, _set_lane("WP01", "planned"), [drift_error], problems)
    _kind1_case(env, "a provenance-only edit", EVERY_WP, _set_actor, [provenance], problems)
    _kind1_case(env, "every work package done", ALL_DONE, _set_lane("WP01", "approved"), [terminal], problems)
    _kind1_case(env, "provenance only beside every work package done (provenance is tested first)", ALL_DONE, _set_actor, [provenance], problems)
    _kind1_case(env, "the unmodified control", EVERY_WP, None, [], problems)
    return problems


def _corrupt_cases() -> list[tuple[str, str | bytes]]:
    return [
        ("not JSON", "{not json"),
        ("a list", "[1, 2]"),
        ("a scalar", "7"),
        ("empty", ""),
        ("not UTF-8", b'{"a": "\xff\xfe"}'),
        ("nested too deep", "[" * 100000),
    ]


def row2_problems(env: Env) -> list[str]:
    problems: list[str] = []
    corrupt = expected_finding(KIND1, 1, SNAPSHOT, "CORRUPT_JSON", severity="error", remedy="materialize_status")
    for label, content in _corrupt_cases():
        repo = new_repo(env)
        mission(repo, SLUG, 1, snapshot=content)
        check(env, f"a snapshot that is {label}", scan(env, repo), [corrupt], problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1)
    check(env, "the control before corruption", scan(env, repo), [], problems)
    broken_log = new_repo(env)
    mission(broken_log, SLUG, 1, snapshot="{}", files={EVENT_LOG: "{not json\n"})
    check(env, "a corrupt event log", scan(env, broken_log), 500, problems)
    log_only = new_repo(env)
    mission(log_only, SLUG, 1, snapshot=None, files={EVENT_LOG: "{not json\n"})
    check(env, "a corrupt event log with no snapshot (the lifecycle reads it)", scan(env, log_only), 500, problems)
    undecodable_log = new_repo(env)
    mission(undecodable_log, SLUG, 1, snapshot="{}", files={EVENT_LOG: b"\xff\xfe\n"})
    check(env, "an event log that is not UTF-8", scan(env, undecodable_log), 500, problems)
    return problems


def _fault_on(name: str) -> drift.FileSystem:
    """A seam whose read of the file ``name`` raises ``OSError``; every other call is real."""

    def read_bytes(path: Path) -> bytes:
        if path.name == name:
            raise PermissionError(name)
        return path.read_bytes()

    return drift.FileSystem(exists=Path.exists, read_bytes=read_bytes)


def _directory_snapshot(env: Env) -> Path:
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1)
    (mission_dir / SNAPSHOT).unlink()
    (mission_dir / SNAPSHOT).mkdir()
    return repo


def row2_oserror_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = new_repo(env)
    mission(repo, SLUG, 1)
    check(env, "an OSError reading status.json", scan(env, repo, fs=_fault_on(SNAPSHOT)), 500, problems)
    check(env, "the control with the real seam", scan(env, repo), [], problems)

    def exists_fails(path: Path) -> bool:
        raise PermissionError(path.name)

    check(env, "an OSError asking whether a file exists", scan(env, repo, fs=drift.FileSystem(exists=exists_fails, read_bytes=Path.read_bytes)), 500, problems)
    check(env, "a status.json that is a directory", scan(env, _directory_snapshot(env)), 500, problems)
    check(env, "a fault on a file the reader does not read for a Mission without lanes.json", scan(env, repo, fs=_fault_on(LANES)), [], problems)
    with pytest.MonkeyPatch.context() as patch:

        def raises(feature_dir: Path) -> Any:
            raise RuntimeError("the reducer failed")

        patch.setattr(drift, "materialize_snapshot", raises)
        check(env, "a reducer that raises", scan(env, repo), 500, problems)
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 3: laneComparison rows and nulls
# ---------------------------------------------------------------------------


def row3_problems(env: Env) -> list[str]:
    problems: list[str] = []
    plain = {"WP01": "approved"}
    repo = new_repo(env)
    mission(repo, SLUG, 1, plain)
    edit_snapshot(repo / "kitty-specs" / SLUG, _set_lane("WP01", "planned"))
    check(env, "a plain lane difference", scan(env, repo), [_drift(1, [lane_row("WP01", "planned", "approved")])], problems)

    def one_sided(document: dict[str, Any]) -> None:
        del document["work_packages"]["WP02"]
        document["work_packages"]["WP03"] = {"lane": "in_progress", "actor": "x", "force_count": 0, "last_event_id": "x", "last_transition_at": "x"}
        document["work_packages"]["WP99"]["lane"] = "planned"
        document["work_packages"]["WP100"]["lane"] = "planned"

    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, {"WP02": "claimed", "WP99": "approved", "WP100": "approved"})
    edit_snapshot(mission_dir, one_sided)
    rows = [
        lane_row("WP02", None, "claimed"),
        lane_row("WP03", "in_progress", None),
        lane_row("WP100", "planned", "approved"),
        lane_row("WP99", "planned", "approved"),
    ]
    check(env, "work packages on one side only, in byte order (WP100 before WP99)", scan(env, repo), [_drift(1, rows)], problems)

    def genesis(document: dict[str, Any]) -> None:
        document["work_packages"]["WP01"]["lane"] = "genesis"
        document["work_packages"]["WP02"]["lane"] = "uninitialized"

    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, {"WP01": "planned", "WP02": "claimed"})
    edit_snapshot(mission_dir, genesis)
    check(
        env,
        "a lane outside the nine display lanes reads null",
        scan(env, repo),
        [_drift(1, [lane_row("WP01", None, "planned"), lane_row("WP02", None, "claimed")])],
        problems,
    )

    def odd_shapes(document: dict[str, Any]) -> None:
        document["work_packages"]["not-a-wp"] = {"lane": "done"}
        document["work_packages"]["WP02"] = 5

    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, {"WP01": "planned", "WP02": "claimed"})
    edit_snapshot(mission_dir, odd_shapes)
    check(
        env,
        "an id that is not a work package id is not a row; an entry that is not an object reads null",
        scan(env, repo),
        [_drift(1, [lane_row("WP02", None, "claimed")])],
        problems,
    )
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, {"WP01": "planned"})
    edit_snapshot(mission_dir, lambda document: document.update(work_packages=[]))
    check(env, "work_packages that is not an object", scan(env, repo), [_drift(1, [lane_row("WP01", None, "planned")])], problems)
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, snapshot="{}", files={EVENT_LOG: json.dumps(helper.lifecycle_row(1, "MissionCreated", _stamp(1))) + "\n"})
    check(env, "a Mission with no work package is never all done", scan(env, repo), [_drift(1, [])], problems)

    for label, change, row in (
        ("work_packages that is a number", lambda document: document.update(work_packages=5), lane_row("WP01", None, "planned")),
        ("a work package entry that is a number", lambda document: document["work_packages"].update(WP01=5), lane_row("WP01", None, "planned")),
    ):
        repo = new_repo(env)
        mission_dir = mission(repo, SLUG, 1, {"WP01": "planned"})
        edit_snapshot(mission_dir, change)
        check(env, label, scan(env, repo), [_drift(1, [row])], problems)

    def outside_lane(document: dict[str, Any]) -> None:
        document["summary"]["planned"] = 99

    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, plain)
    edit_snapshot(mission_dir, outside_lane)
    check(env, "files that differ only outside lane give an empty comparison", scan(env, repo), [_drift(1, [])], problems)
    return problems


def _drift(number: int, comparison: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return expected_finding(KIND1, number, SNAPSHOT, "SNAPSHOT_DRIFT", severity="error", remedy="materialize_status", comparison=comparison)


# ---------------------------------------------------------------------------
# AC-DRIFT 4 and 5: kind 2, and the remedy on a merged Mission
# ---------------------------------------------------------------------------


def row4_problems(env: Env) -> list[str]:
    problems: list[str] = []
    cases: list[tuple[str, dict[str, Any], Sequence[Mapping[str, Any]]]] = [
        ("the log without a snapshot", {"snapshot": None}, [expected_finding(KIND2, 1, SNAPSHOT, None, severity="warning", remedy="materialize_status")]),
        ("a snapshot without the log", {"log": False}, [expected_finding(KIND2, 1, EVENT_LOG, None, severity="warning", remedy=None)]),
        ("neither file", {"snapshot": None, "log": False}, []),
        (
            "a snapshot without the log beside a current manifest",
            {"log": False, "lanes": manifest(SLUG, {LANE_ID: ["WP01"]})},
            [expected_finding(KIND2, 1, EVENT_LOG, None, severity="warning", remedy=None)],
        ),
        ("both files, the control", {}, []),
    ]
    for label, options, want in cases:
        repo = new_repo(env)
        mission(repo, SLUG, 1, **options)
        check(env, label, scan(env, repo), want, problems)
    return problems


def row5_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, meta, remedy in (
        ("merged_at in the own meta.json", {"merged_at": "2026-09-02T10:00:00+00:00"}, None),
        ("an unmerged twin", {}, "materialize_status"),
        ("a merge marker that is not an instant", {"merged_at": "yesterday"}, "materialize_status"),
        ("an empty merge marker", {"merged_at": "  "}, "materialize_status"),
        ("a merge marker that is not text", {"merged_at": 5}, "materialize_status"),
    ):
        repo = new_repo(env)
        mission_dir = mission(repo, SLUG, 1, EVERY_WP, meta=meta)
        edit_snapshot(mission_dir, _set_lane("WP01", "planned"))
        want = [expected_finding(KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT", severity="error", remedy=remedy, comparison=[lane_row("WP01", "planned", "approved")])]
        check(env, f"a disagreement, {label}", scan(env, repo), want, problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot="[]", meta={"merged_at": "2026-09-02T10:00:00+00:00"})
    check(
        env,
        "a corrupt snapshot on a merged Mission",
        scan(env, repo),
        [expected_finding(KIND1, 1, SNAPSHOT, "CORRUPT_JSON", severity="error", remedy=None)],
        problems,
    )
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot=None, meta={"merged_at": "2026-09-02T10:00:00+00:00"})
    check(
        env,
        "a missing snapshot keeps its remedy on a merged Mission",
        scan(env, repo),
        [expected_finding(KIND2, 1, SNAPSHOT, None, severity="warning", remedy="materialize_status")],
        problems,
    )
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 6 to 9: kind 3
# ---------------------------------------------------------------------------


def kind3_repo(
    env: Env,
    *,
    present: Sequence[str],
    remote_only: Sequence[str] = (),
    coordination: Any = None,
    plan: Mapping[str, str] | None = None,
    lanes: Mapping[str, Sequence[str]] | None = None,
    extra: Callable[[Path], None] | None = None,
) -> Path:
    """A real-git repository with one active Mission ``alpha`` (lane-a holds WP01) and the named local branches."""
    repo = new_repo(env)
    meta = {"coordination_branch": coordination} if coordination is not None else {}
    mission(repo, SLUG, 1, plan or {"WP01": "in_progress"}, meta=meta, lanes=manifest(SLUG, lanes or {LANE_ID: ["WP01"]}))
    if extra is not None:
        extra(repo)
    commit(repo, *present)
    for name in remote_only:
        _git(repo, "update-ref", f"refs/remotes/origin/{name}", "HEAD")
    return repo


@contextmanager
def resolver_unchanged() -> Iterator[None]:
    yield


def _kind3_finding(number: int = 1) -> dict[str, Any]:
    return expected_finding(KIND3, number, LANES, None, severity="warning", remedy=None)


def _kind3_cases(env: Env, label: str, cases: Sequence[tuple[str, dict[str, Any], bool]], problems: list[str]) -> None:
    for text, options, flagged in cases:
        coordinated = options.get("coordination") is not None
        repo = kind3_repo(env, **options)
        with own_dirs() if coordinated else resolver_unchanged():
            check(env, f"{label}: {text}", scan(env, repo), [_kind3_finding()] if flagged else [], problems)


def row6_problems(env: Env) -> list[str]:
    problems: list[str] = []
    _kind3_cases(
        env,
        "an expected lane branch",
        [
            ("no branch at all", {"present": []}, True),
            ("the lane branch without the Mission branch", {"present": [LANE_BRANCH]}, True),
            ("the Mission branch without the lane branch", {"present": [MISSION_BRANCH]}, True),
            ("both branches, the control", {"present": [LANE_BRANCH, MISSION_BRANCH]}, False),
            (
                "a planned-only lane beside an expected lane needs no branch of its own",
                {"present": [LANE_BRANCH, MISSION_BRANCH], "plan": {"WP01": "in_progress", "WP02": "planned"}, "lanes": {LANE_ID: ["WP01"], "lane-b": ["WP02"]}},
                False,
            ),
            (
                "an expected lane beside a planned-only lane still needs its branch",
                {"present": [MISSION_BRANCH], "plan": {"WP01": "in_progress", "WP02": "planned"}, "lanes": {LANE_ID: ["WP01"], "lane-b": ["WP02"]}},
                True,
            ),
        ],
        problems,
    )
    return problems


def row6_lanes_problems(env: Env) -> list[str]:
    """Only the five active status lanes make a lane expected; each other lane, beside a planned work package that keeps the Mission open, does not."""
    problems: list[str] = []
    for lane in ("claimed", "in_progress", "for_review", "in_review", "approved", "planned", "blocked", "canceled", "done"):
        repo = kind3_repo(env, present=[], plan={"WP01": lane, "WP02": "planned"}, lanes={LANE_ID: ["WP01"], "lane-b": ["WP02"]})
        active = lane in ("claimed", "in_progress", "for_review", "in_review", "approved")
        check(env, f"a lane holding a work package {lane}", scan(env, repo), [_kind3_finding()] if active else [], problems)
    return problems


def row7_problems(env: Env) -> list[str]:
    problems: list[str] = []
    _kind3_cases(
        env,
        "a coordination Mission expects its coordination branch only",
        [
            ("the coordination branch present, mission_branch absent", {"present": [LANE_BRANCH, COORD_BRANCH], "coordination": COORD_BRANCH}, False),
            ("the coordination branch lost, mission_branch present", {"present": [LANE_BRANCH, MISSION_BRANCH], "coordination": COORD_BRANCH}, True),
            ("an empty coordination_branch names none", {"present": [LANE_BRANCH, MISSION_BRANCH], "coordination": ""}, False),
            ("a coordination_branch that is not text names none", {"present": [LANE_BRANCH, MISSION_BRANCH], "coordination": ["kitty/x"]}, False),
            ("a Mission without a coordination branch expects mission_branch (present)", {"present": [LANE_BRANCH, MISSION_BRANCH]}, False),
            ("a Mission without a coordination branch expects mission_branch (absent)", {"present": [LANE_BRANCH, COORD_BRANCH]}, True),
        ],
        problems,
    )
    return problems


def row8_problems(env: Env) -> list[str]:
    problems: list[str] = []
    _kind3_cases(
        env,
        "local branches only",
        [
            ("both branches only as remote-tracking refs", {"present": [], "remote_only": [LANE_BRANCH, MISSION_BRANCH]}, True),
            ("the same branches local, the control", {"present": [LANE_BRANCH, MISSION_BRANCH]}, False),
        ],
        problems,
    )
    return problems


def row9_problems(env: Env) -> list[str]:
    """Four Missions beside the flagged one: planned-only lane, merge marker, all-terminal Mission, no manifest. Only the flagged one is reported."""
    problems: list[str] = []
    repo = new_repo(env)
    active = {"WP01": "in_progress"}
    mission(repo, "alpha", 1, active, lanes=manifest("alpha", {LANE_ID: ["WP01"]}))
    mission(repo, "beta", 2, {"WP01": "planned"}, lanes=manifest("beta", {LANE_ID: ["WP01"]}, number=2))
    mission(repo, "gamma", 3, active, meta={"merged_at": "2026-09-02T10:00:00+00:00"}, lanes=manifest("gamma", {LANE_ID: ["WP01"]}, number=3))
    mission(repo, "delta", 4, {"WP01": "done"}, lanes=b"this is not a manifest at all")
    mission(repo, "epsilon", 5, active)
    mission(repo, "zeta", 6, {"WP01": "in_progress", "WP02": "planned"}, lanes=manifest("zeta", {"lane-planning": ["WP01"], "lane-b": ["WP02"]}, number=6))
    commit(repo)
    check(env, "not expected", scan(env, repo), [_kind3_finding()], problems)
    return problems


def row9_reopened_problems(env: Env) -> list[str]:
    """A reopened Mission is not completed although every work package is done, so its broken manifest is a 500; never reopened, it is completed and unread."""
    problems: list[str] = []
    reopened = [helper.lifecycle_row(1, "MissionReopened", _stamp(500))]
    for label, extra, want in (("reopened", reopened, 500), ("never reopened", [], [])):
        repo = new_repo(env)
        mission_dir = mission(repo, SLUG, 1, ALL_DONE, lanes=b"not a manifest", extra_rows=extra)
        with own_dirs():
            check(env, f"a Mission with every work package done, {label}, with a broken manifest", scan(env, repo), want, problems)
        if is_mission_completed(mission_dir) is bool(extra):
            problems.append(f"{label}: the product's completion test agrees with the reopened state, so the plant is not real")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 10: lanes.json, three ways, completion first
# ---------------------------------------------------------------------------

MERGED = {"merged_at": "2026-09-02T10:00:00+00:00"}
BROKEN_MANIFESTS: dict[str, str | bytes] = {
    "not UTF-8": b'{"mission_slug": "\xff\xfe"}',
    "not JSON": "{not json",
    "not an object": "[1, 2]",
    "nested too deep": "[" * 100000,
    "neither key": json.dumps({"version": 1, "lanes": []}),
    "current-shaped, missing a required key": json.dumps({"mission_slug": SLUG, "version": 1, "lanes": []}),
    "current-shaped, lanes that are not objects": json.dumps({**manifest(SLUG, {}), "lanes": [1]}),
    "current-shaped, a collapse report that is not an object": json.dumps({**manifest(SLUG, {}), "collapse_report": 5}),
    "current-shaped, a slug that is not text": json.dumps({**manifest(SLUG, {}), "mission_slug": 5}),
    "current-shaped, a work package id that is not text": json.dumps(
        {**manifest(SLUG, {LANE_ID: []}), "lanes": [{**manifest(SLUG, {LANE_ID: []})["lanes"][0], "wp_ids": [5]}]}
    ),
}


def counting_fs(counter: list[str]) -> drift.FileSystem:
    """A seam that records the name of every file it reads."""

    def read_bytes(path: Path) -> bytes:
        counter.append(path.name)
        return path.read_bytes()

    return drift.FileSystem(exists=Path.exists, read_bytes=read_bytes)


def row10_problems(env: Env) -> list[str]:
    problems: list[str] = []
    legacy = new_repo(env)
    mission_dir = mission(legacy, SLUG, 1, EVERY_WP, lanes=legacy_manifest())
    edit_snapshot(mission_dir, _set_lane("WP01", "planned"))
    outcome = scan(env, legacy)
    check(env, "a legacy-shaped manifest keeps kind 1 and gives no kind 3", outcome, [_drift(1, [lane_row("WP01", "planned", "approved")])], problems)
    if outcome.legacy_manifests != (SLUG,):
        problems.append(f"the legacy-shaped manifest is on the list {outcome.legacy_manifests!r}, expected {(SLUG,)!r}")
    for label, content in BROKEN_MANIFESTS.items():
        repo = new_repo(env)
        mission(repo, SLUG, 1, {"WP01": "in_progress"}, lanes=content)
        with own_dirs():  # the product's own resolver also reads lanes.json, and a shape it cannot read ends it first: isolate the reader
            check(env, f"non-completed, {label}", scan(env, repo), 500, problems)
        for completion, meta, plan in (("a merge marker", MERGED, {"WP01": "in_progress"}), ("every work package done", {}, {"WP01": "done"})):
            seen: list[str] = []
            repo = new_repo(env)
            mission(repo, SLUG, 1, plan, meta=meta, lanes=content)
            with own_dirs():
                outcome = scan(env, repo, fs=counting_fs(seen))
            check(env, f"completed by {completion}, {label}", outcome, [], problems)
            if LANES in seen or outcome.legacy_manifests:
                problems.append(f"completed by {completion}, {label}: the manifest was read ({seen}) or listed ({outcome.legacy_manifests})")
    legacy_done = new_repo(env)
    mission(legacy_done, SLUG, 1, ALL_DONE, lanes=legacy_manifest())
    if scan(env, legacy_done).legacy_manifests:
        problems.append("a completed Mission with a legacy-shaped manifest is on the list")
    control = new_repo(env)
    mission(control, SLUG, 1, {"WP01": "planned"}, lanes=manifest(SLUG, {LANE_ID: ["WP01"]}))
    check(env, "a current manifest, the control", scan(env, control), [], problems)
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 11: meta.json is read fail-closed
# ---------------------------------------------------------------------------


def row11_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, content in (("a list", "[]"), ("invalid JSON", "{not json"), ("not UTF-8", b'{"a": "\xff"}')):
        repo = new_repo(env)
        mission_dir = mission(repo, SLUG, 1)
        (mission_dir / "meta.json").write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        with own_dirs():
            check(env, f"meta.json as {label}, resolver patched to the own directory", scan(env, repo), 500, problems)
        check(env, f"meta.json as {label}, the real resolver", scan(env, repo), 500, problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1)
    check(env, "the same Mission before the corruption, the control", scan(env, repo), [], problems)
    bare = env.fresh()
    if drift.read_meta(bare / "kitty-specs" / SLUG) is not None or drift.coordination_branch_of(None) is not None:
        problems.append("an absent meta.json is not 'no coordination branch'")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 12, 13 and 14: git failure, one listing, a remote that cannot be asked
# ---------------------------------------------------------------------------


def row12_problems(env: Env) -> list[str]:
    problems: list[str] = []
    expected = {"WP01": "in_progress"}
    no_git = new_repo(env, git=False)
    mission(no_git, SLUG, 1, expected, lanes=manifest(SLUG, {LANE_ID: ["WP01"]}))
    check(env, "no .git and an expected lane", scan(env, no_git), 500, problems)
    guest = env.fresh()
    _git(guest, "init", "-q")
    nested = guest / "inner"
    nested.mkdir()
    mission(nested, SLUG, 1, expected, lanes=manifest(SLUG, {LANE_ID: ["WP01"]}))
    try:
        drift.list_local_branches(nested)
    except drift.ScanUnreadable:
        pass
    else:
        problems.append("a directory inside another checkout was listed as that checkout")
    no_lane = new_repo(env, git=False)
    mission(no_lane, SLUG, 1, {"WP01": "planned"}, lanes=manifest(SLUG, {LANE_ID: ["WP01"]}))
    check(env, "no .git and no expected lane is not failed", scan(env, no_lane), [], problems)
    repo = kind3_repo(env, present=[LANE_BRANCH, MISSION_BRANCH])
    check(env, "the same Mission in a repository with the branches, the control", scan(env, repo), [], problems)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", str(env.root))
        check(env, "git cannot be started", scan(env, repo), 500, problems)

    def listing_fails(repo_root: Path) -> frozenset[str]:
        raise drift.ScanUnreadable("injected")

    check(env, "an injected listing failure", scan(env, repo, listing=listing_fails), 500, problems)
    return problems


def _many_expected(env: Env, count: int, *, active: bool) -> Path:
    repo = new_repo(env)
    plan = {"WP01": "in_progress" if active else "planned"}
    names = []
    for number in range(1, count + 1):
        slug = f"mission-{number:02d}"
        mission(repo, slug, number, plan, lanes=manifest(slug, {LANE_ID: ["WP01"]}, number=number))
        names += [code_lane_branch_name(slug, LANE_ID), f"kitty/mission-{slug}"]
    commit(repo, *names)
    return repo


def row13_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for active, expected_listings in ((True, 1), (False, 0)):
        repo = _many_expected(env, 4, active=active)
        listings: list[Path] = []

        def counted(repo_root: Path, seen: list[Path] = listings) -> frozenset[str]:
            seen.append(repo_root)
            return drift.list_local_branches(repo_root)

        memo = memo_module.ResolverMemo()
        with memo_module.counting_subprocesses() as total:
            outcome = scan(env, repo, memo=memo, listing=counted)
        resolver = sum(entry.subprocesses for entry in memo.entries())
        label = "many Missions with expected lanes" if active else "no Mission with an expected lane"
        check(env, label, outcome, [], problems)
        if len(listings) != expected_listings or total.started != resolver + expected_listings:
            problems.append(
                f"{label}: {len(listings)} listings, {total.started} processes ({resolver} of the resolver), expected {expected_listings} listing and nothing else"
            )
        with memo_module.counting_subprocesses() as own:
            scan(env, repo, memo=memo)
        if own.started != expected_listings:
            problems.append(f"{label}: with the resolver memoised the reader started {own.started} processes, expected exactly {expected_listings}")
    return problems


def coordination_repo(env: Env, remote: str | None) -> tuple[Path, str]:
    """A real-git repository whose Mission declares a coordination branch that exists nowhere locally, with ``remote`` as ``origin`` (or none)."""
    repo = new_repo(env)
    mission_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    name = f"gone-{mission_id[:8]}"
    mission(repo, name, 1, {"WP01": "planned"}, meta={"mission_id": mission_id, "coordination_branch": "kitty/coord-gone"})
    commit(repo)
    if remote is not None:
        _git(repo, "remote", "add", "origin", remote)
    return repo, name


def row14_problems(env: Env) -> list[str]:
    """A remote that cannot be asked, against the stock resolver of this tree.

    The spec (FRESH3-001, AC-DRIFT 14) expects a 500 here. The resolver of this tree does not give one: an unreachable remote makes it judge the
    declared branch present, no coordination worktree exists, and the aggregate keeps the primary checkout authoritative (the unmaterialised
    create window), so the Mission is read from its own directory and answers 200 with no fallback entry. A clean miss on a reachable remote is
    the deleted branch: the same 200, with the fallback entry. The row pins what the resolver does and tells the two apart.
    """
    problems: list[str] = []
    bare = env.fresh()
    _git(bare, "init", "--bare", "-q")
    plant, plant_name = coordination_repo(env, str(env.root / "no-such-remote"))
    _reset_remote_branch_lookup_cache()
    memo = memo_module.ResolverMemo()
    unreachable = scan(env, plant, memo=memo)
    check(env, "a remote that cannot be asked", unreachable, [], problems)
    entry = memo.lookup((plant.resolve(), plant_name))
    if unreachable.fallbacks or entry is None or entry.outcome != plant / "kitty-specs" / plant_name:
        problems.append(
            f"a remote that cannot be asked: fallbacks {unreachable.fallbacks!r}, resolver outcome {entry!r}, expected the own directory and no fallback"
        )
    control, name = coordination_repo(env, str(bare))
    _reset_remote_branch_lookup_cache()
    outcome = scan(env, control)
    check(env, "a reachable remote that lacks the branch (the fallback)", outcome, [], problems)
    if outcome.fallbacks != {name: "coordination_branch_deleted"}:
        problems.append(f"the fallback of a clean miss is {outcome.fallbacks!r}")
    _reset_remote_branch_lookup_cache()
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 15 and 26: the missionId lookup, 404, 400, per-Mission equality
# ---------------------------------------------------------------------------


RICH_FINDINGS = 7


def rich_repo(env: Env) -> Path:
    """Eight Missions, one for each way the reader answers: five kind-1 and kind-2 plants, a kind-3 plant, a clean one and kitty-ops content."""
    repo = new_repo(env)
    mission_dir = mission(repo, "m1-error", 1, EVERY_WP)
    edit_snapshot(mission_dir, _set_lane("WP01", "planned"))
    mission_dir = mission(repo, "m2-provenance", 2, EVERY_WP)
    edit_snapshot(mission_dir, _set_actor)
    mission_dir = mission(repo, "m3-terminal", 3, ALL_DONE)
    edit_snapshot(mission_dir, _set_lane("WP01", "approved"))
    mission(repo, "m4-corrupt", 4, snapshot="[]")
    mission(repo, "m5-no-snapshot", 5, snapshot=None)
    mission(repo, "m6-no-log", 6, log=False)
    mission(repo, "m7-branch", 7, {"WP01": "in_progress"}, lanes=manifest("m7-branch", {LANE_ID: ["WP01"]}, number=7))
    mission(repo, "m8-clean", 8)
    ops = repo / "kitty-ops"
    ops.mkdir()
    (ops / "placeholder.jsonl").write_text("{}\n", encoding="utf-8")
    commit(repo)
    return repo


def row15_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = new_repo(env)
    first = mission(repo, "a-mission", 1, EVERY_WP)
    edit_snapshot(first, _set_lane("WP01", "planned"))
    second = mission(repo, "b-mission", 2)
    ulid = helper.fixture_ulid(1)
    want = [
        expected_finding(KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT", severity="error", remedy="materialize_status", comparison=[lane_row("WP01", "planned", "approved")])
    ]
    check(env, "a missionId with every identity readable", scan(env, repo, mission_id=ulid), want, problems)
    check(env, "an unknown ULID, every identity readable", scan(env, repo, mission_id=helper.fixture_ulid(99)), 404, problems)
    (second / "meta.json").write_text("{not json", encoding="utf-8")
    check(env, "the missionId of A while meta.json of B is unreadable", scan(env, repo, mission_id=ulid), want, problems)
    check(env, "an unknown ULID while meta.json of B is unreadable", scan(env, repo, mission_id=helper.fixture_ulid(99)), 404, problems)
    check(env, "the project-wide scan while meta.json of B is unreadable", scan(env, repo), 500, problems)
    return problems


def row26_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = rich_repo(env)
    everything = scan(env, repo)
    if everything.status != 200 or len(everything.body["findings"]) != RICH_FINDINGS:
        return [f"the rich repository gives {everything.status} with {len(everything.body.get('findings', []))} findings, expected {RICH_FINDINGS}"]
    problems += [f"the project-wide scan: {error}" for error in env.errors("DriftReport", everything.body)]
    unknown = scan(env, repo, mission_id=helper.fixture_ulid(99))
    check(env, "an unknown ULID", unknown, 404, problems)
    if env.errors("DriftRefusal", unknown.body) or unknown.body.get("code") != "mission_not_found":
        problems.append(f"the 404 body is {unknown.body!r}")
    for text in ("not-a-ulid", "", "00000000000000000000000001X", "0000000000000000000000000I"):
        check(env, f"a missionId that is not a ULID ({text!r})", scan(env, repo, mission_id=text), 400, problems)
    for number in range(1, 9):
        ulid = helper.fixture_ulid(number)
        one = scan(env, repo, mission_id=ulid)
        want = [finding for finding in everything.body["findings"] if finding["missionId"] == ulid]
        check(env, f"the Mission {number} alone equals the project-wide report filtered", one, want, problems)
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 17 and 18: the read directory, the fallback, the strict sibling
# ---------------------------------------------------------------------------

MID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
MID8 = MID[:8]
COORD_NAME = f"beta-{MID8}"
V1_ERRORS = (CoordinationBranchDeleted, CoordAuthorityUnavailable, MissionMetadataUnavailable)


def coordination_mission(env: Env, *, primary_stale: bool, coord_stale: bool, meta: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    """A real coordination Mission: the primary copy, a coordination branch with a materialized worktree and a copy of the Mission there."""
    repo = new_repo(env)
    own_meta = {"mission_id": MID, "coordination_branch": f"kitty/coord-{COORD_NAME}", **(meta or {})}
    own = mission(repo, COORD_NAME, 1, EVERY_WP, meta=own_meta)
    if primary_stale:
        edit_snapshot(own, _set_lane("WP01", "planned"))
    commit(repo, f"kitty/coord-{COORD_NAME}")
    worktree = CoordinationWorkspace.worktree_path(repo, COORD_NAME, MID8)
    _git(repo, "worktree", "add", "-q", str(worktree), f"kitty/coord-{COORD_NAME}")
    coord = worktree / "kitty-specs" / coord_mission_dir_name(COORD_NAME, mid8=MID8)
    (coord / SNAPSHOT).write_text(replay_text(coord), encoding="utf-8")
    if coord_stale:
        edit_snapshot(coord, _set_lane("WP01", "planned"))
    return repo, coord


def _coord_drift() -> dict[str, Any]:
    return expected_finding(
        KIND1, 1, SNAPSHOT, "SNAPSHOT_DRIFT", severity="error", remedy="materialize_status", comparison=[lane_row("WP01", "planned", "approved")], mission_id=MID
    )


def _resolved(repo: Path, memo: memo_module.ResolverMemo) -> Path | Exception:
    entry = memo.lookup((repo.resolve(), COORD_NAME))
    return entry.outcome if entry is not None else RuntimeError("the resolver did not run")


def row17_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, primary_stale, coord_stale, want in (
        ("a consistent coordination copy beside a stale primary copy", True, False, []),
        ("a stale coordination copy beside a consistent primary copy", False, True, [_coord_drift()]),
        ("both copies consistent, the control", False, False, []),
    ):
        repo, coord = coordination_mission(env, primary_stale=primary_stale, coord_stale=coord_stale)
        memo = memo_module.ResolverMemo()
        outcome = scan(env, repo, memo=memo)
        check(env, label, outcome, want, problems)
        if _resolved(repo, memo) != coord:
            problems.append(f"{label}: the resolver answered {_resolved(repo, memo)!r}, not the coordination copy, so the plant is not real")
        if outcome.fallbacks:
            problems.append(f"{label}: unexpected fallbacks {outcome.fallbacks!r}")
    plain = new_repo(env)
    mission(plain, "plain", 2, EVERY_WP)
    check(env, "a Mission without coordination topology reads its own directory", scan(env, plain), [], problems)
    return problems + _fallback_and_failures(env)


def _gone_branch_repo(env: Env, *, branch_exists: bool = False) -> tuple[Path, Path]:
    """A real-git Mission that declares a coordination branch; the branch is gone (default) or exists with no worktree."""
    repo = new_repo(env)
    own = mission(repo, COORD_NAME, 1, EVERY_WP, meta={"mission_id": MID, "coordination_branch": "kitty/coord-gone"})
    edit_snapshot(own, _set_lane("WP01", "planned"))
    commit(repo, *(["kitty/coord-gone"] if branch_exists else []))
    return repo, own


def _fallback_and_failures(env: Env) -> list[str]:
    problems: list[str] = []
    repo, _ = _gone_branch_repo(env)
    outcome = scan(env, repo)
    own_finding = _coord_drift()
    check(env, "a deleted coordination branch is read from the own directory", outcome, [own_finding], problems)
    if outcome.fallbacks != {COORD_NAME: "coordination_branch_deleted"}:
        problems.append(f"the deleted branch names {outcome.fallbacks!r}")
    for label, branch_exists in (("a coordination branch with no worktree", True), ("a deleted coordination branch", False)):
        repo, _ = _gone_branch_repo(env, branch_exists=branch_exists)
        outcome = scan(env, repo)
        check(env, f"{label}: read from the own directory", outcome, [own_finding], problems)
        if bool(outcome.fallbacks) is branch_exists:
            problems.append(f"{label}: fallbacks {outcome.fallbacks!r}")
    repo, coord = coordination_mission(env, primary_stale=True, coord_stale=False)
    shutil.rmtree(coord)
    outcome = scan(env, repo)
    check(env, "a materialized coordination worktree without the Mission directory (coord-empty): the primary copy is read", outcome, [own_finding], problems)
    for label, error_of in _patched_errors().items():
        plain = new_repo(env)
        mission(plain, COORD_NAME, 1, EVERY_WP)
        with resolver_raises(error_of):
            check(env, f"{label} from a patched resolver", scan(env, plain), 500, problems)
    outside = new_repo(env)
    mission(outside, COORD_NAME, 1, EVERY_WP)
    elsewhere = env.fresh()
    mission(elsewhere, COORD_NAME, 1, EVERY_WP)
    with resolver_returns(lambda repo_root, name: elsewhere / "kitty-specs" / name):
        check(env, "a read directory outside the repository from a patched resolver", scan(env, outside), 500, problems)
    return problems


def _patched_errors() -> dict[str, Callable[[Path, str], Exception]]:
    def meta_unavailable(root: Path, name: str) -> Exception:
        place = root / "kitty-specs" / name
        error: Exception = MissionMetadataUnavailable(mission_slug=name, meta_path=place / "meta.json", primary_candidate=place, reason="unreadable")
        return error

    return {
        "MissionMetadataUnavailable": meta_unavailable,
        "InvalidMissionSlug": lambda root, name: InvalidMissionSlug(name),
        "WorktreeRegistryUnavailable": lambda root, name: WorktreeRegistryUnavailable(repo_root=root, detail="injected"),
        "CoordAuthorityUnavailable": lambda root, name: CoordAuthorityUnavailable(
            mission_slug=name, coord_candidate=root / "coord", primary_candidate=root / "kitty-specs" / name
        ),
    }


def _three_fixtures(env: Env) -> list[tuple[str, Path, Callable[[], Any]]]:
    """The three fixtures of the strict sibling's plant: two resolver exceptions and a read directory outside the root."""
    errors = _patched_errors()
    found: list[tuple[str, Path, Callable[[], Any]]] = []
    for label in ("CoordAuthorityUnavailable", "MissionMetadataUnavailable"):
        repo = new_repo(env)
        mission(repo, COORD_NAME, 1, EVERY_WP)
        found.append((label, repo, functools.partial(resolver_raises, errors[label])))
    repo = new_repo(env)
    mission(repo, COORD_NAME, 1, EVERY_WP)
    elsewhere = env.fresh()
    mission(elsewhere, COORD_NAME, 1, EVERY_WP)
    found.append(("a read directory outside the root", repo, functools.partial(resolver_returns, lambda repo_root, name: elsewhere / "kitty-specs" / name)))
    return found


def row18_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, repo, patched in _three_fixtures(env):
        with patched():
            entry = memo_module.memo_resolve(memo_module.ResolverMemo(), repo, COORD_NAME)
            try:
                drift.resolve_scan_dir(repo, COORD_NAME, entry)
            except Exception:
                strict_raised = True
            else:
                strict_raised = False
            v1_dir, v1_reason = helper.resolve_read_dir(repo, COORD_NAME)
        if not strict_raised:
            problems.append(f"{label}: the strict sibling did not raise")
        if v1_dir != repo / "kitty-specs" / COORD_NAME or v1_reason is None:
            problems.append(f"{label}: the v1 helper returned {v1_dir!r} with the reason {v1_reason!r}, so the plant is not real")
    gone, _ = _gone_branch_repo(env)
    entry = memo_module.memo_resolve(memo_module.ResolverMemo(), gone, COORD_NAME)
    own = gone / "kitty-specs" / COORD_NAME
    if not isinstance(entry.outcome, CoordinationBranchDeleted):
        problems.append(f"the deleted-branch fixture gives {entry.outcome!r}")
    strict_dir, strict_reason = drift.resolve_scan_dir(gone, COORD_NAME, entry)
    v1_dir, v1_reason = helper.resolve_read_dir(gone, COORD_NAME)
    if strict_dir != own or v1_dir != own or not strict_reason or not v1_reason:
        problems.append("CoordinationBranchDeleted: the strict sibling and the v1 helper do not both return the own directory with a reason")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 19 (fixture half): completion reads the own directory
# ---------------------------------------------------------------------------


def row19_problems(env: Env) -> list[str]:
    problems: list[str] = []
    malformed = "{not json"
    # (a) merged_at in the own copy only: completed, so its malformed lanes.json is not read. A patched resolver answers a copy inside the repository.
    repo = new_repo(env)
    own = mission(repo, COORD_NAME, 1, {"WP01": "in_progress"}, meta=MERGED, lanes=malformed)
    mission(repo / ".worktrees" / "coord", COORD_NAME, 1, {"WP01": "in_progress"})
    with resolver_returns(lambda repo_root, name: repo_root / ".worktrees" / "coord" / "kitty-specs" / name):
        check(env, "merged_at in the own copy only", scan(env, repo), [], problems)
    if is_mission_completed(own) is not True:
        problems.append("the own copy with a merge marker is not completed for the product")
    # (b) merged_at in the coordination copy only: not completed, so the malformed lanes.json is a 500. Real coordination.
    repo, coord = coordination_mission(env, primary_stale=False, coord_stale=False)
    own = repo / "kitty-specs" / COORD_NAME
    (own / LANES).write_text(malformed, encoding="utf-8")
    coord_meta = json.loads((coord / "meta.json").read_text(encoding="utf-8"))
    (coord / "meta.json").write_text(json.dumps({**coord_meta, **MERGED}), encoding="utf-8")
    check(env, "merged_at in the coordination copy only", scan(env, repo), 500, problems)
    # (control) no marker in either copy, a current manifest.
    control, _ = coordination_mission(env, primary_stale=False, coord_stale=False)
    (control / "kitty-specs" / COORD_NAME / LANES).write_text(json.dumps(manifest(COORD_NAME, {LANE_ID: []})), encoding="utf-8")
    check(env, "no marker in either copy, a current manifest (not completed, the manifest is read)", scan(env, control), [], problems)
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 20 and 21: the generation gate and undecodable files
# ---------------------------------------------------------------------------


def row20_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1, EVERY_WP, snapshot="{}")
    older = replay_text(mission_dir)
    (mission_dir / SNAPSHOT).write_text(older, encoding="utf-8")
    (mission_dir / SNAPSHOT).unlink()
    current = replay_text(mission_dir)
    (mission_dir / SNAPSHOT).write_text(older, encoding="utf-8")
    if '"schema_version"' in older or '"schema_version"' not in current:
        problems.append("the older-generation snapshot is not older than the current replay, so the plant is not real")
    check(env, "an older-generation snapshot in step with its replay", scan(env, repo), [], problems)
    control = new_repo(env)
    mission_dir = mission(control, SLUG, 1, EVERY_WP)
    edit_snapshot(mission_dir, _set_lane("WP01", "planned"))
    check(
        env,
        "the same Mission at the current generation with a field differing",
        scan(env, control),
        [_drift(1, [lane_row("WP01", "planned", "approved")])],
        problems,
    )
    return problems


def row21_problems(env: Env) -> list[str]:
    problems: list[str] = []
    bad = b'{"a": "\xff\xfe"}'
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot=bad)
    check(
        env,
        "status.json not valid UTF-8",
        scan(env, repo),
        [expected_finding(KIND1, 1, SNAPSHOT, "CORRUPT_JSON", severity="error", remedy="materialize_status")],
        problems,
    )
    repo = new_repo(env)
    mission(repo, SLUG, 1, {"WP01": "in_progress"}, lanes=bad)
    check(env, "lanes.json not valid UTF-8, not completed", scan(env, repo), 500, problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1, ALL_DONE, lanes=bad)
    check(env, "lanes.json not valid UTF-8, completed (not read)", scan(env, repo), [], problems)
    repo = new_repo(env)
    mission_dir = mission(repo, SLUG, 1)
    (mission_dir / "meta.json").write_bytes(bad)
    with own_dirs():
        check(env, "meta.json not valid UTF-8", scan(env, repo), 500, problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot="{}", files={EVENT_LOG: bad})
    check(env, "the event log not valid UTF-8", scan(env, repo), 500, problems)
    repo = new_repo(env)
    mission(repo, SLUG, 1, lanes=manifest(SLUG, {LANE_ID: ["WP01"]}))
    check(env, "the same Mission clean, the control", scan(env, repo), [], problems)
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 22: the fourth kind is absent
# ---------------------------------------------------------------------------


def _stale_derived(repo: Path) -> None:
    derived = repo / ".kittify" / "derived" / SLUG
    derived.mkdir(parents=True)
    (derived / SNAPSHOT).write_text('{"stale": true}', encoding="utf-8")
    (derived / "board-summary.json").write_text('{"stale": true}', encoding="utf-8")


def row22_problems(env: Env) -> list[str]:
    problems: list[str] = []
    kinds = yaml.safe_load((SCHEMA_DIR / "DriftKind.yaml").read_text(encoding="utf-8"))["enum"]
    if kinds != [KIND1, KIND2, KIND3]:
        problems.append(f"DriftKind is {kinds!r}, expected exactly the three kinds")
    for label, mismatching, want in (("a clean Mission", False, []), ("a mismatching Mission", True, [_drift(1, [lane_row("WP01", "planned", "approved")])])):
        repo = new_repo(env)
        mission_dir = mission(repo, SLUG, 1, EVERY_WP)
        if mismatching:
            edit_snapshot(mission_dir, _set_lane("WP01", "planned"))
        _stale_derived(repo)
        with recording_opens() as opened:
            outcome = scan(env, repo)
        check(env, f"a stale .kittify/derived/ beside {label}", outcome, want, problems)
        if any(".kittify" in path for path, _ in opened):
            problems.append(f"{label}: the scan opened a derived view")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 23: order and cap
# ---------------------------------------------------------------------------


def _many_findings(env: Env, count: int) -> Path:
    """``count`` Missions that each hold one kind-2 finding, created in shuffled order."""
    repo = new_repo(env, git=False)
    order = list(range(1, count + 1))
    random.Random(20261006).shuffle(order)
    for number in order:
        mission(repo, f"m{count + 1 - number:05d}", number, snapshot="{}", log=False)  # the name order is the reverse of the identity order
    return repo


def row23_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for count, truncated in ((1001, True), (1000, False)):
        with own_dirs():  # the cap does not depend on the resolver, which costs a few processes a Mission
            outcome = scan(env, _many_findings(env, count))
        got = [finding["missionId"] for finding in outcome.body.get("findings", [])]
        want = [helper.fixture_ulid(number) for number in range(1, 1001)]
        want = sorted(want, key=lambda text: text.encode("utf-8"))
        if outcome.status != 200 or got != want or outcome.body.get("truncated") is not truncated:
            problems.append(f"{count} findings: status {outcome.status}, {len(got)} returned, in order {got == want}, truncated {outcome.body.get('truncated')!r}")
        problems += [f"{count} findings: {error}" for error in env.errors("DriftReport", outcome.body)]
    clean = new_repo(env)
    mission(clean, SLUG, 1)
    outcome = scan(env, clean)
    if outcome.status != 200 or outcome.body != {"scannedAt": SCANNED_AT, "findings": [], "truncated": False}:
        problems.append(f"a clean repository answers {outcome.status} {outcome.body!r}, expected 200 with findings [] and truncated false")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 24: fixed summaries, the closed pair table, no leak
# ---------------------------------------------------------------------------

HOST_SLUG = "".join(["", chr(47), "home", chr(47), "someone", chr(47), "project"])
ADDRESS = "someone" + chr(64) + "example.invalid"
FORWARDED = "reducer output does not match persisted status.json"


def row24_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = new_repo(env)
    leaky = mission(repo, SLUG, 1, {"WP01": "in_progress", "WP02": "approved"}, lanes=manifest(HOST_SLUG, {LANE_ID: ["WP01"]}))
    rows = rows_for({"WP01": "in_progress", "WP02": "approved"})
    rows[0]["actor"] = ADDRESS
    (leaky / EVENT_LOG).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    edit_snapshot(leaky, _set_lane("WP02", "planned"))
    commit(repo)
    outcome = scan(env, repo)
    if outcome.status != 200 or len(outcome.body["findings"]) != 2:
        return [f"the leaky Mission gives {outcome.status} with {len(outcome.body.get('findings', []))} findings, expected 200 with two"]
    for finding in outcome.body["findings"]:
        if finding["summary"] != SENTENCES[(finding["kind"], finding["sourceCode"])]:
            problems.append(f"{finding['kind']}: the summary is {finding['summary']!r}, not the fixed sentence")
    text = json.dumps(outcome.body)
    if HOST_SLUG in text or ADDRESS in text or FORWARDED in text:
        problems.append("the payload carries a slug, an address or source prose")
    problems += [f"the leak scan: {finding}" for finding in helper.payload_leaks(outcome.body, env.tools)]
    return problems


def row24_table_problems(env: Env) -> list[str]:
    problems: list[str] = []
    if dict(drift.SUMMARIES) != SENTENCES:
        problems.append("the reader's pair table is not the six fixed sentences")
    description = yaml.safe_load((SCHEMA_DIR / "DriftFinding.yaml").read_text(encoding="utf-8"))["properties"]["summary"]["description"]
    flat = " ".join(str(description).split())
    problems += [f"the schema description lacks {sentence!r}" for sentence in SENTENCES.values() if sentence not in flat]
    for pair in ((KIND1, None), (KIND2, "SNAPSHOT_DRIFT"), (KIND3, "CORRUPT_JSON"), ("derived_view_stale", None)):
        try:
            drift.fixed_summary(*pair)
        except ValueError:
            continue
        problems.append(f"the pair {pair!r} outside the table was accepted")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 25: scannedAt and no-store
# ---------------------------------------------------------------------------


def no_store_problems(operation: Mapping[str, Any]) -> list[str]:
    header = operation.get("get", {}).get("responses", {}).get("200", {}).get("headers", {}).get("Cache-Control", {})
    return [] if header.get("schema", {}).get("const") == "no-store" else ["the 200 does not declare Cache-Control no-store"]


def row25_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = new_repo(env)
    mission(repo, SLUG, 1)
    memo = memo_module.ResolverMemo()
    clock = [T0, T0 + timedelta(seconds=90)]
    stamps = [drift.scan_drift(repo, memo, clock=FrozenClock(instant=instant)).body["scannedAt"] for instant in clock]
    if stamps != [SCANNED_AT, "2026-10-06T09:01:30Z"]:
        problems.append(f"scannedAt follows the injected clock as {stamps!r}")
    operation = yaml.safe_load((MODULE_DIR / "paths" / "drift.yaml").read_text(encoding="utf-8"))
    problems += no_store_problems(operation)
    plant = json.loads(json.dumps(operation))
    del plant["get"]["responses"]["200"]["headers"]
    if not no_store_problems(plant):
        problems.append("a bundle without the Cache-Control header was not refused")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 27: read-only
# ---------------------------------------------------------------------------


def _snapshot_of(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if ".git" not in path.relative_to(root).parts and path.is_file()
    }


@contextmanager
def writers_raise() -> Iterator[None]:
    """Every writing function of the reader's chain raises, and so does ``open`` for a writing mode."""
    real_open = io.open

    def forbidden(*arguments: Any, **options: Any) -> Any:
        raise UnexpectedWrite("the reader wrote")

    def guarded_open(file: Any, mode: str = "r", *arguments: Any, **options: Any) -> Any:
        if any(flag in mode for flag in WRITE_MODES):
            raise UnexpectedWrite(f"the reader opened {file} for writing")
        return real_open(file, mode, *arguments, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(reducer, "materialize", forbidden)
        for name in ("write_text", "write_bytes", "mkdir", "touch", "unlink", "rename"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(io, "open", guarded_open)
        patch.setattr(builtins, "open", guarded_open)
        yield


def row27_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = rich_repo(env)
    before = (_snapshot_of(repo), helper.tree_fingerprint(repo, "kitty-specs"), helper.tree_fingerprint(repo, "kitty-ops"))
    with writers_raise():
        outcome = scan(env, repo)
    after = (_snapshot_of(repo), helper.tree_fingerprint(repo, "kitty-specs"), helper.tree_fingerprint(repo, "kitty-ops"))
    if outcome.status != 200 or len(outcome.body["findings"]) != RICH_FINDINGS:
        problems.append(f"a scan with every writer raising gives {outcome.status} with {len(outcome.body.get('findings', []))} findings, expected {RICH_FINDINGS}")
    if before != after:
        problems.append("the scan changed a file below the repository")
    probe = new_repo(env)
    mission(probe, SLUG, 1)
    seen = _snapshot_of(probe)
    (probe / "kitty-specs" / SLUG / "added.txt").write_text("x", encoding="utf-8")
    if _snapshot_of(probe) == seen:
        problems.append("the probe did not see a write, so it proves nothing")
    try:
        with writers_raise():
            (probe / "kitty-specs" / SLUG / "again.txt").write_text("x", encoding="utf-8")
    except UnexpectedWrite:
        pass
    else:
        problems.append("a control that writes was not stopped by the stubs")
    if sorted(drift.FileSystem.__dataclass_fields__) != ["exists", "read_bytes"]:
        problems.append("the reader's seam has a call beyond the two read calls")
    return problems


# ---------------------------------------------------------------------------
# AC-DRIFT 28: no dead value
# ---------------------------------------------------------------------------


def _enum(name: str) -> list[str]:
    return [str(value) for value in yaml.safe_load((SCHEMA_DIR / f"{name}.yaml").read_text(encoding="utf-8"))["enum"]]


def row28_problems(env: Env) -> list[str]:
    problems: list[str] = []
    outcome = scan(env, rich_repo(env))
    if outcome.status != 200:
        return [f"the rich repository gives {outcome.status}"]
    findings = outcome.body["findings"]
    produced = {
        "kind": {finding["kind"] for finding in findings},
        "severity": {finding["severity"] for finding in findings},
        "authority": {finding["authority"] for finding in findings},
        "derivedSide": {finding["derivedSide"] for finding in findings},
        "remedy": {finding["remedy"] for finding in findings if finding["remedy"] is not None},
    }
    for field, enum in (
        ("kind", "DriftKind"),
        ("severity", "DriftSeverity"),
        ("authority", "DriftAuthority"),
        ("derivedSide", "DriftSide"),
        ("remedy", "DriftRemedy"),
    ):
        if produced[field] != set(_enum(enum)):
            problems.append(f"{enum} is {sorted(_enum(enum))!r} and the fixtures produce {sorted(produced[field])!r}")
    if "info" in _enum("DriftSeverity"):
        problems.append("DriftSeverity still carries info")
    codes = {finding["sourceCode"] for finding in findings}
    if codes != {"SNAPSHOT_DRIFT", "SNAPSHOT_DRIFT_PROVENANCE", "SNAPSHOT_DRIFT_TERMINAL", "CORRUPT_JSON", None}:
        problems.append(f"the fixtures produce the source codes {sorted(map(str, codes))!r}")
    for field in ("missionId", "artifactPath"):
        broken = json.loads(json.dumps(outcome.body))
        broken["findings"][0][field] = None
        if not env.errors("DriftReport", broken):
            problems.append(f"a finding with a null {field} passed validation")
    return problems


# ---------------------------------------------------------------------------
# A finding needs an identity the contract can carry (FR-009: missionId is never null)
# ---------------------------------------------------------------------------


def row29_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, override in (("no mission_id", {"mission_id": None}), ("a mission_id that is not a ULID", {"mission_id": "not-a-ulid"})):
        for flagged in (True, False):
            repo = new_repo(env)
            mission(repo, SLUG, 1, snapshot=None if flagged else "replay", meta=override)
            check(env, f"{label}, {'a finding to carry' if flagged else 'no finding'}", scan(env, repo), 500 if flagged else [], problems)
    # merged, so the lifecycle and the reducer are never asked: only the identity read can refuse a mission_number the product cannot read
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot=None, meta={"mission_number": "pending", **MERGED})
    check(env, "a mission_number the product cannot read, a finding to carry", scan(env, repo), 500, problems)
    return problems


# ---------------------------------------------------------------------------
# AC-CROSS 1, 4 and 5 (fixture-built halves): determinism and bounded reads
# ---------------------------------------------------------------------------


@contextmanager
def recording_opens() -> Iterator[list[tuple[str, str]]]:
    """Every file ``open`` is asked for while the context is open, with its mode."""
    opened: list[tuple[str, str]] = []
    real_open = io.open

    def spy(file: Any, mode: str = "r", *arguments: Any, **options: Any) -> Any:
        opened.append((str(file), mode))
        return real_open(file, mode, *arguments, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(io, "open", spy)
        patch.setattr(builtins, "open", spy)
        yield opened


ALLOWED_OPENS = frozenset({"meta.json", SNAPSHOT, EVENT_LOG, LANES})


def row_cross_problems(env: Env) -> list[str]:
    problems: list[str] = []
    repo = rich_repo(env)
    _stale_derived(repo)
    done = mission(repo, "n9-done", 9, ALL_DONE, lanes=b"not a manifest", meta=MERGED)
    (done / "tasks" / "WP01-extra.md").write_text("# body\n", encoding="utf-8")
    first, second = scan(env, repo), scan(env, repo)
    if json.dumps(first.body, sort_keys=True) != json.dumps(second.body, sort_keys=True):
        problems.append("two reads of one tree are not byte-equal")
    later = drift.scan_drift(repo, memo_module.ResolverMemo(), clock=FrozenClock(instant=T0 + timedelta(seconds=5)))
    if {key: value for key, value in later.body.items() if key != "scannedAt"} != {
        key: value for key, value in first.body.items() if key != "scannedAt"
    } or later.body["scannedAt"] == first.body["scannedAt"]:
        problems.append("a clock tick changed something other than scannedAt, or nothing")
    memo = memo_module.ResolverMemo()
    scan(env, repo, memo=memo)
    with recording_opens() as opened:
        scan(env, repo, memo=memo)
    in_missions = [(Path(path), mode) for path, mode in opened if "kitty-specs" in path]
    if not in_missions:
        problems.append("the counting opener saw no file, so it proves nothing")
    extra = sorted({path.name for path, _ in in_missions} - ALLOWED_OPENS)
    if extra:
        problems.append(f"the scan opened files outside the four it owns: {extra}")
    if any(set(mode) & set(WRITE_MODES) for _, mode in in_missions) or any(path.parent.name == "n9-done" and path.name == LANES for path, _ in in_missions):
        problems.append("the scan opened a file for writing, or the manifest of a completed Mission")
    return problems


def row_memo_problems(env: Env) -> list[str]:
    repo = rich_repo(env)
    memo = memo_module.ResolverMemo()
    scan(env, repo, memo=memo)
    runs = memo.runs
    scan(env, repo, memo=memo)
    scan(env, repo, memo=memo, mission_id=helper.fixture_ulid(1))
    return (
        []
        if runs == 8 and memo.runs == runs
        else [f"the resolver ran {runs} times for eight Missions and {memo.runs} times after two more scans, expected 8 and 8"]
    )


# ---------------------------------------------------------------------------
# The rows as tests
# ---------------------------------------------------------------------------

ROWS: dict[str, Callable[[Env], list[str]]] = {
    "row1": row1_problems,
    "row2": row2_problems,
    "row2-oserror": row2_oserror_problems,
    "row3": row3_problems,
    "row4": row4_problems,
    "row5": row5_problems,
    "row6": row6_problems,
    "row6-lanes": row6_lanes_problems,
    "row7": row7_problems,
    "row8": row8_problems,
    "row9": row9_problems,
    "row9-reopened": row9_reopened_problems,
    "row10": row10_problems,
    "row11": row11_problems,
    "row12": row12_problems,
    "row13": row13_problems,
    "row14": row14_problems,
    "row15": row15_problems,
    "row17": row17_problems,
    "row18": row18_problems,
    "row19": row19_problems,
    "row20": row20_problems,
    "row21": row21_problems,
    "row22": row22_problems,
    "row23": row23_problems,
    "row24": row24_problems,
    "row24-table": row24_table_problems,
    "row25": row25_problems,
    "row26": row26_problems,
    "row27": row27_problems,
    "row28": row28_problems,
    "row29": row29_problems,
    "cross": row_cross_problems,
    "memo": row_memo_problems,
}


@pytest.mark.parametrize("row", sorted(ROWS))
def test_the_drift_rows_hold(row: str, env: Env) -> None:
    assert ROWS[row](env) == []


# ---------------------------------------------------------------------------
# The mutations (proof kind M)
# ---------------------------------------------------------------------------


def _variant_confusion(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(drift, "classify_variant", lambda computed, persisted: drift.CODE_DRIFT)


def _no_generation_gate(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(read_dir: Path) -> str:
        copy = env.fresh() / read_dir.name
        copy.mkdir()
        for name in (EVENT_LOG, "meta.json"):
            if (read_dir / name).exists():
                (copy / name).write_bytes((read_dir / name).read_bytes())
        return replay_text(copy)

    patch.setattr(drift, "replay", defective)


def _read_lanes_before_completion(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.manifest_of
    patch.setattr(drift, "manifest_of", lambda ctx, own, completed: real(ctx, own, False))


def _expect_both_branches(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.expected_branch_names

    def defective(manifest: Any, coordination_branch: str | None, lane_ids: list[str]) -> list[str]:
        names = real(manifest, None, lane_ids)
        return [*names, coordination_branch] if names and coordination_branch else names

    patch.setattr(drift, "expected_branch_names", defective)


def _expect_mission_branch_only(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.expected_branch_names
    patch.setattr(drift, "expected_branch_names", lambda manifest, coordination_branch, lane_ids: real(manifest, None, lane_ids))


def _remote_ref_counts(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(repo_root: Path) -> frozenset[str]:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"], check=True, capture_output=True, text=True
        )
        names = {line.removeprefix("refs/heads/") for line in result.stdout.splitlines()}
        return frozenset({name.split("/", 3)[-1] if name.startswith("refs/remotes/") else name for name in names})

    patch.setattr(drift, "list_local_branches", defective)


def _per_branch_subprocess(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(ctx: drift.ScanContext, names: list[str]) -> bool:
        return any(
            subprocess.run(["git", "-C", str(ctx.repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], check=False, capture_output=True).returncode
            != 0
            for name in names
        )

    patch.setattr(drift, "any_branch_missing", defective)


def _list_without_expected_lane(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(drift, "listing_needed", lambda names: True)


def _fallback_on_any_exception(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.resolve_scan_dir

    def defective(repo_root: Path, name: str, entry: memo_module.MemoEntry) -> tuple[Path, str | None]:
        own = repo_root / "kitty-specs" / name
        outcome = entry.outcome
        if isinstance(outcome, V1_ERRORS):
            return own, type(outcome).__name__
        if isinstance(outcome, Path) and outcome.resolve() != own.resolve():
            try:
                outcome.resolve().relative_to(repo_root.resolve())
            except ValueError:
                return own, "outside"
        return real(repo_root, name, entry)

    patch.setattr(drift, "resolve_scan_dir", defective)


def _completion_from_read_directory(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.completion_of
    patch.setattr(drift, "completion_of", lambda ctx, read_dir, meta: real(ctx, read_dir, drift.read_meta(read_dir)))


def _forward_source_text(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.raw_finding

    def defective(kind: str, artifact_path: str, source_code: str | None, comparison: list[dict[str, Any]], remedy: str | None) -> dict[str, Any]:
        finding = real(kind, artifact_path, source_code, comparison, remedy)
        finding["summary"] = f"{FORWARDED} {HOST_SLUG}" if kind == KIND1 else f"{finding['summary']} {HOST_SLUG}"
        return finding

    patch.setattr(drift, "raw_finding", defective)


def _unsorted(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(drift, "sort_and_cap", lambda findings: (findings[: drift.CAP], len(findings) > drift.CAP))


def _cap_off_by_one(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(drift, "sort_and_cap", lambda findings: (sorted(findings, key=drift.sort_key)[: drift.CAP + 1], len(findings) > drift.CAP + 1))


def _call_materialize(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = drift.replay

    def defective(read_dir: Path) -> str:
        reducer.materialize(read_dir)
        return real(read_dir)

    patch.setattr(drift, "replay", defective)


MUTATIONS: dict[str, tuple[Callable[[pytest.MonkeyPatch, Env], None], tuple[str, ...]]] = {
    "variant-confusion": (_variant_confusion, ("row1",)),
    "no-generation-gate": (_no_generation_gate, ("row20",)),
    "read-lanes-before-completion": (_read_lanes_before_completion, ("row10",)),
    "expect-both-branches": (_expect_both_branches, ("row7",)),
    "expect-mission-branch-only": (_expect_mission_branch_only, ("row7",)),
    "remote-ref-counts": (_remote_ref_counts, ("row8",)),
    "per-branch-subprocess": (_per_branch_subprocess, ("row13",)),
    "list-without-expected-lane": (_list_without_expected_lane, ("row13",)),
    "fallback-on-any-exception": (_fallback_on_any_exception, ("row14", "row17", "row18")),
    "completion-from-read-directory": (_completion_from_read_directory, ("row19",)),
    "forward-source-text": (_forward_source_text, ("row24",)),
    "unsorted": (_unsorted, ("row23",)),
    "cap-off-by-one": (_cap_off_by_one, ("row23",)),
    "call-materialize": (_call_materialize, ("row27",)),
}


def _problems_or_raised(row: Callable[[Env], list[str]], env: Env) -> list[str]:
    try:
        return row(env)
    except Exception as error:  # a mutant may crash the scan: that is a red row, not an error of the test
        return [f"raised {type(error).__name__}: {error}"]


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_every_reader_mutation_turns_its_rows_red(name: str, env: Env) -> None:
    apply, rows = MUTATIONS[name]
    for row in rows:
        assert ROWS[row](env) == [], f"control: row {row} is not clean before the mutation"
    with pytest.MonkeyPatch.context() as patch:
        apply(patch, env)
        killed = any(_problems_or_raised(ROWS[row], env) for row in rows)
    assert killed, f"{NOT_KILLED}: {name}"


def test_the_mutation_table_names_only_known_rows_and_functions() -> None:
    assert all(row in ROWS for _, rows in MUTATIONS.values() for row in rows)
    assert {"classify_variant", "replay", "manifest_of", "expected_branch_names", "list_local_branches", "any_branch_missing", "listing_needed"} <= set(dir(drift))
    assert {"resolve_scan_dir", "completion_of", "raw_finding", "sort_and_cap"} <= set(dir(drift))


def _error_of(name: str, path: Path) -> Exception:
    if name == "MissionMetaReadError":
        return MissionMetaReadError(path, ValueError("injected"))
    return OSError("injected") if name == "OSError" else ValueError("injected")


@pytest.mark.parametrize("name", ["MissionMetaReadError", "OSError", "ValueError"])
def test_an_identity_read_that_fails_ends_a_finding_and_skips_a_lookup(name: str, env: Env) -> None:
    """The identity a finding carries and the identity a lookup matches are each one read: a failing read is a 500 for the first and a skip for the second."""
    repo = new_repo(env)
    mission(repo, SLUG, 1, snapshot=None, meta=MERGED)

    def fails(feature_dir: Path) -> Any:
        raise _error_of(name, feature_dir)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(drift, "resolve_mission_identity", fails)
        assert scan(env, repo).status == 500, FAULT_NOT_FIRED
        assert scan(env, repo, mission_id=helper.fixture_ulid(1)).status == 404, FAULT_NOT_FIRED
    assert scan(env, repo).status == 200


@pytest.mark.parametrize("name", ["ValueError", "OSError"])
def test_a_meta_read_that_fails_does_not_match_a_lookup(name: str, env: Env) -> None:
    repo = new_repo(env)
    mission(repo, SLUG, 1)

    def fails(feature_dir: Path, **options: Any) -> Any:
        raise _error_of(name, feature_dir)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(drift, "load_meta", fails)
        assert scan(env, repo, mission_id=helper.fixture_ulid(1)).status == 404, FAULT_NOT_FIRED
    assert scan(env, repo, mission_id=helper.fixture_ulid(1)).status == 200


@pytest.mark.parametrize("name", ["MissionMetaReadError", "OSError"])
def test_a_meta_read_that_fails_ends_the_scan(name: str, env: Env) -> None:
    repo = new_repo(env)
    mission(repo, SLUG, 1)

    def fails(feature_dir: Path) -> Any:
        raise _error_of(name, feature_dir)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(drift, "load_meta_fail_closed", fails)
        assert scan(env, repo).status == 500, FAULT_NOT_FIRED
    assert scan(env, repo).status == 200


# ---------------------------------------------------------------------------
# The strict sibling and the product's own refusals, side by side
# ---------------------------------------------------------------------------


def _write_manifest(directory: Path, label: str) -> None:
    directory.mkdir()
    content = BROKEN_MANIFESTS[label]
    (directory / LANES).write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


def test_the_product_refuses_the_manifests_the_reader_calls_a_500(tmp_path: Path) -> None:
    """The plants are real: ``read_lanes_json`` raises ``CorruptLanesError`` for these current-shaped manifests, so the 500 is the product's own verdict."""
    for number, label in enumerate(("current-shaped, missing a required key", "current-shaped, lanes that are not objects")):
        _write_manifest(tmp_path / f"refused{number}", label)
        with pytest.raises(CorruptLanesError):
            read_lanes_json(tmp_path / f"refused{number}")


def test_the_reader_is_stricter_than_the_product_only_where_the_product_would_crash_or_the_reader_would(tmp_path: Path) -> None:
    """A collapse report that is no object crashes the product (``AttributeError``); the reader maps it to its 500. Two shapes the product takes are refused."""
    _write_manifest(tmp_path / "crash", "current-shaped, a collapse report that is not an object")
    with pytest.raises(AttributeError):
        read_lanes_json(tmp_path / "crash")
    for number, label in enumerate(("current-shaped, a slug that is not text", "current-shaped, a work package id that is not text")):
        _write_manifest(tmp_path / f"accepted{number}", label)
        assert read_lanes_json(tmp_path / f"accepted{number}") is not None


FORBIDDEN_NAMES = frozenset({"resolve_read_dir", "load_source", "materialize", "write_text", "write_bytes", "InvocationWriter", "append_to_index"})


def forbidden_names(source: str) -> set[str]:
    tree = ast.parse(source)
    used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    return used & FORBIDDEN_NAMES


def test_the_reader_has_no_use_of_the_v1_helper_and_no_write_call() -> None:
    source = READER_FILE.read_text(encoding="utf-8")
    assert forbidden_names(source) == set()
    for plant in ("resolve_read_dir(root, name)", "reducer.materialize(path)", "path.write_text('x')", "InvocationWriter()"):
        assert forbidden_names(source + f"\n{plant}\n"), f"the plant was not seen: {plant}"


# ---------------------------------------------------------------------------
# T056: the one legacy-shape literal is pinned (AC-VERSION, bullet 5)
# ---------------------------------------------------------------------------

LEGACY_LITERAL = RETIRED + "_slug"
LEGACY_FUNCTION = "is_legacy_manifest"


def _names_in(tree: ast.AST) -> Iterator[tuple[int, str, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, "string", node.value
        elif isinstance(node, ast.Name):
            yield node.lineno, "name", node.id
        elif isinstance(node, ast.Attribute):
            yield node.lineno, "attribute", node.attr
        elif isinstance(node, ast.arg):
            yield node.lineno, "argument", node.arg
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.value.lineno, "keyword", node.arg
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield node.lineno, "definition", node.name
        elif isinstance(node, ast.alias):
            yield node.lineno, "import", node.asname or node.name


def retired_term_problems(source: str) -> list[str]:
    """Every way ``source`` misses the rule: exactly one occurrence of the retired term, the literal, inside the legacy-shape function."""
    tree = ast.parse(source)
    hits = [(line, kind, text) for line, kind, text in _names_in(tree) if RETIRED in text.casefold()]
    if not hits:
        return [f"count zero: the legacy-shape test in {LEGACY_FUNCTION} holds no {LEGACY_LITERAL!r}"]
    if len(hits) > 1:
        return [f"{len(hits)} occurrences at lines {sorted(line for line, _, _ in hits)}, expected exactly one"]
    line, kind, text = hits[0]
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.lineno <= line <= (node.end_lineno or node.lineno)]
    inside = min(functions, key=lambda node: (node.end_lineno or 0) - node.lineno).name if functions else None
    problems = []
    if kind != "string" or text != LEGACY_LITERAL:
        problems.append(f"line {line}: the occurrence is a {kind} {text!r}, expected the string {LEGACY_LITERAL!r}")
    if inside != LEGACY_FUNCTION:
        problems.append(f"line {line}: the occurrence is in {inside!r}, expected {LEGACY_FUNCTION}")
    return problems


def test_the_reader_holds_the_retired_term_once_in_the_legacy_shape_function() -> None:
    source = READER_FILE.read_text(encoding="utf-8")
    assert retired_term_problems(source) == []
    plants = {
        "a second constant": source + f'\nSECOND = "{LEGACY_LITERAL}"\n',
        "a docstring that mentions it": source + f'\n\ndef other() -> None:\n    """Mentions {LEGACY_LITERAL}."""\n',
        "a prefixed identifier": source + f"\n{RETIRED}_flag = 1\n",
        "the literal moved out of the function": source.replace(f'"{LEGACY_LITERAL}" in data', "True") + f'\nELSEWHERE = "{LEGACY_LITERAL}"\n',
    }
    for label, text in plants.items():
        assert retired_term_problems(text), f"the plant was not refused: {label}"
    removed = source.replace(f'"{LEGACY_LITERAL}"', '"other_key"')
    problems = retired_term_problems(removed)
    assert problems and problems[0].startswith("count zero"), problems
    assert retired_term_problems(source) != problems


# ---------------------------------------------------------------------------
# The reader against the contract's own examples
# ---------------------------------------------------------------------------


EXAMPLE_FILES = {"mission_not_found": "DriftRefusal.mission-not-found.yaml", "drift_scan_unreadable": "DriftRefusal.scan-unreadable.yaml"}


def test_the_refusals_are_the_contract_examples(env: Env) -> None:
    for code in EXAMPLE_FILES:
        outcome = drift.refusal(code)
        example = yaml.safe_load((MODULE_DIR / "examples" / EXAMPLE_FILES[code]).read_text(encoding="utf-8"))
        assert outcome.body == example
        assert env.errors("DriftRefusal", outcome.body) == []
    assert drift.invalid_identity().status == 400


# ---------------------------------------------------------------------------
# The prose about a remote that cannot be asked (operator ruling at WP07, 2026-10-06)
# ---------------------------------------------------------------------------


UNREACHABLE_SENTENCE = (
    "An unreachable remote leaves the Mission's own directory as the read directory (a 200 with no fallback entry); "
    "a reachable remote that lacks the declared branch gives the coordination_branch_deleted fallback; "
    "any other resolver error is a 500 drift_scan_unreadable."
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _prose_of_the_unreachable_remote() -> dict[str, str]:
    report = yaml.safe_load((SCHEMA_DIR / "DriftReport.yaml").read_text(encoding="utf-8"))["description"]
    operation = yaml.safe_load((MODULE_DIR / "paths" / "drift.yaml").read_text(encoding="utf-8"))["get"]["description"]
    return {"DriftReport": _flat(report), "drift.yaml": _flat(operation)}


def test_the_contract_prose_states_what_an_unreachable_remote_does() -> None:
    for place, prose in _prose_of_the_unreachable_remote().items():
        assert "ends the scan" not in prose, f"{place} still says an unreachable remote ends the scan"
        assert UNREACHABLE_SENTENCE in prose, f"{place} does not state the ruled behaviour of an unreachable remote"
    changelog = _flat((MODULE_DIR / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert "ends the scan in" not in changelog
