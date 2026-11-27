"""The rollback undoes the run's own auto-rebase lane move, and nothing else (FR-009, NFR-002, #7767).

A consolidate run auto-rebases a stale lane (a ``--no-ff`` merge of the Mission branch into the
lane worktree) and then fails. Before FR-009 the single rollback authority treated every lane as
report-only, so the merge stayed on the lane, in its checkout and in its work-tip ref. The run
records that move in ``ConsolidationState.lane_rebase_moves`` as ``[before, after]``; the rollback
now restores ``after -> before`` under compare-and-swap, resyncs the lane checkout, resets the
lane work-tip ref and deletes the durable auto-rebase record. A lane that moved again since the
merge is reported ``LANE_MOVED_SINCE_AUTO_REBASE`` and never reset.

Two layers, real git throughout:

* the observed harm on a real Mission (T018): two approved lanes edit one file in disjoint
  regions, both lane worktrees are allocated by the real ``allocate_lane_worktree`` so the
  auto-rebase really runs, the real executor runs in-process, and the only patches are a
  one-shot reconciliation FAIL (or a one-shot lane merge failure) that delegate afterwards;
* the authority's lane rules on a small repository (T021, T022).

The Mission builder is local: ``tests/terminus/post_approval_support.py`` is frozen, so its
``build_post_approval_lanes_mission`` is copied here with one change, a shared file seeded on the
target before the Mission branch and the lanes are cut.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
import typer

from specify_cli.consolidation import executor, rollback
from specify_cli.consolidation.reconciliation import Divergence, MergeOutcomeVerifier, VerifyResult
from specify_cli.consolidation.rollback import (
    BranchOutcome,
    BranchOutcomeKind,
    NotRestoredCause,
    RollbackReport,
    begin_attempt,
    capture_pre_mutation_snapshot,
    rebaseline_after_full_restore,
    record_post_mutation_tips,
    rollback_to_snapshot,
)
from specify_cli.consolidation.state import ConsolidationState, load_state
from specify_cli.git.ref_advance import write_bookkeeping_ref
from specify_cli.lanes import auto_rebase_record
from specify_cli.lanes import consolidation as lane_consolidation
from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.lane_tip import tip_ref
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status.models import ReviewResult
from tests.terminus.canceled_dependency_support import ACTOR, REVIEWER
from tests.terminus.conftest import CoordMission, git_rev, pin_planning_commit, run_terminus
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

Shape = Literal["clean", "auto_resolved"]

_TARGET = "develop"
_SHARED = "src/pkg/shared.py"
_PYPROJECT = "pyproject.toml"
_STATUS_EVENTS = "status.events.jsonl"
_AUTO_REBASE_PREFIX = "refs/spec-kitty/auto-rebase/"
_LANE_OF_WP = {"WP01": "lane-a", "WP02": "lane-b"}
_SHARED_SEED = "".join(f"LINE_{n:02d} = {n}\n" for n in range(1, 21))
_WP_EDITS = {"WP01": (2, "charlie"), "WP02": (18, "delta")}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def _write(root: Path, rel_path: str, text: str) -> None:
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _pyproject(deps: list[str]) -> str:
    return '[project]\nname = "demo"\ndependencies = [\n' + "".join(f'  "{dep}",\n' for dep in deps) + "]\n"


def _edited_shared(line: int, wp: str) -> str:
    lines = _SHARED_SEED.splitlines(keepends=True)
    lines[line - 1] = f"LINE_{line:02d} = '{wp}'\n"
    return "".join(lines)


def _commit_in(worktree: Path, files: dict[str, str], message: str) -> str:
    for rel_path, text in files.items():
        _write(worktree, rel_path, text)
    _git(worktree, "add", *files)
    _git(worktree, "commit", "-qm", message)
    return git_rev(worktree, "HEAD")


def _approve(mission: CoordMission, wp: str) -> None:
    reference = f"review-{wp}"
    transition(mission, wp, "for_review", actor=ACTOR, subtasks_complete=True)
    transition(mission, wp, "in_review", actor=REVIEWER)
    verdict = ReviewResult(reviewer=REVIEWER, verdict="approved", reference=reference)
    transition(mission, wp, "approved", actor=REVIEWER, review_ref=reference, review_result=verdict)


def _manifest(slug: str, mission_id: str, mission_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch=_TARGET,
        lanes=[
            ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=("src/pkg",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
            for wp, lane_id in _LANE_OF_WP.items()
        ],
        computed_at="2026-11-25T00:00:00+00:00",
        computed_from="rollback-own-lane-moves-fixture",
    )


def _wp_file(wp: str) -> str:
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - src/**\n  - pyproject.toml\n---\n# {wp}\n"


def _init_repo(repo: Path, shape: Shape) -> None:
    repo.mkdir(parents=True)
    _git(repo.parent, "init", "-qb", _TARGET, str(repo))
    for key, value in (("user.email", "terminus@example.invalid"), ("user.name", "terminus"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    seeds = {"README.md": "init\n", _SHARED: _SHARED_SEED}
    if shape == "auto_resolved":
        seeds[_PYPROJECT] = _pyproject(["alpha", "bravo"])
    for rel_path, text in seeds.items():
        _write(repo, rel_path, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init: seed the shared file")


def _write_meta(mission: CoordMission) -> None:
    meta = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": _TARGET,
        "topology": "lanes",
        "purpose_tldr": "rollback own lane moves fixture",
        "purpose_context": "rollback own lane moves fixture",
    }
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _approval_stamp(mission: CoordMission, wp: str) -> str | None:
    stamp: str | None = None
    for line in (mission.feature_dir / _STATUS_EVENTS).read_text(encoding="utf-8").splitlines():
        event = json.loads(line) if line.strip() else {}
        if event.get("wp_id") == wp and event.get("to_lane") == "approved":
            stamp = (event.get("policy_metadata") or {}).get("lane_head")
    return stamp


def _wp_files(shape: Shape, wp: str) -> dict[str, str]:
    line, dep = _WP_EDITS[wp]
    files = {_SHARED: _edited_shared(line, wp)}
    if shape == "auto_resolved":
        files[_PYPROJECT] = _pyproject(["alpha", "bravo", dep])
    return files


def _assert_builder_preconditions(mission: CoordMission, trees: dict[str, Path], shape: Shape) -> None:
    lane_a, lane_b = mission.lane_branches["WP01"], mission.lane_branches["WP02"]
    assert all(tree.is_dir() for tree in trees.values()), "both lane worktrees must exist, or no auto-rebase runs"
    probe = subprocess.run(["git", "-C", str(mission.repo), "merge-tree", "--write-tree", lane_a, lane_b], capture_output=True, text=True, check=False)
    assert (probe.returncode == 0) is (shape == "clean"), f"the {shape} shape: merge-tree exit {probe.returncode}"
    base = git_rev(mission.repo, _TARGET)
    for wp, branch in mission.lane_branches.items():
        assert _SHARED in _git(mission.repo, "diff", "--name-only", base, branch).splitlines(), f"{wp} changed the shared file"
        assert _approval_stamp(mission, wp) == git_rev(mission.repo, branch), f"{wp}'s newest approval stamp is its lane tip"


def _build_shared_file_mission(tmp_path: Path, *, shape: Shape = "clean", mid8: str = "01M7WW03") -> CoordMission:
    """LANES topology: WP01 (lane-a) and WP02 (lane-b) edit one seeded file in disjoint regions, both approved."""
    mission_id = (mid8 + "0" * 26)[:26]
    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission_branch = mission_branch_name(slug, mission_id=mission_id)
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    mission = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=mission_branch,
        target_branch=_TARGET,
    )
    _init_repo(repo, shape)
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    write_lanes_json(mission.feature_dir, _manifest(slug, mission_id, mission_branch))
    pin_planning_commit(mission.repo, mission.feature_dir)
    for wp in _LANE_OF_WP:
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS).write_text("", encoding="utf-8")
    _git(repo, "add", ".gitignore", f"kitty-specs/{slug}")
    _git(repo, "commit", "-qm", f"chore({slug}): bootstrap the shared-file lanes mission")
    _git(repo, "branch", mission_branch)
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None

    trees: dict[str, Path] = {}
    for wp in _LANE_OF_WP:
        tree, branch = allocate_lane_worktree(repo, slug, wp, manifest)
        trees[wp] = tree
        for lane in ("planned", "claimed", "in_progress"):
            transition(mission, wp, lane, actor=ACTOR)
        _commit_in(tree, _wp_files(shape, wp), f"feat({slug}): {wp} work")
        _approve(mission, wp)
        mission.lane_branches[wp] = branch
    _assert_builder_preconditions(mission, trees, shape)
    return mission


# --------------------------------------------------------------------------- driving the run


@dataclass
class _Run:
    """What the rollback door saw: the recorded moves just before it ran, and its report."""

    moves_at_rollback: dict[str, list[str]]
    reports: list[RollbackReport]
    gate_calls: list[int]


def _spy_rollback(monkeypatch: pytest.MonkeyPatch, on_gate: Callable[[], None] | None = None, *, fail_gate: bool = True) -> _Run:
    seen = _Run({}, [], [])
    real_rollback = rollback.rollback_to_snapshot

    def spying(repo_root: Path, state: ConsolidationState, *, target_branch: str) -> RollbackReport:
        seen.moves_at_rollback.update({branch: list(move) for branch, move in state.lane_rebase_moves.items()})
        report = real_rollback(repo_root, state, target_branch=target_branch)
        seen.reports.append(report)
        return report

    monkeypatch.setattr(rollback, "rollback_to_snapshot", spying)
    if not fail_gate:
        return seen
    failed = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))
    real_verify = MergeOutcomeVerifier.verify

    def verify_once(self: MergeOutcomeVerifier, target_ref: str, claim: Any) -> VerifyResult:
        seen.gate_calls.append(len(seen.gate_calls) + 1)
        if len(seen.gate_calls) == 1:
            if on_gate is not None:
                on_gate()
            return failed
        return real_verify(self, target_ref, claim)

    monkeypatch.setattr(MergeOutcomeVerifier, "verify", verify_once)
    return seen


def _consolidate_in_process(mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> int:
    """Drive the real executor in-process, exactly as ``spec-kitty consolidate`` does; return its exit code."""
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    with pytest.raises(typer.Exit) as exited:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)
    return int(exited.value.exit_code or 0)


def _ref(mission: CoordMission, ref: str) -> str:
    return subprocess.run(["git", "-C", str(mission.repo), "rev-parse", "--verify", "-q", ref], capture_output=True, text=True, check=False).stdout.strip()


def _auto_rebase_refs(repo: Path, lane_branch: str) -> list[str]:
    return _git(repo, "for-each-ref", "--format=%(refname)", f"{_AUTO_REBASE_PREFIX}{lane_branch}/").splitlines()


def _lane_b_worktree(mission: CoordMission) -> Path:
    for block in _git(mission.repo, "worktree", "list", "--porcelain").split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        if fields.get("branch") == f"refs/heads/{mission.lane_branches['WP02']}":
            return Path(fields["worktree"])
    raise AssertionError("lane-b has no worktree")


def _pre_run(mission: CoordMission) -> dict[str, str]:
    lane_b = mission.lane_branches["WP02"]
    return {
        "lane_b": git_rev(mission.repo, lane_b),
        "lane_b_tip_ref": _ref(mission, tip_ref(lane_b)),
        "mission": git_rev(mission.repo, mission.coord_branch),
        "target": git_rev(mission.repo, _TARGET),
    }


def _assert_the_run_auto_rebased_lane_b(mission: CoordMission, seen: _Run, pre: dict[str, str]) -> str:
    """Fixture precondition: this run's own auto-rebase moved lane-b, and the record says so."""
    lane_b = mission.lane_branches["WP02"]
    move = seen.moves_at_rollback.get(lane_b)
    assert move is not None and move[0] == pre["lane_b"], f"the run must record lane-b's own auto-rebase move, saw {seen.moves_at_rollback}"
    parents = _git(mission.repo, "rev-list", "--parents", "-n", "1", move[1]).split()
    assert len(parents) == 3, "the recorded move ends at a two-parent merge"
    return move[1]


