"""#5571 -- committing the staged deletions of an interrupted consolidate must not ship a mission without its code.

A REAL ``spec-kitty consolidate`` is SIGKILLed in the window #1826 describes: the
mission (coordination) branch ref has been advanced by the first lane merge, but
the ``git reset --hard`` that refreshes the coordination worktree never ran. The
worktree then sits behind its own HEAD and the lane's files read as STAGED
DELETIONS. The operator follows the advice the CLI used to print ("Commit ...")
with a plain ``git commit`` in the coordination worktree, which records a revert
of the lane's code on the mission branch. ``_lane_already_integrated`` now sees
the lane as an ancestor, so ``consolidate --resume`` used to skip it, marked every
WP ``done`` and exited 0 with the code missing.

The approved-content presence axis is the backstop: the resumed run must refuse
with ``APPROVED_CONTENT_MISSING`` naming the WP whose content is gone, mark no WP
``done`` and restore the target to the pre-mutation snapshot.

Nothing is mocked and no deletion is hand-written (no ``git rm``): the kill is a
``git`` shim on the CLI's ``PATH`` that SIGKILLs the calling ``spec-kitty`` process
exactly when it is about to run the coordination worktree's ``reset --hard``; the
staged deletions are what that kill leaves behind. Each negative has a same-fixture
positive control (the "revert" remedy instead of "commit").
"""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.git_probes import _lane_already_integrated
from specify_cli.status.reducer import materialize_snapshot
from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.mixed_lane_support import collapse

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

STRATEGIES = ("squash", "merge")
ERROR_CODE = "APPROVED_CONTENT_MISSING"
WP_PATHS = {"WP01": "src/pkg/wp01.py", "WP02": "src/pkg/wp02.py"}

_SHIM = """#!/bin/sh
# Test fault injection: SIGKILL the calling spec-kitty process when it is about to
# resync the coordination worktree, otherwise behave exactly like git.
if [ "$(pwd -P)" = "{coord_wt}" ] && [ "$1" = "reset" ] && [ "$2" = "--hard" ] && [ "$3" = "{coord_branch}" ]; then
    kill -9 "$PPID"
    exit 137
fi
exec "{real_git}" "$@"
"""


def coord_worktree(mission: CoordMission) -> Path:
    for line in git_out(mission.repo, "worktree", "list").splitlines():
        path = line.split()[0]
        if "coord" in path:
            return Path(path).resolve()
    raise AssertionError("coordination worktree not found")


