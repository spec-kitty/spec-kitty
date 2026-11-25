"""#7802: the lane-head reading carries the pre-sync tip, and the pipeline stamps it as ``lane_head_presync``.

``read_lane_head`` reports ``presync_sha`` only when the clone-local
``refs/spec-kitty/review-presync/<lane>`` ref differs from the lane head and every commit on the
head's first-parent path down to it is a merge commit. Any other shape is ``None``, and the
``lane_head`` reading itself never changes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.status import LANE_HEAD_KEY, LANE_HEAD_PRESYNC_KEY, TransitionRequest, review_presync_ref, sits_on_through_merges
from specify_cli.status.emit import emit_status_transition, emit_status_transition_batch
from specify_cli.status.lane_head import LaneHeadReading, read_lane_head
from specify_cli.status.wp_window import CaptureCause
from tests.integration.coord_topology_fixture import FlatTopologyContext, _git, build_flat_topology_mission
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]

_WP = "WP01"


@pytest.fixture
def flat_mission(tmp_path: Path) -> FlatTopologyContext:
    ctx = build_flat_topology_mission(tmp_path, topology="lanes")
    _git(ctx.repo, "rm", "-q", "--", str(ctx.status_events_path.relative_to(ctx.repo)))
    _git(ctx.repo, "commit", "-qm", "test: start WP01 with no status log")
    return ctx


@pytest.fixture
def lane(flat_mission: FlatTopologyContext, tmp_path: Path) -> tuple[Path, str]:
    """``(lane worktree, lane branch)``, the branch one commit ahead of ``main``."""
    branch = lane_branch_name(flat_mission.slug, "lane-a", target_branch="main")
    worktree = tmp_path / "lane-worktree"
    _git(flat_mission.repo, "worktree", "add", "-q", "-b", branch, str(worktree), "main")
    _commit(worktree, "impl.txt", "lane work")
    return worktree, branch


def _commit(worktree: Path, name: str, text: str) -> str:
    (worktree / name).write_text(f"{text}\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", f"commit {name}")
    return _git(worktree, "rev-parse", "HEAD")


def _side_branch_commit(repo: Path, tmp_path: Path, name: str) -> str:
    """A new commit on a side branch off ``main`` (what a sync merge brings in); returns the branch name."""
    branch = f"side-{name}"
    side = tmp_path / f"side-{name}"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(side), "main")
    _commit(side, f"{name}.txt", name)
    _git(repo, "worktree", "remove", "-f", str(side))
    return branch


def _merge(worktree: Path, source: str) -> str:
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", source)
    return _git(worktree, "rev-parse", "HEAD")


def _record(repo: Path, branch: str, sha: str) -> None:
    _git(repo, "update-ref", review_presync_ref(branch), sha)


def _reading(ctx: FlatTopologyContext) -> LaneHeadReading:
    return read_lane_head(repo_root=ctx.repo, mission_slug=ctx.slug, wp_id=_WP)


def test_a_head_on_merges_only_reports_the_recorded_pre_sync_tip(flat_mission: FlatTopologyContext, lane: tuple[Path, str], tmp_path: Path) -> None:
    worktree, branch = lane
    presync = _git(worktree, "rev-parse", "HEAD")
    _record(flat_mission.repo, branch, presync)
    _merge(worktree, _side_branch_commit(flat_mission.repo, tmp_path, "one"))
    head = _merge(worktree, _side_branch_commit(flat_mission.repo, tmp_path, "two"))

    reading = _reading(flat_mission)

    assert reading.sha == head
    assert reading.presync_sha == presync


def test_a_non_merge_commit_between_the_tip_and_the_head_reports_none(flat_mission: FlatTopologyContext, lane: tuple[Path, str], tmp_path: Path) -> None:
    worktree, branch = lane
    _record(flat_mission.repo, branch, _git(worktree, "rev-parse", "HEAD"))
    _merge(worktree, _side_branch_commit(flat_mission.repo, tmp_path, "one"))
    head = _commit(worktree, "reviewer.txt", "a reviewer commit on top of the sync merge")

    reading = _reading(flat_mission)

    assert reading.sha == head
    assert reading.presync_sha is None


def test_no_recorded_ref_or_a_ref_at_the_head_reports_none(flat_mission: FlatTopologyContext, lane: tuple[Path, str], tmp_path: Path) -> None:
    worktree, branch = lane
    _merge(worktree, _side_branch_commit(flat_mission.repo, tmp_path, "one"))
    assert _reading(flat_mission).presync_sha is None

    _record(flat_mission.repo, branch, _git(worktree, "rev-parse", "HEAD"))
    assert _reading(flat_mission).presync_sha is None


def test_a_tip_reached_only_through_a_second_parent_reports_none(flat_mission: FlatTopologyContext, lane: tuple[Path, str], tmp_path: Path) -> None:
    """The tip must be a first-parent ancestor: a merge INTO another branch that is then merged in does not count."""
    worktree, branch = lane
    lane_tip = _git(worktree, "rev-parse", "HEAD")
    _record(flat_mission.repo, branch, lane_tip)
    _git(worktree, "checkout", "-q", "--detach", "main")
    _commit(worktree, "other.txt", "other line of work")
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", lane_tip)
    rebuilt = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "checkout", "-q", branch)
    _git(worktree, "reset", "-q", "--hard", rebuilt)

    assert _reading(flat_mission).presync_sha is None


def test_a_merges_only_head_that_reaches_the_tip_only_through_a_second_parent_is_not_on_it(flat_mission: FlatTopologyContext, lane: tuple[Path, str]) -> None:
    """M12b: every commit down to the tip is a merge, yet the tip is only a second parent, never a first-parent ancestor."""
    worktree, branch = lane
    lane_tip = _git(worktree, "rev-parse", "HEAD")
    _record(flat_mission.repo, branch, lane_tip)
    _git(worktree, "checkout", "-q", "--detach", "main")
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", lane_tip)
    rebuilt = _git(worktree, "rev-parse", "HEAD")
    _git(worktree, "checkout", "-q", branch)
    _git(worktree, "reset", "-q", "--hard", rebuilt)

    assert sits_on_through_merges(flat_mission.repo, lane_tip, rebuilt) is False
    assert _reading(flat_mission).presync_sha is None


def _raise_on_presync() -> Callable[..., tuple[int, str, str]]:
    """A ``run_command`` that fails every read of the pre-sync ref and runs every other command for real."""
    from specify_cli.core import git_ops

    real = git_ops.run_command

    def _run(cmd: list[str], **kwargs: Any) -> tuple[int, str, str]:
        if any("review-presync" in part for part in cmd):
            raise OSError("git exploded")
        result: tuple[int, str, str] = real(cmd, **kwargs)
        return result

    return _run


@pytest.mark.parametrize(
    ("sha", "applicable", "cause", "presync"),
    [
        (None, False, None, "a" * 40),
        ("a" * 40, True, None, "a" * 40),
        ("a" * 40, True, None, ""),
        (None, True, CaptureCause.GIT_ERROR, "b" * 40),
    ],
)
def test_the_pre_sync_tip_is_valid_only_beside_a_distinct_sha(sha: str | None, applicable: bool, cause: CaptureCause | None, presync: str) -> None:
    with pytest.raises(ValueError, match="presync_sha"):
        LaneHeadReading(sha=sha, applicable=applicable, cause=cause, presync_sha=presync)


def test_of_sha_carries_an_optional_pre_sync_tip() -> None:
    assert LaneHeadReading.of_sha("a" * 40).presync_sha is None
    assert LaneHeadReading.of_sha("a" * 40, "b" * 40).presync_sha == "b" * 40


def _request(ctx: FlatTopologyContext, to_lane: str, *, workspace_context: str | None = None) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=ctx.primary_feature_dir,
        mission_slug=ctx.slug,
        wp_id=_WP,
        to_lane=to_lane,
        actor="presync-tester",
        repo_root=ctx.repo,
        workspace_context=workspace_context,
    )


def test_the_single_and_batch_shells_stamp_the_pre_sync_tip_beside_the_lane_head(flat_mission: FlatTopologyContext, lane: tuple[Path, str], tmp_path: Path) -> None:
    worktree, branch = lane
    presync = _git(worktree, "rev-parse", "HEAD")
    _record(flat_mission.repo, branch, presync)
    head = _merge(worktree, _side_branch_commit(flat_mission.repo, tmp_path, "one"))
    seed_wp_to_planned(flat_mission.primary_feature_dir, _WP, slug=flat_mission.slug)

    single = emit_status_transition(_request(flat_mission, "claimed"))
    batch = emit_status_transition_batch([_request(flat_mission, "in_progress", workspace_context="worktree:/x")])

    for event in (single, *batch):
        assert event.policy_metadata is not None
        assert event.policy_metadata[LANE_HEAD_KEY] == head
        assert event.policy_metadata[LANE_HEAD_PRESYNC_KEY] == presync


def test_no_pre_sync_tip_writes_no_key(flat_mission: FlatTopologyContext, lane: tuple[Path, str]) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, _WP, slug=flat_mission.slug)

    event = emit_status_transition(_request(flat_mission, "claimed"))

    assert event.policy_metadata is not None
    assert LANE_HEAD_KEY in event.policy_metadata
    assert LANE_HEAD_PRESYNC_KEY not in event.policy_metadata


def test_a_git_failure_never_fails_the_reading(flat_mission: FlatTopologyContext, lane: tuple[Path, str], monkeypatch: pytest.MonkeyPatch) -> None:
    worktree, branch = lane
    head = _git(worktree, "rev-parse", "HEAD")
    _record(flat_mission.repo, branch, head)
    monkeypatch.setattr("specify_cli.core.git_ops.run_command", _raise_on_presync())

    reading = _reading(flat_mission)

    assert reading.sha == head
    assert reading.presync_sha is None
    assert reading.cause is None


def test_sits_on_through_merges_is_false_for_the_head_itself_an_empty_tip_and_a_git_failure(
    flat_mission: FlatTopologyContext, lane: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree, _branch = lane
    head = _git(worktree, "rev-parse", "HEAD")

    assert sits_on_through_merges(flat_mission.repo, head, head) is False
    assert sits_on_through_merges(flat_mission.repo, "", head) is False

    def _fail(cmd: list[str], **kwargs: Any) -> tuple[int, str, str]:
        raise OSError("git exploded")

    monkeypatch.setattr("specify_cli.core.git_ops.run_command", _fail)
    assert sits_on_through_merges(flat_mission.repo, _git(worktree, "rev-parse", "HEAD^"), head) is False