def _assert_lane_b_restored(mission: CoordMission, pre: dict[str, str], merge: str) -> None:
    lane_b = mission.lane_branches["WP02"]
    assert git_rev(mission.repo, lane_b) == pre["lane_b"], f"lane-b still carries the run's own merge {merge[:12]}"
    assert _ref(mission, tip_ref(lane_b)) == pre["lane_b"], "the lane work-tip ref is reset to the restored tip"
    assert _auto_rebase_refs(mission.repo, lane_b) == [], "the durable auto-rebase record of the undone merge is deleted"


def _assert_checkout_matches(worktree: Path, tip: str) -> None:
    assert _git(worktree, "rev-parse", "HEAD") == tip
    staged = subprocess.run(["git", "-C", str(worktree), "diff", "--cached", "--quiet", tip], check=False)
    unstaged = subprocess.run(["git", "-C", str(worktree), "diff", "--quiet"], check=False)
    assert staged.returncode == 0, "no staged reversal of the merge is left in the lane checkout's index"
    assert unstaged.returncode == 0, "the lane checkout's working tree equals the restored tip"


# --------------------------------------------------------------------------- T018: the observed harm


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_a_failed_run_restores_the_auto_rebased_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: Shape) -> None:
    mission = _build_shared_file_mission(tmp_path, shape=shape)
    pre = _pre_run(mission)
    seen = _spy_rollback(monkeypatch)

    assert _consolidate_in_process(mission, monkeypatch) != 0
    assert seen.gate_calls == [1], "the run must reach the reconciliation gate"
    merge = _assert_the_run_auto_rebased_lane_b(mission, seen, pre)

    _assert_lane_b_restored(mission, pre, merge)
    outcome = {o.branch: o for o in seen.reports[-1].outcomes}[mission.lane_branches["WP02"]]
    assert outcome.kind is BranchOutcomeKind.RESTORED
    assert f"restored   {mission.lane_branches['WP02']}" in seen.reports[-1].render()
    assert git_rev(mission.repo, mission.coord_branch) == pre["mission"]
    assert git_rev(mission.repo, _TARGET) == pre["target"]


