"""#5287 (R1): the status board on a remote-only coordination branch names how to recover.

A checkout with no local head for the coordination branch (a fresh clone, a CI
checkout, a pruned branch) used to fail the board with a raw
``STATUS_SURFACE_REF_UNREADABLE`` and no next step. The door now refuses with the
typed ``STATUS_SURFACE_REF_REMOTE_ONLY`` carrying the canonical remedy; running
its local-branch step unblocks the board.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    LANES_WITH_COORD,
    SLUG,
    UNMATERIALIZED,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Deliberately not ``origin``: the remedy must name the remote that owns the branch.
REMOTE = "coord-remote"


def make_coordination_branch_remote_only(repo: Path, base: Path) -> None:
    """Push the coordination branch to a bare remote, then delete the local head (tracking ref kept)."""
    bare = base / "coord-remote.git"
    git(base, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", REMOTE, str(bare))
    git(repo, "push", "-q", REMOTE, COORD_BRANCH)
    git(repo, "fetch", "-q", REMOTE, COORD_BRANCH)
    git(repo, "branch", "-D", COORD_BRANCH)


def _status(repo: Path) -> tuple[int, str]:
    from specify_cli.cli.commands.agent.tasks import app

    result = CliRunner().invoke(app, ["status", "--mission", SLUG, "--json"])
    return result.exit_code, result.output


def test_status_board_on_a_remote_only_coordination_branch_names_the_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    make_coordination_branch_remote_only(mission.repo, tmp_path)
    monkeypatch.chdir(mission.repo)

    exit_code, output = _status(mission.repo)

    assert exit_code != 0, output
    message = json.dumps(json.loads(output[output.index("{") :]))
    assert "STATUS_SURFACE_REF_REMOTE_ONLY" in message
    assert f"branch {COORD_BRANCH} refs/remotes/{REMOTE}/{COORD_BRANCH}" in message
    assert f"spec-kitty doctor coordination --mission {SLUG} --fix" in message
    assert "origin" not in message


def test_running_the_printed_branch_step_unblocks_the_status_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the same fixture (SC-002): the remedy's local-branch step is enough to read."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    make_coordination_branch_remote_only(mission.repo, tmp_path)
    monkeypatch.chdir(mission.repo)

    git(mission.repo, "branch", COORD_BRANCH, f"{REMOTE}/{COORD_BRANCH}")
    exit_code, output = _status(mission.repo)

    assert exit_code == 0, output
