"""#7578 (FR-002, ruling Q3): a commit-to-target ``single_branch`` Mission records its window points.

A Mission whose STORED topology is ``single_branch`` and whose write branch IS its target
(``--commit-to-target``: no ``meta.mission_branch``) now stamps every lifecycle transition with the
target branch head (``policy_metadata.lane_head``) and opens a work-package window
(``policy_metadata.wp_window.open_sha``) at that head. The review range (#7578) reads a recorded
window on every topology.

Unchanged around it: a ``lanes`` Mission's planning-lane work package stays unstamped (C-009), a
minted ``single_branch`` Mission stamps its minted branch, and a Mission with no stored topology or
no recorded target keeps the lane-map reading. The probe never raises (C-1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.lane_head import CaptureCause, LaneHeadReading, read_lane_head
from specify_cli.status.models import TransitionRequest
from specify_cli.status.store import read_events
from tests.integration.coord_topology_fixture import FlatTopologyContext, build_flat_topology_mission
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.git_repo]

_TARGET = "main"
_CTT_SLUG = "ctt-fixture-01CTTFIX"
_SB_SLUG = "sb-fixture-01SBFIXT"
_SB_BRANCH = "kitty/mission-sb-fixture-01SBFIXT"
_LANES_SLUG = "lanes-fixture-01LNFIXT"
_BARE_SLUG = "bare-fixture-01BAREFX"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write_mission(repo: Path, slug: str, *, topology: str | None, mission_branch: str | None, target: str | None = _TARGET) -> None:
    """``meta.json`` and a one-lane ``lane-planning`` ``lanes.json`` holding WP01, as finalize writes them."""
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": f"{slug[-8:]}000000000000000000",
        "mission_slug": slug,
        "slug": slug,
        "mission_type": "software-dev",
        "vcs": "git",
    }
    if target is not None:
        meta["target_branch"] = target
    if topology is not None:
        meta["topology"] = topology
    if mission_branch is not None:
        meta["mission_branch"] = mission_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    lanes = {
        "version": 1,
        "mission_slug": slug,
        "mission_id": meta["mission_id"],
        "mission_branch": mission_branch or _TARGET,
        "target_branch": _TARGET,
        "lanes": [
            {
                "lane_id": "lane-planning",
                "wp_ids": ["WP01"],
                "write_scope": ["src/**"],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-11-12T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes, indent=2), encoding="utf-8")


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def missions(tmp_path: Path) -> Path:
    """One repository holding a commit-to-target, a minted ``single_branch``, a ``lanes`` and a bare Mission.

    The checkout sits on ``main`` (the commit-to-target write checkout); the minted Mission branch carries
    one commit beyond ``main``, so the two heads differ.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _write_mission(repo, _CTT_SLUG, topology="single_branch", mission_branch=None)
    _write_mission(repo, _SB_SLUG, topology="single_branch", mission_branch=_SB_BRANCH)
    _write_mission(repo, _LANES_SLUG, topology="lanes", mission_branch=f"kitty/mission-{_LANES_SLUG}")
    _commit(repo, "seed.txt", "seed\n", "seed: four missions")
    _git(repo, "branch", _SB_BRANCH)
    _git(repo, "checkout", "-q", _SB_BRANCH)
    _commit(repo, "src/minted.py", "VALUE = 1\n", "feat(WP01): implement on the minted branch")
    _git(repo, "checkout", "-q", _TARGET)
    _commit(repo, "src/impl.py", "VALUE = 2\n", "feat(WP01): implement on the target")
    return repo


# --------------------------------------------------------------------------- the probe


@pytest.mark.fast
def test_commit_to_target_single_branch_stamps_target_head(missions: Path) -> None:
    """#7578: the reading is the target branch head, applicable."""
    reading = read_lane_head(repo_root=missions, mission_slug=_CTT_SLUG, wp_id="WP01")

    assert reading == LaneHeadReading.of_sha(_git(missions, "rev-parse", f"refs/heads/{_TARGET}"))
    assert reading.applicable


@pytest.mark.fast
def test_commit_to_target_stamp_reads_the_target_ref_not_the_checkout_head(missions: Path) -> None:
    """The stamp reads ``refs/heads/<target>``: the same from a checkout on another branch."""
    head = _git(missions, "rev-parse", f"refs/heads/{_TARGET}")
    _git(missions, "checkout", "-q", _SB_BRANCH)

    assert read_lane_head(repo_root=missions, mission_slug=_CTT_SLUG, wp_id="WP01").sha == head


@pytest.mark.fast
def test_commit_to_target_with_absent_target_ref_is_a_failed_reading(missions: Path) -> None:
    """C-1: a recorded target whose branch does not exist is ``lane_branch_missing``, never an exception."""
    meta_path = missions / "kitty-specs" / _CTT_SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["target_branch"] = "release/absent"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    reading = read_lane_head(repo_root=missions, mission_slug=_CTT_SLUG, wp_id="WP01")

    assert reading.sha is None and reading.applicable
    assert reading.cause is CaptureCause.LANE_BRANCH_MISSING, reading
    assert "release/absent" in reading.detail