def test_the_next_run_is_not_harmed_by_the_run_s_own_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLEAN shape only: the second, real run lands, and names no commit of the first run's recorded move."""
    mission = _build_shared_file_mission(tmp_path, shape="clean")
    pre = _pre_run(mission)
    seen = _spy_rollback(monkeypatch)
    assert _consolidate_in_process(mission, monkeypatch) != 0
    merge = _assert_the_run_auto_rebased_lane_b(mission, seen, pre)
    monkeypatch.undo()

    second = run_terminus(mission, ["consolidate", "--mission", mission.slug], env={"COLUMNS": "1000"})
    output = second.stdout + second.stderr

    assert second.returncode == 0, output
    for name in (merge, merge[:12], merge[:7]):
        assert name not in output, f"the second run names the first run's own merge {name}"


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_the_lane_checkout_is_resynced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: Shape) -> None:
    mission = _build_shared_file_mission(tmp_path, shape=shape)
    pre = _pre_run(mission)
    seen = _spy_rollback(monkeypatch)

    assert _consolidate_in_process(mission, monkeypatch) != 0
    _assert_the_run_auto_rebased_lane_b(mission, seen, pre)

    _assert_checkout_matches(_lane_b_worktree(mission), pre["lane_b"])


def test_a_lane_whose_consolidation_failed_after_the_auto_rebase_is_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The auto-rebase of lane-b succeeds, then lane-b's consolidation into the Mission branch fails (WP07 records the move)."""
    mission = _build_shared_file_mission(tmp_path, shape="clean")
    pre = _pre_run(mission)
    seen = _spy_rollback(monkeypatch, fail_gate=False)
    lane_b = mission.lane_branches["WP02"]
    real_merge = lane_consolidation._merge_branch_into
    failed_for: list[str] = []

    def merge_fails_once_for_lane_b(repo_root: Path, source_branch: str, target_branch: str, **kwargs: Any) -> bool:
        if source_branch == lane_b and not failed_for:
            failed_for.append(source_branch)
            raise RuntimeError("injected: lane-b's consolidation into the Mission branch failed")
        return bool(real_merge(repo_root, source_branch, target_branch, **kwargs))

    monkeypatch.setattr(lane_consolidation, "_merge_branch_into", merge_fails_once_for_lane_b)

    assert _consolidate_in_process(mission, monkeypatch) != 0
    assert failed_for == [lane_b], "the injected failure must hit lane-b's consolidation"
    merge = _assert_the_run_auto_rebased_lane_b(mission, seen, pre)

    _assert_lane_b_restored(mission, pre, merge)
    _assert_checkout_matches(_lane_b_worktree(mission), pre["lane_b"])


