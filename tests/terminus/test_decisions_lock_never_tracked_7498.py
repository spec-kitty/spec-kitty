"""#7498 gap 1: the decisions runtime lock on a coordination topology, end to end.

Drives the REAL ``spec-kitty`` CLI (``run_terminus``, a subprocess with an isolated
``HOME``) against a real coordination Mission: a ``decision open`` takes the decisions
lock on the coordination surface, then a ``spec-commit`` that names the lock is refused.
Afterwards no branch tracks the lock (the target branch and the coordination branch)
and neither the repository root checkout nor the coordination worktree lists it as an
untracked change.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LOCK_SUFFIX = "decisions/index.json.lock"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _checkouts(repo: Path) -> list[Path]:
    porcelain = _git(repo, "worktree", "list", "--porcelain")
    return [Path(line.removeprefix("worktree ")) for line in porcelain.splitlines() if line.startswith("worktree ")]


def test_decision_lock_is_never_tracked_or_dirt_on_a_coordination_topology(coord_mission: CoordMission) -> None:
    mission = coord_mission
    opened = run_terminus(
        mission,
        [
            "agent",
            "decision",
            "open",
            "--mission",
            mission.slug,
            "--flow",
            "specify",
            "--slot-key",
            "specify.scope.lock-pin",
            "--input-key",
            "lock_pin",
            "--question",
            "Pin the lock?",
        ],
    )
    assert opened.returncode == 0, opened.stdout + opened.stderr

    locks = [path for checkout in _checkouts(mission.repo) for path in checkout.rglob("index.json.lock") if ".git" not in path.parts]
    assert locks, "the decision write must have taken (and kept) the runtime lock on disk"

    # Even with the operator's protected-branch escape hatch set, the lock is refused:
    # branch protection is not what keeps it out of history.
    refused = run_terminus(
        mission,
        ["spec-commit", "--mission", mission.slug, "-m", "try the lock", str(locks[0])],
        env={"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS": "1"},
    )
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "runtime lock" in refused.stdout + refused.stderr

    for branch in (mission.target_branch, mission.coord_branch):
        tracked = _git(mission.repo, "ls-tree", "-r", "--name-only", branch)
        assert _LOCK_SUFFIX not in tracked, branch
    for checkout in _checkouts(mission.repo):
        assert _LOCK_SUFFIX not in _git(checkout, "status", "--porcelain=v1", "--untracked-files=all"), checkout
