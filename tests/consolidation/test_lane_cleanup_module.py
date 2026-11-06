"""The one lane-cleanup module behind a remover port (S5, FR-030, FR-033, FR-034, FR-035, NFR-008).

Seam-level cases run the module over a small real git repository: the plan is pure, ``apply`` never
raises, retention is reported apart from a refusal, a lane-tip ref is cleared only after a confirmed
branch delete, and a remover with no process proof keeps the lane (the off-Linux behaviour,
simulated). The FR-035 case drives the REAL ``spec-kitty consolidate`` and kills it right after
cleanup's own commit, then resumes.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation.lane_cleanup import (
    LaneCleanupItem,
    LaneCleanupOutcome,
    LaneCleanupResult,
    LaneRetention,
    LocalTargetAtPass,
    MainTodayRemover,
    apply,
    plan_lane_cleanup,
)
from specify_cli.coordination.coherence import CheckoutRole, residue_context_or_strictest
from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.workspace.process_probe import ProcessProbeResult
from tests.consolidation.test_lane_cleanup_kept_report import (
    consolidate_args,
    git,
    lane_branch,
    lane_worktree,
    output,
    ref_exists,
    run_patched,
    state_files,
)
from tests.terminus.conftest import build_coord_mission, run_terminus

pytestmark = [pytest.mark.git_repo]

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "specify_cli"
_TIP_PREFIX = "refs/spec-kitty/lane-tip/"
_LANDING = LocalTargetAtPass(target_ref="main", passed_sha="0" * 40)


def _manifest(slug: str, lane_ids: tuple[str, ...] = ("lane-a", "lane-b")) -> LanesManifest:
    lanes = [
        ExecutionLane(lane_id=lane_id, wp_ids=(f"WP0{idx + 1}",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
        for idx, lane_id in enumerate(lane_ids)
    ]
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id="01M7280X" + "0" * 18,
        mission_branch=f"kitty/mission-{slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-11-06T00:00:00+00:00",
        computed_from="test",
    )


# -- T091: one answer for the lane branch name ------------------------------------------------------


def test_branch_name_drift_pinned(tmp_path: Path) -> None:
    """The handle a caller holds (here the mission id) composed a branch that was never created."""
    manifest = _manifest("payments-01M7280X")
    handle = manifest.mission_id
    drifted = code_lane_branch_name(handle, "lane-a")
    created = lane_created_branch(manifest, "lane-a")
    assert drifted != created, "fixture invalid: the two compositions must disagree"

    items = plan_lane_cleanup(manifest, repo_root=tmp_path)

    assert [item.branch for item in items] == [lane_created_branch(manifest, lane.lane_id) for lane in manifest.lanes]
    assert [item.worktree for item in items] == [tmp_path / ".worktrees" / f"{manifest.mission_slug}-{lane.lane_id}" for lane in manifest.lanes]


def test_planning_lane_is_never_a_cleanup_item(tmp_path: Path) -> None:
    manifest = _manifest("plan-01M7280X", ("lane-planning", "lane-a"))
    items = plan_lane_cleanup(manifest, repo_root=tmp_path, expected_tips={"kitty/mission-plan-01M7280X-lane-a": "abc"})
    assert [(item.lane_id, item.expected_tip) for item in items] == [("lane-a", "abc")]


@pytest.mark.parametrize(
    "path",
    ["consolidation/phase_teardown.py", "orchestrator_api/consolidation.py", "cli/commands/mission_type.py"],
)
def test_every_lane_teardown_caller_goes_through_the_module(path: str) -> None:
    """FR-030: the three former copies call ``lane_cleanup.apply`` and no longer delete lane branches themselves."""
    tree = ast.parse((_SRC_ROOT / path).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "specify_cli.consolidation.lane_cleanup" in imports, path
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "code_lane_branch_name" not in names, f"{path} must not compose lane branch names itself"


# -- a small real repository for the remover ---------------------------------------------------------


@dataclass
class _Repo:
    root: Path
    manifest: LanesManifest

    def branch(self, lane_id: str) -> str:
        return lane_created_branch(self.manifest, lane_id)

    def remover(self, *, probe: Callable[[Sequence[Path]], ProcessProbeResult]) -> MainTodayRemover:
        context = residue_context_or_strictest(self.root, self.manifest.mission_slug, CheckoutRole.LANE)
        return MainTodayRemover(self.root, context=context, probe=probe)


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    for key, value in (("user.email", "t@t"), ("user.name", "T"), ("commit.gpgsign", "false")):
        git(root, "config", key, value)
    (root / "README.md").write_text("x\n", encoding="utf-8")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    git(root, "add", "README.md", ".gitignore")
    git(root, "commit", "-qm", "init")
    manifest = _manifest("unit-01M7280X")
    built = _Repo(root, manifest)
    for lane in manifest.lanes:
        git(root, "branch", built.branch(lane.lane_id))
        git(root, "update-ref", f"{_TIP_PREFIX}{built.branch(lane.lane_id)}", git(root, "rev-parse", "main"))
    return built


def _available(_paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


def _unavailable(_paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=False, detail="no /proc on this platform")


def test_missing_branch_keeps_its_lane_tip_ref(repo: _Repo) -> None:
    branch = repo.branch("lane-a")
    git(repo.root, "branch", "-D", branch)

    report = apply(plan_lane_cleanup(repo.manifest, repo_root=repo.root), repo.remover(probe=_available), landing=_LANDING, retention=LaneRetention())

    assert ref_exists(repo.root, f"{_TIP_PREFIX}{branch}"), "FR-034: the tip ref is the last reference to a missing branch"
    assert not ref_exists(repo.root, f"{_TIP_PREFIX}{repo.branch('lane-b')}"), "a confirmed delete clears its tip ref"
    assert [result.outcome for result in report.results] == [LaneCleanupOutcome.REMOVED, LaneCleanupOutcome.REMOVED]
    assert report.results[1].recreate is not None and repo.branch("lane-b") in report.results[1].recreate


def test_unique_commits_keep_the_branch_and_its_tip(repo: _Repo) -> None:
    branch = repo.branch("lane-a")
    git(repo.root, "checkout", "-q", branch)
    (repo.root / "work.txt").write_text("only copy\n", encoding="utf-8")
    git(repo.root, "add", "work.txt")
    git(repo.root, "commit", "-qm", "unlanded work")
    git(repo.root, "checkout", "-q", "main")

    report = apply(plan_lane_cleanup(repo.manifest, repo_root=repo.root), repo.remover(probe=_available), landing=_LANDING, retention=LaneRetention())

    kept = report.results[0]
    assert kept.outcome is LaneCleanupOutcome.KEPT and kept.code == "BRANCH_HAS_UNIQUE_COMMITS"
    assert kept.command == "spec-kitty doctor workspaces --prune" and kept.remedy
    assert ref_exists(repo.root, f"refs/heads/{branch}") and ref_exists(repo.root, f"{_TIP_PREFIX}{branch}")
    assert report.kept == (kept,)


def test_retention_is_reported_apart_from_kept(repo: _Repo) -> None:
    report = apply(
        plan_lane_cleanup(repo.manifest, repo_root=repo.root),
        repo.remover(probe=_available),
        landing=_LANDING,
        retention=LaneRetention(remove_worktree=False, delete_branch=False),
    )

    assert {result.outcome for result in report.results} == {LaneCleanupOutcome.RETAINED_BY_POLICY}
    assert all(ref_exists(repo.root, f"refs/heads/{repo.branch(lane.lane_id)}") for lane in repo.manifest.lanes)
    lines = report.render_lines()
    assert lines[0] == "Lane cleanup" and all("retained by policy" in line for line in lines[1:]), lines
    assert report.to_json()[0]["outcome"] == "retained_by_policy"


def test_no_process_proof_keeps_the_worktree(repo: _Repo) -> None:
    """NFR-008 simulated: off Linux the probe is unavailable, so a lane worktree is kept and reported."""
    worktree = repo.root / ".worktrees" / f"{repo.manifest.mission_slug}-lane-a"
    git(repo.root, "worktree", "add", "-q", str(worktree), repo.branch("lane-a"))

    report = apply(plan_lane_cleanup(repo.manifest, repo_root=repo.root), repo.remover(probe=_unavailable), landing=_LANDING, retention=LaneRetention())

    kept = report.results[0]
    assert kept.outcome is LaneCleanupOutcome.KEPT and kept.code == "PROCESS_PROOF_UNAVAILABLE", kept
    assert worktree.is_dir() and ref_exists(repo.root, f"refs/heads/{repo.branch('lane-a')}")
    assert report.results[1].outcome is LaneCleanupOutcome.REMOVED, "a lane without a worktree needs no process proof"


def test_a_busy_worktree_is_kept(repo: _Repo) -> None:
    worktree = repo.root / ".worktrees" / f"{repo.manifest.mission_slug}-lane-a"
    git(repo.root, "worktree", "add", "-q", str(worktree), repo.branch("lane-a"))

    def busy(paths: Sequence[Path]) -> ProcessProbeResult:
        return ProcessProbeResult(available=True, busy=frozenset({worktree}))

    report = apply(plan_lane_cleanup(repo.manifest, repo_root=repo.root), repo.remover(probe=busy), landing=_LANDING, retention=LaneRetention())

    assert report.results[0].code == "PROCESS_IN_WORKTREE" and worktree.is_dir()


def test_apply_never_raises_after_a_verified_landing(repo: _Repo) -> None:
    class Exploding:
        def remove(self, item: LaneCleanupItem, *, landing: object) -> LaneCleanupResult:
            raise RuntimeError("boom")

    report = apply(plan_lane_cleanup(repo.manifest, repo_root=repo.root), Exploding(), landing=_LANDING, retention=LaneRetention())

    assert all(result.outcome is LaneCleanupOutcome.KEPT and result.code == "LANE_CLEANUP_FAILED" for result in report.results)


# -- T091 / FR-035: resume after a kill inside cleanup ---------------------------------------------


def _kill_after_cleanup_commit() -> str:
    return """
