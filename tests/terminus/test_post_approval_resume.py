"""#5668 -- ``consolidate --resume`` refuses a commit added to a not-yet-consolidated lane after the interruption.

A real ``spec-kitty consolidate`` over the two-lane approved mission of
:mod:`tests.terminus.post_approval_support` is SIGKILLed right after its first lane
merge advanced the mission branch (the fault hook of
:class:`~tests.terminus.approved_content_support.InterruptedConsolidate`). Review had
approved both lanes; the operator then commits more content to the second lane, which
has not been consolidated yet, and resumes. The claim is rebuilt on ``--resume``, so
the approved bound applies to the resumed run exactly as to a fresh one: refused with
``LANE_MOVED_AFTER_APPROVAL``, the late file not on the target.

A second case closes the interruption window between the lane merge and the gate: the
content commit lands on the FIRST lane before that lane is merged (injected by wrapping
``executor._phase_merge_lanes`` in the killed run's driver), the lane merge carries it
into the mission branch, and the run is SIGKILLed right after. On ``--resume`` the
mission branch already holds the late commit, which an anchor taken from the live
mission branch would exempt; it must still be refused.

Real git, the real CLI in subprocesses, nothing mocked.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.terminus.approved_content_support import _DRIVER, InterruptedConsolidate
from tests.terminus.conftest import _cli_env
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import LATE_CONTENT, LATE_PATH, Topology, add_post_approval_commit, build_post_approval_mission, lane_worktree
from tests.terminus.canceled_dependency_support import LANE_B

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "LANE_MOVED_AFTER_APPROVAL"


# Prepended to the kill driver: commit the late file on lane-a, then run the real lane-merging phase.
_INJECT_BEFORE_LANE_MERGE = textwrap.dedent(
    """
    import os
    import subprocess

    from specify_cli.consolidation import executor

    _LANE_A, _LATE_PATH, _LATE_CONTENT = os.environ["LATE_LANE"], os.environ["LATE_PATH"], os.environ["LATE_CONTENT"]
    _REAL_MERGE_LANES = executor._phase_merge_lanes


    def _inject_then_merge(run):
        target = os.path.join(_LANE_A, _LATE_PATH)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(_LATE_CONTENT)
        for args in (["add", _LATE_PATH], ["commit", "-qm", "feat: unreviewed change added before the lane merge"]):
            subprocess.run(["git", "-C", _LANE_A, *args], capture_output=True, text=True, check=True)
        _REAL_MERGE_LANES(run)


    executor._phase_merge_lanes = _inject_then_merge
    """
)


class _InterruptedPostApproval(InterruptedConsolidate):
    """The post-approval mission, its real ``consolidate`` killed after the first lane merge advanced the mission branch.

    With ``inject_before_lane_merge`` the killed run also commits :data:`LATE_PATH` on lane-a
    right before that lane is merged, so the lane merge carries the late commit into the mission branch.
    """

    def __init__(self, tmp_path: Path, topology: Topology, *, inject_before_lane_merge: bool = False) -> None:
        self.inject_before_lane_merge = inject_before_lane_merge
        self.point = "kill"
        self.tmp_path = tmp_path
        self.mission = build_post_approval_mission(tmp_path, topology)
        if topology == "coord":
            self.lagging = self._coord_worktree()
        else:
            self.lagging = tmp_path / "mission-wt"
            git(self.mission.repo, "worktree", "add", "-q", str(self.lagging), self.mission.coord_branch)
        self.lagging = self.lagging.resolve()
        self.pre_target = self.mission.rev(self.mission.target_branch)
        self.pre_mission = self.mission.rev(self.mission.coord_branch)
        self.log = tmp_path / "hook_5571.jsonl"
        self.run = self._interrupt("merge")
        assert self.log.exists(), f"fixture precondition: the fault hook was never reached\n{collapse(self.run.stdout + self.run.stderr)}"
        assert self.run.returncode == -signal.SIGKILL, f"fixture precondition: consolidate must be SIGKILLed\n{collapse(self.run.stdout + self.run.stderr)}"
        assert self.mission.rev(self.mission.coord_branch) != self.pre_mission, "fixture precondition: the first lane merge advanced the mission branch"

    def _interrupt(self, strategy: str) -> subprocess.CompletedProcess[str]:
        driver = self.tmp_path / "driver_5571.py"
        driver.write_text((_INJECT_BEFORE_LANE_MERGE if self.inject_before_lane_merge else "") + _DRIVER, encoding="utf-8")
        env = _cli_env(self.mission.home)
        env.update(REPRO_5571_POINT=self.point, REPRO_5571_BRANCH=self.mission.coord_branch, REPRO_5571_LOG=str(self.log))
        env.update(LATE_LANE=str(lane_worktree(self.mission, "lane-a")), LATE_PATH=LATE_PATH, LATE_CONTENT=LATE_CONTENT)
        return subprocess.run(
            [sys.executable, str(driver), "consolidate", "--mission", self.mission.slug, "--strategy", strategy, "--yes"],
            cwd=str(self.mission.repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=240,
        )


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_resume_refuses_a_commit_added_to_a_lane_not_yet_consolidated(tmp_path: Path, topology: Topology) -> None:
    run = _InterruptedPostApproval(tmp_path, topology)
    add_post_approval_commit(run.mission, lane=LANE_B)

    rc, flat = run.resume()

    assert rc != 0, f"a commit added after approval must be refused on --resume ({topology}):\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert f"That attempt already moved {run.mission.coord_branch}." in flat, f"the killed attempt moved the mission branch, so the refusal must say so:\n{flat}"
    assert "will report" in flat and "as NOT restored" in flat, f"the killed attempt recorded no post tip, so the refusal must not promise a restore:\n{flat}"
    assert not blob_present_at(run.mission.repo, run.mission.target_branch, LATE_PATH), "the unreviewed file must not be on the target"
    assert run.mission.rev(run.mission.target_branch) == run.pre_target, "the refusal must not move the target"


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_resume_refuses_a_commit_the_interrupted_lane_merge_already_carried_into_the_mission_branch(tmp_path: Path, topology: Topology) -> None:
    run = _InterruptedPostApproval(tmp_path, topology, inject_before_lane_merge=True)
    assert blob_present_at(run.mission.repo, run.mission.coord_branch, LATE_PATH), "fixture precondition: the lane merge carried the late file"

    rc, flat = run.resume()

    assert rc != 0, f"a commit the interrupted run merged after approval must be refused on --resume ({topology}):\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert "Reconciliation verified" not in flat
    assert not blob_present_at(run.mission.repo, run.mission.target_branch, LATE_PATH), "the unreviewed file must not be on the target"
    assert run.mission.rev(run.mission.target_branch) == run.pre_target, "the refusal must not move the target"