def killing_git_env(tmp_path: Path, mission: CoordMission, coord_wt: Path) -> dict[str, str]:
    """``PATH`` overlay whose ``git`` kills the CLI at the coordination-worktree resync."""
    real_git = shutil.which("git")
    assert real_git is not None, "git must be on PATH"
    shim_dir = tmp_path / "kill-shim"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(_SHIM.format(coord_wt=coord_wt, coord_branch=mission.coord_branch, real_git=real_git), encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    return {"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}


class Interrupted:
    """A mission whose real ``consolidate`` was killed mid-lane-merge, plus the snapshot to compare against."""

    def __init__(self, tmp_path: Path, strategy: str, mid8: str, wps: tuple[str, ...] = ("WP01", "WP02")) -> None:
        self.strategy = strategy
        self.mission = build_coord_mission(tmp_path, wps=wps, mid8=mid8)
        self.coord_wt = coord_worktree(self.mission)
        self.pre_target = self.mission.rev(self.mission.target_branch)
        self.pre_coord = self.mission.rev(self.mission.coord_branch)
        env = killing_git_env(tmp_path, self.mission, self.coord_wt)
        killed = run_terminus(self.mission, ["consolidate", "--mission", self.mission.slug, "--strategy", strategy, "--yes"], env=env)
        assert killed.returncode == -signal.SIGKILL, f"fixture precondition: the consolidate run must be SIGKILLed.\n{collapse(killed.stdout + killed.stderr)}"
        assert self.mission.rev(self.mission.coord_branch) != self.pre_coord, "fixture precondition: the mission branch ref was advanced before the kill"
        assert self.mission.rev(self.mission.target_branch) == self.pre_target, "fixture precondition: the target was not touched yet"
        self.staged = git_out(self.coord_wt, "diff", "--cached", "--name-status").splitlines()
        assert any(line.startswith("D") for line in self.staged), f"fixture precondition: the kill must leave staged deletions, got {self.staged}"

    def operator_commits_staged_deletions(self) -> None:
        """The advice the CLI used to print: record what ``git status`` shows."""
        git(self.coord_wt, "commit", "-qm", "operator: commit the staged changes")

    def operator_reverts_staged_deletions(self) -> None:
        """The correct remedy: discard the phantom staged deletions."""
        git(self.coord_wt, "reset", "--hard", "HEAD")

    def operator_clears_stale_lock(self) -> None:
        """A SIGKILLed run cannot release the global merge lock; the CLI tells the operator to remove it by hand."""
        lock = self.mission.repo / ".kittify" / "runtime" / "merge" / "__global_merge__" / "lock"
        assert lock.exists(), "fixture precondition: the killed run left its merge lock behind"
        lock.unlink()

    def resume(self) -> tuple[int, str]:
        self.operator_clears_stale_lock()
        result = run_terminus(self.mission, ["consolidate", "--resume", "--mission", self.mission.slug, "--yes"])
        return result.returncode, collapse(result.stdout + "\n" + result.stderr)

    @property
    def deleted_paths(self) -> list[str]:
        return [line.split("\t", 1)[1] for line in self.staged if line.startswith("D")]


def wp_lanes(mission: CoordMission, ref: str) -> dict[str, str]:
    """Each WP's lane in the status log as of *ref* (no files are written)."""
    events = git_out(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl")
    feature_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"snap-{mission.mid8}-{abs(hash(ref))}"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.events.jsonl").write_text(events, encoding="utf-8")
    snapshot = materialize_snapshot(feature_dir)
    shutil.rmtree(feature_dir, ignore_errors=True)
    return {wp: str(state["lane"]) for wp, state in snapshot.work_packages.items()}


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_committed_staged_deletions_make_resume_refuse(tmp_path: Path, strategy: str) -> None:
    run = Interrupted(tmp_path, strategy, mid8="01M55710")
    mission = run.mission
    run.operator_commits_staged_deletions()
    assert blob_present_at(mission.repo, mission.coord_branch, WP_PATHS["WP01"]) is False, "fixture precondition: the committed deletions removed WP01's code"

    rc, flat = run.resume()

    assert rc != 0, f"resume after the operator committed the staged deletions must refuse, got exit 0 ({strategy}):\n{flat}"
    assert ERROR_CODE in flat, f"expected {ERROR_CODE} in the refusal:\n{flat}"
    assert "WP01" in flat, f"the refusal must name the WP whose content is missing:\n{flat}"
    assert mission.rev(mission.target_branch) == run.pre_target, "target must be restored to the pre-mutation snapshot"
    assert not blob_present_at(mission.repo, mission.target_branch, WP_PATHS["WP01"])
    for ref in (mission.target_branch, mission.coord_branch):
        lanes = wp_lanes(mission, ref)
        assert "done" not in lanes.values(), f"no WP may be marked done on {ref}: {lanes}"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_control_reverting_the_staged_deletions_lands_all_code(tmp_path: Path, strategy: str) -> None:
    """Same fixture and interruption; the operator discards the staged deletions instead of committing them."""
    run = Interrupted(tmp_path, strategy, mid8="01M55711")
    mission = run.mission
    run.operator_reverts_staged_deletions()

    rc, flat = run.resume()

    assert rc == 0, f"resume after discarding the staged deletions must land the mission ({strategy}):\n{flat}"
    for wp, path in WP_PATHS.items():
        assert blob_present_at(mission.repo, mission.target_branch, path), f"{wp}'s approved code must be on the target"


def test_5571_the_ancestry_skip_is_what_hides_the_missing_content(tmp_path: Path) -> None:
    """The fix is the presence axis, not a change to the ancestry skip: after the committed revert the lane still reads as integrated."""
    run = Interrupted(tmp_path, "merge", mid8="01M55712")
    mission = run.mission
    run.operator_commits_staged_deletions()

    assert _lane_already_integrated(mission.repo, mission.lane_branch("WP01"), mission.coord_branch), (
        "the committed revert leaves lane-a an ancestor of the mission branch, so the ancestry skip still fires"
    )
    assert subprocess.run(["git", "-C", str(mission.repo), "cat-file", "-e", f"{mission.coord_branch}:{WP_PATHS['WP01']}"], check=False).returncode != 0
