"""Allocator-faithful fixture for the approved-content supersession family (#5571 presence axis).

``WP01`` (``lane-a``) authors content; ``WP02`` (``lane-b``, depending on ``WP01``)
then deletes, renames away or reverts it. Lanes are cut by the REAL
``allocate_lane_worktree`` and every transition runs through the production status
shell, exactly like :mod:`tests.terminus.canceled_dependency_support`; the only
variables are WHAT the later WP does and whether it ends approved, canceled or
still in progress -- so a pass and its twin differ in one fact.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.terminus.canceled_dependency_support import ACTOR, WP02_PATH, _approve, _commit_in, _manifest, _wp_file
from tests.terminus.conftest import (
    CoordMission,
    _cli_env,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _git,
    _git_out,
    _init_fixture_repo,
    _STATUS_EVENTS_FILENAME,
    _write_meta,
    build_coord_mission,
    run_terminus,
    sha_reachable,
)
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.mixed_lane_support import collapse, transition

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


# --------------------------------------------------------------------------- #
# A real consolidate, interrupted where an advanced branch has not refreshed its checkout
# --------------------------------------------------------------------------- #

WPS = ("WP01", "WP02")

#: arm id -> (fault point, topology)
ARMS = {
    "kill_coord": ("kill", "coord"),
    "lock_coord": ("lock", "coord"),
    "kill_mission_worktree": ("kill", "lanes"),
}

_DRIVER = textwrap.dedent(
    """
    import json
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path

    POINT = os.environ["REPRO_5571_POINT"]
    BRANCH = os.environ["REPRO_5571_BRANCH"]
    LOG = Path(os.environ["REPRO_5571_LOG"])

    from specify_cli.git import ref_advance

    _orig = ref_advance._resync_checkouts


    def _hook(checkouts, branch, env, *, context):
        if branch == BRANCH and checkouts and not LOG.exists():
            if POINT == "lock":
                for checkout in checkouts:
                    gitdir = subprocess.run(
                        ["git", "-C", str(checkout), "rev-parse", "--absolute-git-dir"],
                        capture_output=True, text=True, check=True,
                    ).stdout.strip()
                    (Path(gitdir) / "index.lock").write_text("")
            LOG.write_text(json.dumps({"point": POINT, "checkouts": [str(c) for c in checkouts]}))
            if POINT == "kill":
                os.kill(os.getpid(), signal.SIGKILL)
        return _orig(checkouts, branch, env, context=context)


    ref_advance._resync_checkouts = _hook

    from specify_cli import main

    sys.argv[0] = "spec-kitty"
    main()
    """
)


class InterruptedConsolidate:
    """A mission whose real ``consolidate`` was interrupted after the first lane merge advanced the mission branch."""

    def __init__(self, tmp_path: Path, arm: str, strategy: str = "merge", *, mid8: str | None = None) -> None:
        self.point, topology = ARMS[arm]
        self.tmp_path = tmp_path
        if topology == "coord":
            self.mission: CoordMission = build_coord_mission(tmp_path, wps=WPS, mid8=mid8 or "01M55713")
            self.lagging = self._coord_worktree()
        else:
            self.mission = build_lanes_mission(tmp_path, wps=WPS, mid8=mid8 or "01M55714")
            self.lagging = tmp_path / "mission-wt"
            _git(self.mission.repo, "worktree", "add", "-q", str(self.lagging), self.mission.coord_branch)
        self.lagging = self.lagging.resolve()
        self.approved = self.mission.approved_shas_from_lane_tips(WPS)
        self.pre_target = self.mission.rev(self.mission.target_branch)
        self.pre_mission = self.mission.rev(self.mission.coord_branch)
        self.log = tmp_path / "hook_5571.jsonl"
        self.run = self._interrupt(strategy)
        assert self.log.exists(), f"fixture precondition: the fault hook was never reached\n{collapse(self.run.stdout + self.run.stderr)}"
        if self.point == "kill":
            assert self.run.returncode == -signal.SIGKILL, f"fixture precondition: consolidate must be SIGKILLed\n{collapse(self.run.stdout + self.run.stderr)}"
        assert self.mission.rev(self.mission.coord_branch) != self.pre_mission, "fixture precondition: the mission branch ref was advanced"
        assert self.mission.rev(self.mission.target_branch) == self.pre_target, "fixture precondition: the target was not touched yet"
        self.staged = _git_out(self.lagging, "diff", "--cached", "--name-status").splitlines()
        assert any(line.startswith("D") for line in self.staged), f"fixture precondition: the lagging checkout must read as staged deletions, got {self.staged}"

    def _coord_worktree(self) -> Path:
        for line in _git_out(self.mission.repo, "worktree", "list").splitlines():
            if "coord" in line.split()[0]:
                return Path(line.split()[0])
        raise AssertionError("coordination worktree not found")

    def _interrupt(self, strategy: str) -> subprocess.CompletedProcess[str]:
        driver = self.tmp_path / "driver_5571.py"
        driver.write_text(_DRIVER, encoding="utf-8")
        env = _cli_env(self.mission.home)
        env.update(REPRO_5571_POINT=self.point, REPRO_5571_BRANCH=self.mission.coord_branch, REPRO_5571_LOG=str(self.log))
        return subprocess.run(
            [sys.executable, str(driver), "consolidate", "--mission", self.mission.slug, "--strategy", strategy, "--yes"],
            cwd=str(self.mission.repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=240,
        )

    # -- what the operator does ------------------------------------------------

    def operator_clears_stale_locks(self, *, clear_index_lock: bool = True) -> None:
        """A SIGKILLed run cannot release the global merge lock; the CLI tells the operator to remove it by hand."""
        lock = self.mission.repo / ".kittify" / "runtime" / "merge" / "__global_merge__" / "lock"
        if self.point == "kill":
            assert lock.exists(), "fixture precondition: the killed run left its merge lock behind"
        lock.unlink(missing_ok=True)
        if self.point == "lock":
            index_lock = Path(_git_out(self.lagging, "rev-parse", "--absolute-git-dir")) / "index.lock"
            assert index_lock.exists(), "fixture precondition: the fault left a real index.lock"
            if clear_index_lock:
                index_lock.unlink()

    def resume(self, *, clear_index_lock: bool = True) -> tuple[int, str]:
        self.operator_clears_stale_locks(clear_index_lock=clear_index_lock)
        result = run_terminus(self.mission, ["consolidate", "--resume", "--mission", self.mission.slug, "--yes"])
        return result.returncode, collapse(result.stdout + "\n" + result.stderr)

    def assert_all_approved_code_landed(self, flat: str) -> None:
        for wp_id, shas in self.approved.items():
            for sha in shas:
                assert sha_reachable(self.mission.repo, sha, self.mission.target_branch), (
                    f"approved {wp_id} commit {sha[:10]} is NOT reachable from {self.mission.target_branch} after --resume (#5571)\n{flat}"
                )
