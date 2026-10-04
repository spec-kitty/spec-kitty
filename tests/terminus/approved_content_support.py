"""Allocator-faithful fixture for the approved-content supersession family (#5571 presence axis).

``WP01`` (``lane-a``) authors content; ``WP02`` (``lane-b``, depending on ``WP01``)
then deletes, renames away or reverts it. Lanes are cut by the REAL
``allocate_lane_worktree`` and every transition runs through the production status
shell, exactly like :mod:`tests.terminus.canceled_dependency_support`; the only
variables are WHAT the later WP does and whether it ends approved, canceled or
still in progress -- so a pass and its twin differ in one fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.terminus.canceled_dependency_support import ACTOR, WP02_PATH, _approve, _commit_in, _manifest, _wp_file
from tests.terminus.conftest import (
    CoordMission,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _git,
    _init_fixture_repo,
    _STATUS_EVENTS_FILENAME,
    _write_meta,
)
from tests.terminus.mixed_lane_support import transition

Edit = Literal["delete", "rename", "revert", "modify", "none"]
Wp02Final = Literal["approved", "canceled", "in_progress"]

ADDED_PATH = "src/pkg/added.py"
RENAMED_PATH = "src/pkg/renamed.py"
SHARED_PATH = "src/pkg/shared.py"
SHARED_V0 = "def shared() -> int:\n    return 0\n"
SHARED_V1 = "def shared() -> int:\n    return 1\n"
ADDED_BODY = "def added() -> int:\n    return 1\n"


@dataclass(frozen=True)
class DependentEditMission:
    """The built scenario plus the facts the assertions need."""

    mission: CoordMission
    edit: Edit
    lane_a_branch: str
    lane_b_branch: str


def _wp01_work(lane_a_tree: Path, edit: Edit, slug: str) -> None:
    """WP01's authored change: add a file, or (for the revert and modify arms) modify a pre-existing one."""
    if edit in ("revert", "modify"):
        _commit_in(lane_a_tree, SHARED_PATH, SHARED_V1, f"feat({slug}): WP01 changes {SHARED_PATH}")
    else:
        _commit_in(lane_a_tree, ADDED_PATH, ADDED_BODY, f"feat({slug}): WP01 adds {ADDED_PATH}")


def _wp02_work(lane_b_tree: Path, edit: Edit, slug: str) -> None:
    """WP02's later change to what WP01 authored (``modify`` and ``none``: its own file, WP01's work untouched)."""
    message = f"feat({slug}): WP02 {edit}"
    if edit == "delete":
        _git(lane_b_tree, "rm", "-q", ADDED_PATH)
        _git(lane_b_tree, "commit", "-qm", message)
    elif edit == "rename":
        _git(lane_b_tree, "mv", ADDED_PATH, RENAMED_PATH)
        _git(lane_b_tree, "commit", "-qm", message)
    elif edit == "revert":
        _commit_in(lane_b_tree, SHARED_PATH, SHARED_V0, message)
    else:
        _commit_in(lane_b_tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", message)


def build_dependent_edit_mission(
    tmp_path: Path,
    *,
    edit: Edit,
    wp02_final: Wp02Final = "approved",
    mid8: str = "01M55710",
    target_branch: str = "main",
) -> DependentEditMission:
    """Coordination mission: approved ``WP01`` authors, ``WP02`` (depends on it) then *edit*s it."""
    mid8 = mid8.upper()
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch=target_branch, extra_base_files={SHARED_PATH: SHARED_V0})
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = _manifest(mission, depends=True)
    write_lanes_json(mission.feature_dir, manifest)
    (mission.feature_dir / "tasks" / "WP01-work.md").write_text(_wp_file("WP01", dependencies=()), encoding="utf-8")
    (mission.feature_dir / "tasks" / "WP02-work.md").write_text(_wp_file("WP02", dependencies=("WP01",)), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap dependent-edit mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    repo = mission.repo
    manifest = read_lanes_json(mission.feature_dir) or manifest

    lane_a_tree, lane_a_branch = allocate_lane_worktree(repo, slug, "WP01", manifest)
    _lane_b_tree, lane_b_branch = allocate_lane_worktree(repo, slug, "WP02", manifest)

    transition(mission, "WP01", "planned", actor=ACTOR)
    transition(mission, "WP01", "claimed", actor=ACTOR)
    transition(mission, "WP01", "in_progress", actor=ACTOR)
    _wp01_work(lane_a_tree, edit, slug)
    _approve(mission, "WP01", reference="review-WP01")

    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    lane_b_tree, lane_b_branch = allocate_lane_worktree(repo, slug, "WP02", manifest)  # REUSE path: fast-forwards lane-a's work in
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    _wp02_work(lane_b_tree, edit, slug)
    if wp02_final == "approved":
        _approve(mission, "WP02", reference="review-WP02")
    elif wp02_final == "canceled":
        transition(mission, "WP02", "canceled", actor=ACTOR, reason_source="operator", reason="operator: scope removed from mission")
        mission.canceled_wps.add("WP02")

    mission.lane_branches.update({"WP01": lane_a_branch, "WP02": lane_b_branch})
    return DependentEditMission(mission=mission, edit=edit, lane_a_branch=lane_a_branch, lane_b_branch=lane_b_branch)