@pytest.mark.fast
def test_commit_to_target_git_failure_is_a_git_error_reading(missions: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-1: a failing ``git rev-parse`` is ``git_error``, never an exception."""
    import specify_cli.core.git_ops as git_ops

    real = git_ops.run_command

    def _fake(cmd: Any, **kwargs: Any) -> tuple[int, str, str]:
        if list(cmd[:3]) == ["git", "rev-parse", "--verify"]:
            return 128, "", "fatal: unable to read packed-refs"
        return real(cmd, **kwargs)

    monkeypatch.setattr(git_ops, "run_command", _fake)

    reading = read_lane_head(repo_root=missions, mission_slug=_CTT_SLUG, wp_id="WP01")

    assert reading.cause is CaptureCause.GIT_ERROR and "packed-refs" in reading.detail, reading


@pytest.mark.fast
def test_lanes_planning_lane_stays_not_applicable(missions: Path) -> None:
    """C-009 positive control, same repository: a ``lanes`` Mission's planning-lane work package records nothing."""
    assert read_lane_head(repo_root=missions, mission_slug=_LANES_SLUG, wp_id="WP01") == LaneHeadReading.not_applicable()


@pytest.mark.fast
def test_minted_single_branch_still_stamps_the_minted_branch(missions: Path) -> None:
    """Unchanged: a minted ``single_branch`` Mission stamps its Mission branch head, never the target."""
    minted = _git(missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")
    assert minted != _git(missions, "rev-parse", f"refs/heads/{_TARGET}")

    assert read_lane_head(repo_root=missions, mission_slug=_SB_SLUG, wp_id="WP01") == LaneHeadReading.of_sha(minted)


@pytest.mark.fast
@pytest.mark.parametrize(
    ("topology", "target"),
    [pytest.param(None, _TARGET, id="no-stored-topology"), pytest.param("single_branch", None, id="no-recorded-target")],
)
def test_mission_without_topology_or_target_keeps_the_lane_map_reading(missions: Path, topology: str | None, target: str | None) -> None:
    """Unchanged: without a stored ``single_branch`` topology and a recorded target, the planning lane reads not applicable."""
    _write_mission(missions, _BARE_SLUG, topology=topology, mission_branch=None, target=target)

    assert read_lane_head(repo_root=missions, mission_slug=_BARE_SLUG, wp_id="WP01") == LaneHeadReading.not_applicable()


# --------------------------------------------------------------------------- through the pipeline


@pytest.fixture
def ctt_mission(tmp_path: Path) -> FlatTopologyContext:
    """The shared flat fixture's commit-to-target ``single_branch`` Mission, WP01 seeded to ``planned``."""
    ctx = build_flat_topology_mission(tmp_path, topology="single_branch")
    ctx.status_events_path.unlink()
    _git(ctx.repo, "add", "-A")
    _git(ctx.repo, "commit", "-qm", "test: start WP01 with no status log")
    seed_wp_to_planned(ctx.primary_feature_dir, "WP01", slug=ctx.slug)
    return ctx


def _emit(ctx: FlatTopologyContext, to_lane: str, **extra: Any) -> dict[str, Any]:
    request = TransitionRequest(
        feature_dir=ctx.primary_feature_dir,
        mission_slug=ctx.slug,
        wp_id="WP01",
        to_lane=to_lane,
        actor="tester",
        repo_root=ctx.repo,
        **extra,
    )
    event = emit_status_transition(request)
    (persisted,) = [e for e in read_events(ctx.primary_feature_dir) if e.event_id == event.event_id]
    return dict(persisted.policy_metadata or {})


@pytest.mark.integration
def test_pipeline_records_window_open_and_lane_head_at_target_head(ctt_mission: FlatTopologyContext) -> None:
    """``claimed`` and ``in_progress`` open the window at the target head; ``for_review`` records it as ``lane_head``."""
    head = _git(ctt_mission.repo, "rev-parse", f"refs/heads/{_TARGET}")

    claimed = _emit(ctt_mission, "claimed")
    in_progress = _emit(ctt_mission, "in_progress", workspace_context="repo-root")
    for_review = _emit(ctt_mission, "for_review", force=True, reason="handed to review")

    assert claimed.get(WP_WINDOW_KEY) == {"schema_version": 1, "open_sha": head}, claimed
    assert in_progress.get(WP_WINDOW_KEY) == {"schema_version": 1, "open_sha": head}, in_progress
    assert claimed.get(LANE_HEAD_KEY) == head and in_progress.get(LANE_HEAD_KEY) == head
    assert for_review.get(LANE_HEAD_KEY) == head, for_review
    assert WP_WINDOW_KEY not in for_review