def test_abort_after_a_moved_lane_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An operator commit lands on lane-b after the run's merge: the rollback keeps it, and ``--abort`` still finishes."""
    mission = _build_shared_file_mission(tmp_path, shape="clean")
    pre = _pre_run(mission)
    late: list[str] = []

    def operator_commits_on_lane_b() -> None:
        late.append(_commit_in(_lane_b_worktree(mission), {"src/pkg/operator.py": "OPERATOR = True\n"}, "operator: work on lane-b"))

    seen = _spy_rollback(monkeypatch, operator_commits_on_lane_b)
    assert _consolidate_in_process(mission, monkeypatch) != 0
    merge = _assert_the_run_auto_rebased_lane_b(mission, seen, pre)
    lane_b = mission.lane_branches["WP02"]
    outcome = {o.branch: o for o in seen.reports[-1].outcomes}[lane_b]
    assert outcome.kind is BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE
    assert git_rev(mission.repo, lane_b) == late[0], "the operator's commit is never reset"
    saved = load_state(mission.repo, mission.mission_id)
    assert saved is not None and saved.lane_rebase_moves.get(lane_b) == [pre["lane_b"], merge], "the moved lane keeps its record"
    monkeypatch.undo()

    aborted = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--abort"], env={"COLUMNS": "1000"})
    output = aborted.stdout + aborted.stderr

    assert aborted.returncode == 0, output
    assert lane_b in output and merge[:7] in output and late[0][:7] in output
    assert git_rev(mission.repo, lane_b) == late[0]
    assert _auto_rebase_refs(mission.repo, lane_b) == [f"{_AUTO_REBASE_PREFIX}{lane_b}/{merge}"], "the durable record still names the tool merge"


