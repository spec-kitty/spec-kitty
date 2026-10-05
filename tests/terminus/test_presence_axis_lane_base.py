"""#5792 review (M1) -- the presence axis measures a lane from the lane's OWN base.

#5788 measured each approved lane's content (:class:`ApprovedLaneContent`) from
the target's pre-mutation tip, so the lane-a range swallowed every mission-branch
commit between that tip and the commit lane-a was cut from. A mission-branch
commit made outside every lane before the lanes were cut (operator scaffolding)
was then read as WP01's approved content; a later mission-branch commit that
deleted it again (net zero for the mission) made the squash FAIL with a false
``APPROVED_CONTENT_MISSING`` naming WP01. Before #5788 the run landed.

Same fixture, control: without the deleting commit the scaffolding is on the
target and nothing is reported missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.terminus.approved_content_support import ADDED_PATH, _wp01_work, _wp02_work
from tests.terminus.canceled_dependency_support import ACTOR, WP02_PATH, _approve, _commit_in, _manifest, _wp_file
from tests.terminus.conftest import (
    _STATUS_EVENTS_FILENAME,
    CoordMission,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _git,
    _git_out,
    _init_fixture_repo,
    _write_meta,
)
from tests.terminus.mixed_lane_support import transition

SCRATCH = "src/pkg/scratch.py"
WP_PATHS = {"WP01": ADDED_PATH, "WP02": WP02_PATH}

pytestmark = pytest.mark.git_repo


def _coord_worktree(mission: CoordMission) -> Path:
    trees = [line.split(" ", 1)[1] for line in _git_out(mission.repo, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    return next(Path(tree) for tree in trees if _git_out(Path(tree), "rev-parse", "--abbrev-ref", "HEAD").strip() == mission.coord_branch)


def _build(tmp_path: Path, mid8: str, *, drop_scaffolding: bool) -> CoordMission:
    """WP01 (lane-a) and WP02 (lane-b, depends on WP01) approved; the mission branch got scaffolding BEFORE the lanes were cut."""
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main", extra_base_files={})
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = _manifest(mission, depends=True)
    write_lanes_json(mission.feature_dir, manifest)
    (mission.feature_dir / "tasks" / "WP01-work.md").write_text(_wp_file("WP01", dependencies=()), encoding="utf-8")
    (mission.feature_dir / "tasks" / "WP02-work.md").write_text(_wp_file("WP02", dependencies=("WP01",)), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap")
    _cut_coord_branch(mission)
    _git(mission.repo, "checkout", "-q", mission.coord_branch)
    _commit_in(mission.repo, SCRATCH, "x = 1\n", "chore: scaffolding outside every lane")
    _git(mission.repo, "checkout", "-q", "main")
    _finish_coord_mission(mission)
    manifest = read_lanes_json(mission.feature_dir) or manifest
    a_tree, a_branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _wp01_work(a_tree, "none", slug)
    _approve(mission, "WP01", reference="r1")
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    b_tree, b_branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    _wp02_work(b_tree, "none", slug)
    _approve(mission, "WP02", reference="r2")
    mission.lane_branches.update({"WP01": a_branch, "WP02": b_branch})
    if drop_scaffolding:
        coord = _coord_worktree(mission)
        _git(coord, "rm", "-q", SCRATCH)
        _git(coord, "commit", "-qm", "chore: drop the scaffolding (never a lane's work)")
    return mission


def _consolidate(mission: CoordMission, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    from specify_cli.consolidation import executor

    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)
    code = 0
    try:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)
    except typer.Exit as exc:
        code = int(exc.exit_code or 0)
    return code, " ".join(capsys.readouterr().out.split())


def _blob_on(mission: CoordMission, ref: str, path: str) -> bool:
    return bool(_git_out(mission.repo, "ls-tree", "--name-only", ref, "--", path).strip())


def test_mission_branch_commit_outside_every_lane_is_not_a_lanes_approved_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The scaffolding added and deleted again on the mission branch is no lane's content: the squash lands both WPs."""
    mission = _build(tmp_path, "01MPB5E1", drop_scaffolding=True)

    code, output = _consolidate(mission, monkeypatch, capsys)

    assert "APPROVED_CONTENT_MISSING" not in output, f"mission-branch scaffolding is no lane's approved content:\n{output}"
    assert code == 0, output
    for wp, path in WP_PATHS.items():
        assert _blob_on(mission, mission.target_branch, path), f"{wp}'s approved code must land"
    assert not _blob_on(mission, mission.target_branch, SCRATCH), "the mission branch's net state (no scaffolding) lands"


def test_control_scaffolding_kept_on_the_mission_branch_is_not_reported_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same fixture, the scaffolding stays: the presence axis stays silent.

    Pre-existing residual (fail closed, not this axis): content committed on the
    mission branch outside every lane is attributable to no approved WP, so the
    squash blob axis refuses it and the door restores the target.
    """
    mission = _build(tmp_path, "01MPB5E2", drop_scaffolding=False)
    pre_target = _git_out(mission.repo, "rev-parse", mission.target_branch).strip()

    code, output = _consolidate(mission, monkeypatch, capsys)

    assert "APPROVED_CONTENT_MISSING" not in output, f"present content is never reported missing:\n{output}"
    assert code == 1, output
    assert SCRATCH in output and "belongs to NO approved WP" in output, f"the residual: the blob axis refuses:\n{output}"
    assert _git_out(mission.repo, "rev-parse", mission.target_branch).strip() == pre_target, "the door restores the target"
