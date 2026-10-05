"""#5668 -- ``consolidate --resume`` refuses a commit added to a not-yet-consolidated lane after the interruption.

A real ``spec-kitty consolidate`` over the two-lane approved mission of
:mod:`tests.terminus.post_approval_support` is SIGKILLed right after its first lane
merge advanced the mission branch (the fault hook of
:class:`~tests.terminus.approved_content_support.InterruptedConsolidate`). Review had
approved both lanes; the operator then commits more content to the second lane, which
has not been consolidated yet, and resumes. The claim is rebuilt on ``--resume``, so
the approved bound applies to the resumed run exactly as to a fresh one: refused with
``LANE_MOVED_AFTER_APPROVAL``, the late file not on the target.

Real git, the real CLI in subprocesses, nothing mocked.
"""

from __future__ import annotations

import signal
from pathlib import Path

import pytest

from tests.terminus.approved_content_support import InterruptedConsolidate
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import LATE_PATH, Topology, add_post_approval_commit, build_post_approval_mission
from tests.terminus.canceled_dependency_support import LANE_B

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CODE = "LANE_MOVED_AFTER_APPROVAL"


class _InterruptedPostApproval(InterruptedConsolidate):
    """The post-approval mission, its real ``consolidate`` killed after the first lane merge advanced the mission branch."""

    def __init__(self, tmp_path: Path, topology: Topology) -> None:
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


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_resume_refuses_a_commit_added_to_a_lane_not_yet_consolidated(tmp_path: Path, topology: Topology) -> None:
    run = _InterruptedPostApproval(tmp_path, topology)
    add_post_approval_commit(run.mission, lane=LANE_B)

    rc, flat = run.resume()

    assert rc != 0, f"a commit added after approval must be refused on --resume ({topology}):\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert not blob_present_at(run.mission.repo, run.mission.target_branch, LATE_PATH), "the unreviewed file must not be on the target"
    assert run.mission.rev(run.mission.target_branch) == run.pre_target, "the refusal must not move the target"