# --------------------------------------------------------------------------- T021 / T022: the authority's lane rules

_SLUG = "m-01ABCDEF"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


@dataclass
class _Env:
    repo: Path
    state: ConsolidationState
    lane: str
    worktree: Path
    before: str
    after: str


def _commit_here(cwd: Path, name: str) -> str:
    _write(cwd, f"{name}.txt", f"{name}\n")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-qm", name)
    return _git(cwd, "rev-parse", "HEAD")


def _env(tmp_path: Path) -> _Env:
    """A run that advanced the target and the Mission branch and auto-rebased its one lane, as recorded."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(tmp_path, "init", "-qb", _TARGET, str(repo))
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / ".gitignore").write_text(".kittify/runtime/\nlanes/\n")
    _commit_here(repo, "base")
    lane_manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_MISSION_BRANCH,
        target_branch=_TARGET,
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )
    lane = lane_created_branch(lane_manifest, "lane-a")
    _git(repo, "branch", _MISSION_BRANCH)
    worktree = repo / "lanes" / "lane-a"
    _git(repo, "worktree", "add", "-q", "-b", lane, str(worktree), _MISSION_BRANCH)
    _commit_here(worktree, "lane-work")
    state = ConsolidationState(mission_id="M1", mission_slug=_SLUG, target_branch=_TARGET, wp_order=["WP01"])
    capture_pre_mutation_snapshot(repo, state, lane_manifest, coord_ref=None)
    begin_attempt(repo, state)
    before = _git(repo, "rev-parse", f"refs/heads/{lane}")
    mission_wt = tmp_path / "mission-wt"
    _git(repo, "worktree", "add", "-q", str(mission_wt), _MISSION_BRANCH)
    _commit_here(mission_wt, "mission-advance")
    _git(repo, "worktree", "remove", "--force", str(mission_wt))
    _commit_here(repo, "target-advance")
    record_post_mutation_tips(repo, state)
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION_BRANCH)  # the merge lanes.auto_rebase makes
    after = _git(worktree, "rev-parse", "HEAD")
    assert auto_rebase_record.record(repo, lane, after)
    state.lane_rebase_moves[lane] = [before, after]
    return _Env(repo, state, lane, worktree, before, after)


def _lane_outcome(report: RollbackReport, lane: str) -> BranchOutcome:
    return {o.branch: o for o in report.outcomes}[lane]


def test_a_recorded_move_restores_the_lane_its_checkout_and_its_records(tmp_path: Path) -> None:
    env = _env(tmp_path)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _lane_outcome(report, env.lane).kind is BranchOutcomeKind.RESTORED
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.before
    assert _git(env.repo, "rev-parse", tip_ref(env.lane)) == env.before
    assert _auto_rebase_refs(env.repo, env.lane) == []
    assert env.lane not in env.state.lane_rebase_moves
    _assert_checkout_matches(env.worktree, env.before)
    assert report.rebaselineable


def test_a_lane_moved_after_the_auto_rebase_is_reported_not_reset(tmp_path: Path) -> None:
    env = _env(tmp_path)
    live = _commit_here(env.worktree, "operator-on-lane")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE
    assert (outcome.observed_sha, outcome.expected_sha, outcome.restored_to_sha) == (live, env.after, env.before)
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == live, "an operator commit on top of the merge is never reset"
    rendered = report.render()
    assert env.lane in rendered
    for sha in (env.before, env.after, live):
        assert sha[:7] in rendered


def test_the_moved_lane_keeps_its_record_and_blocks_the_rebaseline(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _commit_here(env.worktree, "operator-on-lane")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert report.rebaselineable is False
    assert report.fully_restored is True, "an --abort may finish: a lane has no release mechanism"
    assert env.state.lane_rebase_moves[env.lane] == [env.before, env.after]
    assert _auto_rebase_refs(env.repo, env.lane) == [f"{_AUTO_REBASE_PREFIX}{env.lane}/{env.after}"]
    assert env.lane not in env.state.unsettled_refs, "a lane is not run-movable; settling never touches it"


def _second_auto_rebase(env: _Env, tmp_path: Path) -> str:
    """A second tool merge of the same lane in the same attempt (the Mission branch advanced again), recorded like the first."""
    mission_wt = tmp_path / "mission-wt-2"
    _git(env.repo, "worktree", "add", "-q", str(mission_wt), _MISSION_BRANCH)
    _commit_here(mission_wt, "mission-advance-2")
    _git(env.repo, "worktree", "remove", "--force", str(mission_wt))
    _git(env.worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION_BRANCH)
    second = _git(env.worktree, "rev-parse", "HEAD")
    assert auto_rebase_record.record(env.repo, env.lane, second)
    return second


@pytest.mark.parametrize("entry", ["first_move_kept", "second_move_recorded"])
def test_a_second_auto_rebase_of_one_lane_in_one_attempt_is_reported_not_restored(tmp_path: Path, entry: str) -> None:
    """Squad-3 F4: ``lane_rebase_moves`` holds ONE move per lane. A second move of the same lane in one attempt
    is never restored, whichever move the entry holds: the lane stays where it is and is reported (fail closed)."""
    env = _env(tmp_path)
    second = _second_auto_rebase(env, tmp_path)
    if entry == "second_move_recorded":
        env.state.lane_rebase_moves[env.lane] = [env.after, second]

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    expected = BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE if entry == "first_move_kept" else BranchOutcomeKind.UNCHANGED_BY_RUN
    assert outcome.kind is expected, outcome
    assert outcome.kind is not BranchOutcomeKind.RESTORED
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == second, "neither move is undone"
    assert env.lane in report.render()


def test_a_dirty_lane_checkout_is_not_restored(tmp_path: Path) -> None:
    env = _env(tmp_path)
    (env.worktree / "lane-work.txt").write_text("an uncommitted operator edit\n")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.NOT_RESTORED
    assert outcome.cause is NotRestoredCause.DIRTY_CHECKOUT
    assert outcome.blocked_checkout is not None and Path(outcome.blocked_checkout).resolve() == env.worktree.resolve()
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.after
    assert report.fully_restored is False, "the record is kept"
    assert env.state.lane_rebase_moves[env.lane] == [env.before, env.after]
    assert (env.worktree / "lane-work.txt").read_text() == "an uncommitted operator edit\n"


def test_a_refused_compare_and_swap_is_not_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: a lane that moves between the read and the compare-and-swap is reported, never forced."""
    env = _env(tmp_path)
    real_restore = rollback.restore_branch_ref

    def lane_moves_under_the_restore(repo_root: Path, branch: str, restored_sha: str, **kwargs: Any) -> None:
        if branch == env.lane:
            _commit_here(env.worktree, "racing-commit")
        real_restore(repo_root, branch, restored_sha, **kwargs)

    monkeypatch.setattr(rollback, "restore_branch_ref", lane_moves_under_the_restore)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.NOT_RESTORED and outcome.cause is NotRestoredCause.RESTORE_REFUSED
    assert env.state.lane_rebase_moves[env.lane] == [env.before, env.after]
    assert report.fully_restored is False


