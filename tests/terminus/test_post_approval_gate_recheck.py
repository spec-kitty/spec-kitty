"""#5668 -- a commit that reaches an approved lane DURING ``consolidate`` must not land under a verified banner.

The claim-time check (WP02) refuses a lane whose content went past its approval
stamp before the run started. It cannot see a commit added to the lane after the
claim was captured and before the lane is merged into the mission branch: that
commit rides the lane merge to the target and, without a second look at the gate,
the run exits 0 and prints "Reconciliation verified".

Injection mechanism (deterministic, no timing): the consolidation runs as a real
subprocess through the production CLI entry point, started by a tiny launcher
script that wraps ONE phase function, ``executor._phase_merge_lanes`` (the first
phase that merges a lane branch into the mission branch; it runs after
``_phase_gates_and_state`` captured the claim and the pre-mutation snapshot).
The wrapper commits a content file on the lane-a branch from the lane worktree,
delegates to the real phase function, and then prints one marker line stating
whether the injected SHA became an ancestor of the mission branch during the run.
The tests assert that marker, so a commit injected after the lane merge (which
would prove nothing) cannot pass for the injection point this suite needs.

Cells: both merge strategies and both topologies. On a LANES mission the claim
base is the mission branch itself, the case a check anchored on live branch names
passes vacuously. Each cell has a same-fixture positive control: the same launcher
injecting nothing consolidates and prints the banner.

Known gap: no harness drives ``implement`` and the review transitions through the
CLI end to end (see :mod:`tests.terminus.post_approval_support`).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.conftest import CoordMission, _cli_env, blob_present_at, git_rev
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import (
    LATE_CONTENT,
    LATE_PATH,
    Topology,
    WP01_PATH,
    build_post_approval_mission,
    lane_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_TOPOLOGIES: tuple[Topology, ...] = ("lanes", "coord")
_STRATEGIES = ("squash", "merge")
_CODE = "LANE_MOVED_AFTER_APPROVAL"
_BANNER = "Reconciliation verified"
_MARKER = re.compile(r"INJECTED_SHA=([0-9a-f]{40}) ON_MISSION_BRANCH=(True|False)")

# Runs in the subprocess: wrap the first lane-merging phase, then start the real CLI.
_LAUNCHER = """\
import os
import subprocess
import sys

from specify_cli import main
from specify_cli.consolidation import executor

LANE_WORKTREE, LATE_PATH, LATE_CONTENT = sys.argv[1:4]
INJECT = sys.argv[4] == "inject"
REAL = executor._phase_merge_lanes


def _git(*args):
    return subprocess.run(["git", "-C", LANE_WORKTREE, *args], capture_output=True, text=True, check=True).stdout.strip()


def _inject_then_merge(run):
    sha = None
    if INJECT:
        late_file = os.path.join(LANE_WORKTREE, LATE_PATH)
        os.makedirs(os.path.dirname(late_file), exist_ok=True)
        with open(late_file, "w", encoding="utf-8") as handle:
            handle.write(LATE_CONTENT)
        _git("add", LATE_PATH)
        _git("commit", "-qm", "feat: unreviewed change added during consolidate")
        sha = _git("rev-parse", "HEAD")
    REAL(run)
    if sha is not None:
        check = subprocess.run(
            ["git", "-C", str(run.main_repo), "merge-base", "--is-ancestor", sha, run.lanes_manifest.mission_branch],
            capture_output=True,
        )
        print(f"INJECTED_SHA={sha} ON_MISSION_BRANCH={check.returncode == 0}", flush=True)


executor._phase_merge_lanes = _inject_then_merge
sys.argv = ["spec-kitty", *sys.argv[5:]]
main()
"""


def _consolidate_with_injection(mission: CoordMission, strategy: str, *, inject: bool) -> tuple[int, str]:
    launcher = mission.home / "inject_during_consolidate.py"
    launcher.write_text(_LAUNCHER, encoding="utf-8")
    lane_a = lane_worktree(mission, "lane-a")
    args = ["consolidate", "--mission", mission.slug, "--yes", "--strategy", strategy]
    result = subprocess.run(
        [sys.executable, str(launcher), str(lane_a), LATE_PATH, LATE_CONTENT, "inject" if inject else "none", *args],
        cwd=str(mission.repo),
        env=_cli_env(mission.home),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


def _run_tips(mission: CoordMission) -> dict[str, str]:
    """Target, mission and coordination branch tips: every branch a rollback must put back."""
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    refs = {mission.target_branch, mission.coord_branch, manifest.mission_branch}
    return {ref: git_rev(mission.repo, ref) for ref in sorted(refs)}


@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_commit_added_during_the_run_is_refused_at_the_gate_and_rolled_back(tmp_path: Path, topology: Topology, strategy: str) -> None:
    control = build_post_approval_mission(tmp_path / "control", topology)
    rc, flat = _consolidate_with_injection(control, strategy, inject=False)
    assert rc == 0, f"positive control: nothing injected must consolidate ({topology}/{strategy}):\n{flat}"
    assert _BANNER in flat
    assert blob_present_at(control.repo, control.target_branch, WP01_PATH)

    mission = build_post_approval_mission(tmp_path / "late", topology)
    pre = _run_tips(mission)

    rc, flat = _consolidate_with_injection(mission, strategy, inject=True)

    marker = _MARKER.search(flat)
    assert marker is not None, f"the launcher did not report the injection ({topology}/{strategy}):\n{flat}"
    late_sha, on_mission_branch = marker.group(1), marker.group(2)
    assert on_mission_branch == "True", "the injected commit must have been merged into the mission branch before the gate"
    assert rc != 0, f"a commit added during the run must be refused at the gate, got exit 0 ({topology}/{strategy}):\n{flat}"
    assert _CODE in flat, f"expected {_CODE}:\n{flat}"
    assert late_sha[:7] in flat and "WP01" in flat, f"the refusal must name the late commit and WP01:\n{flat}"
    assert _BANNER not in flat
    assert _run_tips(mission) == pre, "the rollback authority must put every moved branch back"
    assert not blob_present_at(mission.repo, mission.target_branch, LATE_PATH), "the unreviewed file must not be on the target"
