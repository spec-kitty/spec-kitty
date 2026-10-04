"""#5570 contract (#5613) -- a coordination branch that moved after landing has a stable code and exit code.

The behaviour itself (the branch delete is a compare-and-swap, the late commit
survives, ``--resume`` projects it) and the real-CLI exit code 75 with the
``COORD_MOVED_AFTER_LANDING`` code are pinned by
``tests/terminus/test_coord_teardown_cas_branch_delete.py`` and
``tests/orchestrator_api/test_mission_branch_delete_cas.py``. This file pins what
automation keys on at the unit seam: the code and the distinct exit code of the
teardown error, both asserted by value, next to the existing message; the early
teardown-gate window that stays a plain exit 1; and the orchestrator-api message.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.consolidation import executor as ex
from specify_cli.git.ref_advance import RefDeleteMismatchError
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.orchestrator_api import commands as orchestrator_commands
from tests.terminus.conftest import _cli_env as cli_env
from tests.terminus.conftest import build_coord_mission
from tests.terminus.test_coord_teardown_cas_branch_delete import _COORD_MOVED_CODE, _COORD_MOVED_EXIT, _flat

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("coordination", [True, False], ids=["coordination-branch", "mission-branch"])
def test_tip_moved_error_carries_the_code_and_exit_code(coordination: bool) -> None:
    mismatch = RefDeleteMismatchError(branch="kitty/mission-x", expected_sha="a" * 40, actual_sha="b" * 40)

    error = ex._tip_moved_teardown_error("kitty/mission-x", mismatch, coordination=coordination)

    assert isinstance(error, ex.CoordinationTeardownError), "existing handlers must still catch it"
    assert error.exit_code == _COORD_MOVED_EXIT
    assert error.error_code == _COORD_MOVED_CODE
    assert str(error).endswith(f" Error code: {_COORD_MOVED_CODE}."), "the code is appended; the message before it is unchanged"
    assert "NOT deleted" in str(error) and "kitty/mission-x" in str(error)


# Lands a real commit on the coordination branch just before the REAL teardown gate runs its
# compare-and-swap, so the tip has moved since the projection captured its window.
_MOVED_BEFORE_GATE_DRIVER = """
import os
import subprocess
import sys
from pathlib import Path

import specify_cli.coordination.teardown as teardown

real_gate = teardown._enforce_projection_teardown_gate


def gate_after_late_commit(repo_root, gate):
    worktree = Path(os.environ["COORD_WORKTREE"])
    (worktree / "kitty-specs" / os.environ["MISSION_SLUG"] / "late-status-emit.md").write_text("late\\n", encoding="utf-8")
    for args in (["add", "-A"], ["-c", "user.name=Late", "-c", "user.email=late@example.com", "commit", "-q", "-m", "late"]):
        subprocess.run(["git", "-C", str(worktree), *args], check=True, capture_output=True)
    return real_gate(repo_root, gate)


teardown._enforce_projection_teardown_gate = gate_after_late_commit

from specify_cli import main

sys.argv = ["spec-kitty", "consolidate", "--mission", os.environ["MISSION_SLUG"], "--yes"]
main()
"""


def test_5637_a_tip_that_moves_before_the_teardown_gate_is_a_rendered_refusal_with_exit_1(tmp_path: Path) -> None:
    """The earlier window (``PROJECTION_TEARDOWN_ABORTED``): rendered like its siblings, exit 1, no traceback."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5637A")
    env = cli_env(mission.home)
    env["COORD_WORKTREE"] = str(mission.repo / ".worktrees" / f"{mission.slug}-coord")
    env["MISSION_SLUG"] = mission.slug

    result = subprocess.run(
        [sys.executable, "-c", _MOVED_BEFORE_GATE_DRIVER], cwd=str(mission.repo), env=env, capture_output=True, text=True, check=False, timeout=180
    )

    combined = _flat(result)
    assert "PROJECTION_TEARDOWN_ABORTED" in combined, combined
    assert result.returncode == 1 and "Traceback" not in combined, combined
    assert _COORD_MOVED_CODE not in combined
    assert mission.rev(mission.coord_branch), "nothing may be torn down: the coordination branch must survive"


def test_orchestrator_api_moved_mission_branch_names_the_code(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    branch = "kitty/mission-orch-moved-01M5570P"
    git("init", "-q", "-b", "main")
    git("-c", "user.name=T", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "seed")
    git("branch", branch)
    approved = git("rev-parse", branch)
    late = git("-c", "user.name=L", "-c", "user.email=l@example.invalid", "commit-tree", git("rev-parse", "main^{tree}"), "-p", branch, "-m", "late")
    git("update-ref", f"refs/heads/{branch}", late)
    manifest = LanesManifest(
        version=1,
        mission_slug="orch-moved-01M5570P",
        mission_id="orch-moved-01M5570P",
        mission_branch=branch,
        target_branch="main",
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )

    with pytest.raises(RuntimeError) as raised:
        orchestrator_commands._delete_mission_branch_at(repo, manifest, approved)

    message = str(raised.value)
    assert message.endswith(f" Error code: {_COORD_MOVED_CODE}.")
    assert f"git log main..{branch}" in message, "the existing message is kept"
    assert git("rev-parse", branch) == late