def test_a_deleted_lane_branch_keeps_its_record(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _git(env.repo, "worktree", "remove", "--force", str(env.worktree))
    _git(env.repo, "branch", "-D", env.lane)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _lane_outcome(report, env.lane).kind is BranchOutcomeKind.LANE_MISSING
    assert report.rebaselineable is False
    assert env.state.lane_rebase_moves[env.lane] == [env.before, env.after]


def test_a_work_tip_ref_moved_after_the_merge_is_not_overwritten_by_the_restore(tmp_path: Path) -> None:
    """The work-tip reset is compare-and-swap: a tip another writer moved off the merge stays put and is named."""
    env = _env(tmp_path)
    foreign = _git(env.repo, "rev-parse", "HEAD")
    assert foreign not in (env.before, env.after)
    assert write_bookkeeping_ref(env.repo, tip_ref(env.lane), foreign)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.RESTORED
    assert _git(env.repo, "rev-parse", tip_ref(env.lane)) == foreign
    assert outcome.reason is not None and "work-tip" in outcome.reason


def test_a_failed_record_cleanup_still_reports_the_restore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The branch IS restored; a left work-tip or auto-rebase ref is named in the report, never turned into a failure."""
    env = _env(tmp_path)
    monkeypatch.setattr(rollback, "write_bookkeeping_ref", lambda *_a, **_k: False)
    monkeypatch.setattr(rollback.auto_rebase_record, "delete", lambda *_a, **_k: False)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.RESTORED
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.before
    assert outcome.reason is not None and env.after[:12] in outcome.reason and "work-tip" in outcome.reason
    assert env.after[:12] in report.render()
    assert env.lane not in env.state.lane_rebase_moves


def test_a_render_never_suggests_a_destructive_command(tmp_path: Path) -> None:
    env = _env(tmp_path)
    _commit_here(env.worktree, "operator-on-lane")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    for follow_up in (rollback.RollbackFollowUp.ABORT, rollback.RollbackFollowUp.RESUME):
        lane_text = [line for line in report.render(follow_up).splitlines() if env.lane in line]
        assert len(lane_text) == 2, "one report line and one next step name the moved lane"
        for destructive in ("git reset", "reset --hard", "--force", "update-ref", "git branch -f"):
            assert not any(destructive in line for line in lane_text), f"{destructive!r} in {lane_text}"


def test_a_resumed_attempt_after_a_moved_lane_treats_the_kept_move_as_report_only(tmp_path: Path) -> None:
    """``begin_attempt`` re-anchors a lane that moved between attempts; the kept entry is no longer this attempt's."""
    env = _env(tmp_path)
    live = _commit_here(env.worktree, "operator-on-lane")
    assert _lane_outcome(rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET), env.lane).kind is BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE

    begin_attempt(env.repo, env.state)
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert env.state.restore_targets[env.lane] == live
    assert _lane_outcome(report, env.lane).kind is BranchOutcomeKind.ALREADY_AT_SNAPSHOT
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == live