from specify_cli.consolidation import phase_teardown as _teardown
_original_commit = _teardown._commit_tombstoned_workspace_contexts
def _commit_tombstoned_workspace_contexts(run, tombstoned):
    _original_commit(run, tombstoned)
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(137)
_teardown._commit_tombstoned_workspace_contexts = _commit_tombstoned_workspace_contexts
"""


@pytest.mark.integration
def test_resume_after_kill_in_cleanup_skips_regate(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M7280F")
    # Tracked workspace contexts make cleanup commit their tombstones onto the target (#6450).
    workspaces = mission.repo / ".kittify" / "workspaces"
    workspaces.mkdir(parents=True, exist_ok=True)
    for lane_id in ("lane-a", "lane-b"):
        git(mission.repo, "worktree", "add", "-q", str(lane_worktree(mission, lane_id)), lane_branch(mission, lane_id))
        (workspaces / f"{mission.slug}-{lane_id}.json").write_text('{"workspace_name": "x"}\n', encoding="utf-8")
    git(mission.repo, "add", "-f", ".kittify/workspaces")
    git(mission.repo, "commit", "-qm", "chore: track lane workspace contexts")

    killed = run_patched(mission, consolidate_args(mission), _kill_after_cleanup_commit())
    assert killed.returncode == 137, output(killed)
    assert state_files(mission), f"the kill must leave the record behind\n{output(killed)}"

    resumed = run_terminus(mission, consolidate_args(mission, "--resume"))

    out = output(resumed)
    assert resumed.returncode == 0, f"an interrupted cleanup must not be a dead end (FR-035)\n{out}"
    assert "UNEXPLAINED_BRANCH_MOVE" not in out and "Traceback" not in out, out
    assert state_files(mission) == [], out
    for lane_id in ("lane-a", "lane-b"):
        assert not ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, lane_id)}"), out
