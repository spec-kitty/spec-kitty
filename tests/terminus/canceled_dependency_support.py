"""Allocator-faithful fixture for the canceled-dependency scenario (#5569).

``WP02`` depends on ``WP01``. Lane branches are cut by the REAL
``allocate_lane_worktree`` (never a hand-planted merge, never
``plant_canceled_commit``): ``lane-b`` is created from the coordination base and
the allocator's dependency step then merges ``lane-a``'s tip into it, which is a
fast-forward -- so ``WP01``'s commit lands on ``lane-b``'s ``--first-parent``
spine with no merge commit. Every lifecycle transition runs through the
production coord-topology status shell (:func:`tests.terminus.mixed_lane_support.transition`),
so each ``lane_head`` stamp comes from ``probe_lane_head`` and not from a hand
written event.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status.models import ReviewResult
from tests.terminus.conftest import (
    CoordMission,
    _cut_coord_branch,
    _commit_planning_artifacts,
    _finish_coord_mission,
    _git,
    _init_fixture_repo,
    _now_iso,
    _STATUS_EVENTS_FILENAME,
    _write_meta,
    git_rev,
)
from tests.terminus.mixed_lane_support import transition

ACTOR = "canceled-dependency-test"
WP01_PATH = "src/pkg/wp01.py"
WP02_PATH = "src/pkg/wp02.py"
LANE_A = "lane-a"
LANE_B = "lane-b"

Wp01Final = Literal["canceled", "rejected", "approved"]


@dataclass(frozen=True)
class CanceledDependencyMission:
    """The built scenario plus the facts the assertions need."""

    mission: CoordMission
    wp01_sha: str
    lane_a_branch: str
    lane_b_branch: str


def _wp_file(wp: str, *, dependencies: tuple[str, ...]) -> str:
    deps = "[" + ", ".join(dependencies) + "]"
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: {deps}\nsubtasks: []\n---\n# {wp}\n"


def _manifest(mission: CoordMission, *, depends: bool) -> LanesManifest:
    def _lane(lane_id: str, wp: str, deps: tuple[str, ...]) -> ExecutionLane:
        return ExecutionLane(
            lane_id=lane_id,
            wp_ids=(wp,),
            write_scope=("src/pkg",),
            predicted_surfaces=("code",),
            depends_on_lanes=deps,
            parallel_group=0 if not deps else 1,
        )

    return LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[_lane(LANE_A, "WP01", ()), _lane(LANE_B, "WP02", (LANE_A,) if depends else ())],
        computed_at=_now_iso(),
        computed_from="terminus-canceled-dependency-allocator-fixture",
    )


def _commit_in(worktree: Path, rel_path: str, text: str, message: str) -> str:
    target = worktree / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(worktree, "add", rel_path)
    _git(worktree, "commit", "-qm", message)
    return git_rev(worktree, "HEAD")


def _approve(mission: CoordMission, wp: str, *, reference: str) -> None:
    transition(mission, wp, "for_review", actor=ACTOR, subtasks_complete=True)
    transition(mission, wp, "in_review", actor=ACTOR)
    transition(
        mission,
        wp,
        "approved",
        actor=ACTOR,
        review_ref=reference,
        review_result=ReviewResult(reviewer=ACTOR, verdict="approved", reference=reference),
    )


def _reopen_and_finish_wp01(mission: CoordMission, final: Wp01Final) -> None:
    if final == "approved":
        return
    transition(mission, "WP01", "in_progress", actor=ACTOR, review_ref="review-WP01-rejected")
    if final == "canceled":
        transition(mission, "WP01", "canceled", actor=ACTOR, reason_source="operator", reason="operator: scope removed from mission")


def build_canceled_dependency_mission(
    tmp_path: Path,
    *,
    wp01_final: Wp01Final = "canceled",
    depends: bool = True,
    wp02_overwrites_wp01: bool = False,
    approve_wp02: bool = True,
    mid8: str = "01M55690",
    target_branch: str = "main",
) -> CanceledDependencyMission:
    """Build a coordination mission whose lanes were cut by the real allocator.

    Timeline (the governed order): ``WP01`` is implemented and approved on
    ``lane-a``; ``WP02`` is then allocated ``lane-b`` (dependency step
    fast-forwards ``WP01``'s commit onto it); ``WP01`` is later reopened and
    ``wp01_final`` decides whether it is canceled with operator provenance, left
    rejected, or re-approved; ``WP02`` finishes and is approved.
    """
    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch=target_branch)
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = _manifest(mission, depends=depends)
    write_lanes_json(mission.feature_dir, manifest)
    (mission.feature_dir / "tasks" / "WP01-work.md").write_text(_wp_file("WP01", dependencies=()), encoding="utf-8")
    (mission.feature_dir / "tasks" / "WP02-work.md").write_text(_wp_file("WP02", dependencies=("WP01",) if depends else ()), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap canceled-dependency mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    repo = mission.repo
    manifest = read_lanes_json(mission.feature_dir) or manifest

    # Both lanes are allocated up front, at the same coordination tip (the
    # orchestrator's start-implementation shape), so lane-b's base is an ancestor
    # of lane-a's later work.
    lane_a_tree, lane_a_branch = allocate_lane_worktree(repo, slug, "WP01", manifest)
    lane_b_tree, lane_b_branch = allocate_lane_worktree(repo, slug, "WP02", manifest)

    # WP01 on lane-a, approved.
    transition(mission, "WP01", "planned", actor=ACTOR)
    transition(mission, "WP01", "claimed", actor=ACTOR)
    transition(mission, "WP01", "in_progress", actor=ACTOR)
    wp01_sha = _commit_in(lane_a_tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")

    # `implement WP02` re-enters lane-b once WP01 is approved: the REUSE path of
    # the real allocator merges lane-a's tip, which fast-forwards (no --no-ff).
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    lane_b_tree, lane_b_branch = allocate_lane_worktree(repo, slug, "WP02", manifest)
    transition(mission, "WP02", "in_progress", actor=ACTOR)

    _reopen_and_finish_wp01(mission, wp01_final)

    _commit_in(lane_b_tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
    if wp02_overwrites_wp01:
        _commit_in(lane_b_tree, WP01_PATH, "def wp01() -> int:\n    return 'superseded by WP02'\n", f"feat({slug}): WP02 supersedes WP01")
    if approve_wp02:
        _approve(mission, "WP02", reference="review-WP02")

    mission.lane_branches.update({"WP01": lane_a_branch, "WP02": lane_b_branch})
    if wp01_final == "canceled":
        mission.canceled_wps.add("WP01")
    assert lane_a_branch == lane_branch_name(slug, LANE_A, target_branch=target_branch)
    return CanceledDependencyMission(mission=mission, wp01_sha=wp01_sha, lane_a_branch=lane_a_branch, lane_b_branch=lane_b_branch)


def first_parent_shas(repo: Path, base: str, tip: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "rev-list", "--first-parent", f"{base}..{tip}"], capture_output=True, text=True, check=True).stdout
    return out.split()


def merge_commits(repo: Path, base: str, tip: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "rev-list", "--merges", f"{base}..{tip}"], capture_output=True, text=True, check=True).stdout
    return out.split()


def strip_lane_head_stamps(mission: CoordMission, wp_id: str) -> None:
    """Make *wp_id* a legacy, unstamped WP: drop ``policy_metadata.lane_head`` from its events.

    Rewrites every copy of the mission's event log (coord worktree and primary)
    and commits it where it lives, so the verifier reads an attribution-less
    history -- the ``no_stamp`` shape of a mission created before lane-head stamps.
    """
    import json

    for log in mission.repo.rglob("status.events.jsonl"):
        if ".git" in log.parts:
            continue
        rewritten: list[str] = []
        for line in log.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("wp_id") == wp_id:
                metadata = event.get("policy_metadata") or {}
                metadata.pop("lane_head", None)
                event["policy_metadata"] = metadata or None
            rewritten.append(json.dumps(event, sort_keys=True))
        log.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        _git(log.parent, "add", str(log))
        _git(log.parent, "commit", "-qm", f"test: strip lane_head stamps of {wp_id}", "--allow-empty")