def test_a_resumed_attempt_still_at_the_recorded_merge_keeps_the_move_restorable(tmp_path: Path) -> None:
    """An interrupted run left lane-b at its own recorded merge: the resume's rollback still undoes it."""
    env = _env(tmp_path)

    begin_attempt(env.repo, env.state)  # the --resume re-begins the attempt
    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert env.state.restore_targets[env.lane] == env.before
    assert _lane_outcome(report, env.lane).kind is BranchOutcomeKind.RESTORED
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.before


def test_a_recorded_move_to_a_reviewed_non_merge_commit_is_never_restored(tmp_path: Path) -> None:
    """Review cycle 1 repro: a stale or edited entry ``[before, live]`` naming a reviewed non-merge commit.

    The rollback must not trust the entry: ``after`` is not a two-parent merge of ``before``, so the
    lane is reported and never rewound past the reviewed commit, and its work-tip ref is kept.
    """
    env = _env(tmp_path)
    _git(env.worktree, "reset", "-q", "--hard", env.before)  # the lane at ``before`` again (test-local raw git)
    reviewed = _commit_here(env.worktree, "reviewed-work-after-snapshot")
    _git(env.repo, "update-ref", tip_ref(env.lane), reviewed)
    assert auto_rebase_record.record(env.repo, env.lane, reviewed), "even a durable record does not make a non-merge restorable"
    env.state.lane_rebase_moves[env.lane] = [env.before, reviewed]

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.UNCHANGED_BY_RUN
    assert outcome.reason is not None and "not an auto-rebase merge" in outcome.reason
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == reviewed, "the reviewed commit is never rewound"
    assert _git(env.repo, "rev-parse", tip_ref(env.lane)) == reviewed, "the lane work-tip ref is kept"
    kept = {f"{_AUTO_REBASE_PREFIX}{env.lane}/{sha}" for sha in (env.after, reviewed)}
    assert set(_auto_rebase_refs(env.repo, env.lane)) == kept, "no record is deleted"
    _assert_checkout_matches(env.worktree, reviewed)


