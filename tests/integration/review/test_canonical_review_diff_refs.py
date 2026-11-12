from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.workflow import _resolve_review_context
from specify_cli.cli.commands.agent.workflow_cores import wp_owned_files
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.wp_range import RangeStatus, WpReviewRange
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, Lane, StatusEvent
from specify_cli.status.store import append_events_atomic

pytestmark = pytest.mark.git_repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _rev_parse(repo: Path, ref: str) -> str:
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _event(event_id: str, from_lane: Lane, to_lane: Lane, metadata: dict[str, object]) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="mission-canonical-refs",
        wp_id="WP03",
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-05-02T09:0{event_id[-1]}:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata=metadata,
    )


def test_review_diff_refs_use_canonical_manifest_for_mission_prefixed_slug(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    mission_slug = "mission-canonical-refs"
    mission_branch = "kitty/mission-canonical-refs"
    lane_branch = "kitty/mission-canonical-refs-lane-a"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_frontmatter(
        tasks_dir / "WP03-review-prompt-isolation.md",
        {
            "work_package_id": "WP03",
            "title": "Review Prompt Isolation",
            "execution_mode": "code_change",
            "owned_files": ["src/review_target.py"],
        },
        "\n# WP03\n",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id="01KQKV85CANONICAL000000000",
            mission_branch=mission_branch,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP03",),
                    write_scope=("src/**",),
                    predicted_surfaces=("src",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-05-02T09:00:00Z",
            computed_from="test",
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed mission")
    _git(repo, "branch", mission_branch)

    worktree = repo / ".worktrees" / f"{mission_slug}-lane-a"
    _git(repo, "worktree", "add", "-b", lane_branch, str(worktree), mission_branch)
    (worktree / "src").mkdir()
    (worktree / "src" / "review_target.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(worktree, "add", "src/review_target.py")
    _git(worktree, "commit", "-m", "feat(WP03): add review target")
    window_open = _rev_parse(repo, mission_branch)
    submitted_tip = _rev_parse(repo, lane_branch)
    opened = {LANE_HEAD_KEY: window_open, WP_WINDOW_KEY: {"schema_version": 1, "open_sha": window_open}}
    append_events_atomic(
        feature_dir,
        [
            _event("01KQKV85CANON0000000000001", Lane.PLANNED, Lane.CLAIMED, opened),
            _event("01KQKV85CANON0000000000002", Lane.IN_PROGRESS, Lane.FOR_REVIEW, {LANE_HEAD_KEY: submitted_tip}),
        ],
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "status: WP03 claimed and submitted")

    owned_files = wp_owned_files(tasks_dir / "WP03-review-prompt-isolation.md")
    ctx = _resolve_review_context(worktree, repo, mission_slug, "WP03", owned_files)

    reconstructed_wrong_ref = f"kitty/mission-{mission_slug}"
    assert reconstructed_wrong_ref == "kitty/mission-mission-canonical-refs"
    # Re-pin (#7578, IC-05, DIRECTIVE_041): the review base is the WP review range's, not the mission
    # branch. The canonical manifest still names the mission and lane branches; the range is resolved
    # for this WP from its recorded window (the claim's open SHA to the submission's lane_head) and
    # scoped to its owned_files -- never a slug-reconstructed ref.
    review_range = ctx["review_range"]
    assert isinstance(review_range, WpReviewRange)
    assert review_range.wp_id == "WP03" and review_range.owned_pathspecs == ("src/review_target.py",)
    assert review_range.status is RangeStatus.RECORDED
    assert (review_range.base, review_range.tip) == (window_open, submitted_tip)
    assert [commit.subject for commit in review_range.commits] == ["feat(WP03): add review target"]
    assert ctx["mission_branch"] == mission_branch
    assert ctx["base_ref"] == window_open
    assert ctx["base_branch"] == window_open
    assert ctx["commit_count"] == 1
    assert ctx["lane_branch"] == lane_branch
    assert reconstructed_wrong_ref not in {ctx["base_ref"], ctx["lane_branch"], ctx["mission_branch"]}
