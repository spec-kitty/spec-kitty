"""Repro #5570 — teardown must not delete a coordination branch that moved after the gate.

The teardown gate (``_enforce_projection_teardown_gate``) compare-and-swaps the coordination
tip once, then the retrospective is persisted, the coordination worktree is destroyed, and
only then ``_delete_mission_branch`` ran an unconditional ``git branch -D``. A status commit
landing in that window (a concurrent ``agent status emit``) was never projected onto the target
and became unreachable: the branch was deleted over it and the command exited 0.

Expected behaviour: the branch delete is a compare-and-swap at the gated tip. A moved tip
keeps the branch (with the late commit), keeps the coordination marker, and ``consolidate``
exits non-zero naming the branch and the moved SHA.

Driven through the REAL ``spec-kitty consolidate`` CLI in a subprocess. The only seam is a
concurrency injection: a driver wraps ``coordination.teardown._destroy_coordination_worktree``
so that a real commit is made on the coordination branch (from inside its worktree, exactly
where a concurrent status emit would land) immediately before the REAL destroy runs. No other
product code is replaced.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus
from tests.terminus.conftest import _cli_env as cli_env
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LATE_SHA_FILE = "late-commit-sha.txt"

# Runs the real CLI after wrapping ONE seam: the destroy leg first lands a real commit on the
# coordination branch (inside its worktree), then calls the original destroy.
_INJECTION_DRIVER = """
import os
import subprocess
import sys
from pathlib import Path

import specify_cli.coordination.teardown as teardown

real_destroy = teardown._destroy_coordination_worktree


def destroy_after_late_commit(repo_root, mission_slug, mid8):
    worktree = Path(os.environ["COORD_WORKTREE"])
    note = worktree / "kitty-specs" / mission_slug / "late-status-emit.md"
    note.write_text("late status emit\\n", encoding="utf-8")
    def git(*args):
        return subprocess.run(["git", "-C", str(worktree), *args], check=True, capture_output=True, text=True)
    git("add", "-A")
    git("-c", "user.name=Late Emit", "-c", "user.email=late@example.com", "commit", "-q", "-m", "late status emit")
    Path(os.environ["LATE_SHA_FILE"]).write_text(git("rev-parse", "HEAD").stdout.strip(), encoding="utf-8")
    return real_destroy(repo_root, mission_slug, mid8)


teardown._destroy_coordination_worktree = destroy_after_late_commit

from specify_cli import main

sys.argv = ["spec-kitty", "consolidate", "--mission", os.environ["MISSION_SLUG"], "--yes"]
main()
"""


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with Rich's terminal line wrapping collapsed to single spaces."""
    return " ".join((result.stdout + result.stderr).split())


def _coord_worktree(mission: CoordMission) -> Path:
    for line in git_out(mission.repo, "worktree", "list").splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path)
    raise AssertionError("coordination worktree not found")


def _branch_exists(mission: CoordMission, branch: str) -> bool:
    ref = f"refs/heads/{branch}"
    return subprocess.run(["git", "-C", str(mission.repo), "rev-parse", "--verify", ref], capture_output=True, check=False).returncode == 0


def _consolidate_with_late_commit(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    env = cli_env(mission.home)
    env["COORD_WORKTREE"] = str(_coord_worktree(mission))
    env["LATE_SHA_FILE"] = str(mission.repo / _LATE_SHA_FILE)
    env["MISSION_SLUG"] = mission.slug
    return subprocess.run(
        [sys.executable, "-c", _INJECTION_DRIVER],
        cwd=str(mission.repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def test_5570_commit_landing_after_the_gate_survives_and_consolidate_fails_loud(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570A")

    result = _consolidate_with_late_commit(mission)

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    late_sha_file = mission.repo / _LATE_SHA_FILE
    assert late_sha_file.exists(), f"fixture invalid: the injection seam never ran\n{output}"
    late_sha = late_sha_file.read_text(encoding="utf-8").strip()
    assert result.returncode != 0, f"#5570: consolidate exited 0 after deleting a coordination branch that moved past the gate\n{output}"
    assert _branch_exists(mission, mission.coord_branch), f"#5570: the coordination branch was deleted over the late commit\n{output}"
    assert mission.rev(mission.coord_branch) == late_sha, "the late commit must still be the coordination tip"
    combined = _flat(result)
    assert mission.coord_branch in combined, f"the refusal must name the branch\n{output}"
    assert late_sha[:12] in combined, f"the refusal must name the moved tip\n{output}"


def test_5570_unmoved_coordination_branch_is_still_deleted(tmp_path: Path) -> None:
    """Positive control: with no commit in the window the real consolidate still tears down."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5570B")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, f"a clean consolidate must succeed\n{output}"
    assert not _branch_exists(mission, mission.coord_branch), f"an unmoved coordination branch must still be deleted\n{output}"