def test_a_merge_with_another_first_parent_is_never_restored(tmp_path: Path) -> None:
    """``after`` is a two-parent merge, but not of ``before``: not this run's auto-rebase move."""
    env = _env(tmp_path)
    other_first = _git(env.repo, "rev-parse", f"refs/heads/{_TARGET}")
    tree = _git(env.repo, "rev-parse", f"{env.after}^{{tree}}")
    forged = _git(env.repo, "commit-tree", tree, "-p", other_first, "-p", env.before, "-m", "a merge of something else")
    _git(env.repo, "update-ref", f"refs/heads/{env.lane}", forged, env.after)
    _git(env.worktree, "reset", "-q", "--hard", forged)
    assert auto_rebase_record.record(env.repo, env.lane, forged)
    env.state.lane_rebase_moves[env.lane] = [env.before, forged]

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    assert _lane_outcome(report, env.lane).kind is BranchOutcomeKind.UNCHANGED_BY_RUN
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == forged


def test_an_unrecorded_merge_is_never_restored(tmp_path: Path) -> None:
    """A genuine merge of ``before`` without the durable auto-rebase record is not proven to be the tool's."""
    env = _env(tmp_path)
    _git(env.repo, "update-ref", "-d", f"{_AUTO_REBASE_PREFIX}{env.lane}/{env.after}")

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.UNCHANGED_BY_RUN
    assert outcome.reason is not None and "no auto-rebase record" in outcome.reason
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.after


@pytest.mark.parametrize("failing", ["commit_parents", "is_recorded"])
def test_a_probe_error_is_not_restored_and_keeps_the_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str) -> None:
    """NFR-002: a git probe that cannot answer never reads as "verified"; the lane is NOT_RESTORED and keeps its record."""
    env = _env(tmp_path)
    if failing == "commit_parents":

        def broken_parents(*_a: object, **_k: object) -> list[str]:
            raise rollback.GitProbeError("injected: git rev-list failed")

        monkeypatch.setattr(rollback, "commit_parents", broken_parents)
    else:

        def broken_record(*_a: object, **_k: object) -> bool:
            raise auto_rebase_record.AutoRebaseRecordError("injected: git rev-parse failed")

        monkeypatch.setattr(rollback.auto_rebase_record, "is_recorded", broken_record)

    report = rollback_to_snapshot(env.repo, env.state, target_branch=_TARGET)

    outcome = _lane_outcome(report, env.lane)
    assert outcome.kind is BranchOutcomeKind.NOT_RESTORED and outcome.cause is NotRestoredCause.RESTORE_REFUSED
    assert outcome.reason is not None and "injected" in outcome.reason
    assert _git(env.repo, "rev-parse", f"refs/heads/{env.lane}") == env.after
    assert env.state.lane_rebase_moves[env.lane] == [env.before, env.after]
    assert _auto_rebase_refs(env.repo, env.lane) == [f"{_AUTO_REBASE_PREFIX}{env.lane}/{env.after}"]
    assert report.fully_restored is False


def test_rebaseline_keeps_the_moves_of_unrestored_lanes() -> None:
    state = ConsolidationState(mission_id="M1", mission_slug=_SLUG, target_branch=_TARGET, wp_order=["WP01"])
    state.lane_rebase_moves = {"lane-x": ["a" * 40, "b" * 40], "lane-y": ["c" * 40, "d" * 40], "lane-z": ["e" * 40, "f" * 40]}
    outcomes = (
        BranchOutcome("lane-x", BranchOutcomeKind.RESTORED, "a" * 40, "b" * 40, restored_to_sha="a" * 40),
        BranchOutcome("lane-y", BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE, "c" * 40, "9" * 40, "d" * 40, restored_to_sha="c" * 40),
        BranchOutcome("lane-z", BranchOutcomeKind.NOT_RESTORED, "e" * 40, "f" * 40, "f" * 40, cause=NotRestoredCause.DIRTY_CHECKOUT),
    )

    assert rebaseline_after_full_restore(state, iter(outcomes)) is True

    assert state.lane_rebase_moves == {"lane-y": ["c" * 40, "d" * 40], "lane-z": ["e" * 40, "f" * 40]}
