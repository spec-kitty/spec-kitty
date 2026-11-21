"""A coordination Mission whose two approved, independent lanes edit adjacent hunks of one file (#7755, #7754).

``lane-a`` (``WP01``) and ``lane-b`` (``WP02``) are cut by the real allocator
(:func:`allocate_lane_worktree`), each with a real worktree, and every lifecycle
transition runs through the production coordination status shell, so each
``lane_head`` stamp comes from the product. Stock git conflicts on the two edits:
``consolidate`` folds ``lane-a`` into the Mission branch first, then finds
``lane-b`` stale and its in-run auto-rebase stops on the conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status.models import ReviewResult
from tests.terminus.conftest import (
    _STATUS_EVENTS_FILENAME,
    CoordMission,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _git,
    _init_fixture_repo,
    _now_iso,
    _write_meta,
    pin_planning_commit,
)
from tests.terminus.mixed_lane_support import transition

IMPLEMENTER = "stale-sibling-implementer"
#: An independent reviewer (#6715): an approval by the implementer's own identity is refused.
REVIEWER = "stale-sibling-reviewer"
POPUP = "src/components/Popup.vue"
SEED = "<template>\n  <div>\n    <p>title</p>\n    <p>body</p>\n  </div>\n</template>\n"
LANE_A_TEXT = SEED.replace("<p>title</p>", "<p>Title A</p>")
LANE_B_TEXT = SEED.replace("<p>body</p>", "<p>Body B</p>")
#: The operator's resolution of the sibling conflict: both lanes' edits.
RESOLVED_TEXT = SEED.replace("<p>title</p>", "<p>Title A</p>").replace("<p>body</p>", "<p>Body B</p>")


@dataclass(frozen=True)
class StaleSiblingMission:
    mission: CoordMission
    lane_a_branch: str
    lane_b_branch: str
    lane_a_worktree: Path
    lane_b_worktree: Path


def _wp_file(wp: str) -> str:
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - src/**\n---\n# {wp}\n"


def _manifest(mission: CoordMission) -> LanesManifest:
    def _lane(lane_id: str, wp: str) -> ExecutionLane:
        return ExecutionLane(
            lane_id=lane_id,
            wp_ids=(wp,),
            write_scope=("src/**",),
            predicted_surfaces=("ui",),
            depends_on_lanes=(),
            parallel_group=0,
        )

    return LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[_lane("lane-a", "WP01"), _lane("lane-b", "WP02")],
        computed_at=_now_iso(),
        computed_from="stale-sibling-lane-fixture",
    )


def commit_in(worktree: Path, rel_path: str, text: str, message: str) -> None:
    target = worktree / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(worktree, "add", rel_path)
    _git(worktree, "commit", "-qm", message)


def approve(mission: CoordMission, wp: str, *, reference: str) -> None:
    """Hand *wp* to review and approve it through the production shell (stamps ``lane_head``)."""
    transition(mission, wp, "for_review", actor=IMPLEMENTER, subtasks_complete=True)
    transition(mission, wp, "in_review", actor=REVIEWER)
    transition(
        mission,
        wp,
        "approved",
        actor=REVIEWER,
        review_ref=reference,
        review_result=ReviewResult(reviewer=REVIEWER, verdict="approved", reference=reference),
    )


def build_stale_sibling_mission(tmp_path: Path, *, mid8: str = "01M77550", target_branch: str = "main") -> StaleSiblingMission:
    mid8 = mid8.upper()
    slug = f"alpha-{mid8.lower()}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch=target_branch, extra_base_files={POPUP: SEED})
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    write_lanes_json(mission.feature_dir, _manifest(mission))
    pin_planning_commit(mission.repo, mission.feature_dir)
    for wp in ("WP01", "WP02"):
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap stale-sibling mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    manifest = read_lanes_json(mission.feature_dir) or _manifest(mission)

    worktrees: dict[str, tuple[Path, str]] = {}
    for wp, text in (("WP01", LANE_A_TEXT), ("WP02", LANE_B_TEXT)):
        transition(mission, wp, "planned", actor=IMPLEMENTER)
        transition(mission, wp, "claimed", actor=IMPLEMENTER)
        worktree, branch = allocate_lane_worktree(mission.repo, slug, wp, manifest)
        transition(mission, wp, "in_progress", actor=IMPLEMENTER)
        commit_in(worktree, POPUP, text, f"feat({slug}): {wp} edits Popup.vue")
        approve(mission, wp, reference=f"review-{wp}")
        worktrees[wp] = (worktree, branch)
        mission.lane_branches[wp] = branch
    (a_tree, a_branch), (b_tree, b_branch) = worktrees["WP01"], worktrees["WP02"]
    return StaleSiblingMission(mission=mission, lane_a_branch=a_branch, lane_b_branch=b_branch, lane_a_worktree=a_tree, lane_b_worktree=b_tree)
