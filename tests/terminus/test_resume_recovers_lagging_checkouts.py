"""Repro #5571 / #5613 -- ``consolidate --resume`` must recover ANY checkout it advanced that merely lags its own HEAD.

An interrupted consolidate leaves a checkout behind its own HEAD: the mission
branch ref was advanced by a lane merge (``git update-ref``) but the
``reset --hard`` that refreshes the checkout that has the branch checked out never
completed. The lane's files then read as STAGED DELETIONS. Upstream (#5605) recovers
the repository root and the coordination worktree; #5613 extends the same proof to a
worktree that has the mission branch checked out on a LANES-topology mission, stops a
leftover ``index.lock`` refusal from advising "Commit", and gives a lag that carries an
operator edit runnable save-the-edit-first advice.

Real interruptions, no mocking of git and no hand-written deletions. A named fault
hook (``REPRO_5571_POINT``) wraps the production resync seam
(``git.ref_advance._resync_checkouts``) inside the real ``spec-kitty consolidate``
subprocess, i.e. right after the mission-branch ``update-ref`` and before the
checkout's ``reset --hard``:

* ``kill``  -- a real ``os.kill(SIGKILL)`` of the consolidate process (arm 1; the
  killed process leaves its global merge lock behind, which the operator removes as
  the error instructs);
* ``lock``  -- a real ``index.lock`` file makes the real ``reset --hard`` fail
  (arm 2, no kill; the operator removes the lock before resuming).

Where the lag lives: the coordination worktree (arms 1 and 2) or a worktree that has
the mission branch checked out on a LANES-topology mission (arm 3).
"""

from __future__ import annotations

import re
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, _cli_env, build_coord_mission, run_terminus, sha_reachable
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.mixed_lane_support import collapse

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

WPS = ("WP01", "WP02")

#: Remediation advice to "Commit"; the success banner's ``Commit: <sha>`` line is not advice.
ADVISES_COMMIT = re.compile(r"\bCommit\b(?!:)")

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


class Interrupted:
    """A mission whose real ``consolidate`` was interrupted after the first lane merge advanced the mission branch."""

    def __init__(self, tmp_path: Path, arm: str, strategy: str = "merge") -> None:
        self.point, topology = ARMS[arm]
        self.tmp_path = tmp_path
        if topology == "coord":
            self.mission: CoordMission = build_coord_mission(tmp_path, wps=WPS, mid8="01M55713")
            self.lagging = self._coord_worktree()
        else:
            self.mission = build_lanes_mission(tmp_path, wps=WPS, mid8="01M55714")
            self.lagging = tmp_path / "mission-wt"
            git(self.mission.repo, "worktree", "add", "-q", str(self.lagging), self.mission.coord_branch)
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
        self.staged = git_out(self.lagging, "diff", "--cached", "--name-status").splitlines()
        assert any(line.startswith("D") for line in self.staged), f"fixture precondition: the lagging checkout must read as staged deletions, got {self.staged}"

    def _coord_worktree(self) -> Path:
        for line in git_out(self.mission.repo, "worktree", "list").splitlines():
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
            index_lock = Path(git_out(self.lagging, "rev-parse", "--absolute-git-dir")) / "index.lock"
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


def printed_commands(output: str) -> list[str]:
    """The shell commands in the printed guidance bullets, un-wrapped (the console folds long lines at 80 columns, keeping trailing spaces)."""
    bullets: list[str] = []
    in_guidance = False
    for line in output.splitlines():
        if "Resume recovery guidance" in line:
            in_guidance = True
        elif in_guidance and line.lstrip().startswith("\u2022"):
            bullets.append(line.lstrip()[1:].lstrip())
        elif in_guidance and bullets:
            bullets[-1] += line
    return ["git " + bullet.split(": git ", 1)[1].strip() for bullet in bullets if ": git " in bullet]


@pytest.mark.parametrize("arm", list(ARMS))
def test_5571_resume_recovers_a_pure_lag_in_place_and_lands_all_code(tmp_path: Path, arm: str) -> None:
    run = Interrupted(tmp_path, arm)

    rc, flat = run.resume()

    assert rc == 0, f"resume over a pure behind-own-HEAD checkout ({arm}) must recover in place and complete, got rc={rc}\n{flat}"
    assert not ADVISES_COMMIT.search(flat), f"no remediation for a lagging checkout may say 'Commit'\n{flat}"
    run.assert_all_approved_code_landed(flat)


# -- controls on the same fixtures -------------------------------------------


def test_5571_control_a_left_index_lock_refuses_without_advising_commit(tmp_path: Path) -> None:
    """The real ``index.lock`` the interrupted reset left is NOT cleared: resume refuses, naming the lock, never 'Commit'."""
    run = Interrupted(tmp_path, "lock_coord")

    rc, flat = run.resume(clear_index_lock=False)

    assert rc != 0, f"a resume over a live index.lock must refuse\n{flat}"
    assert "index.lock" in flat, flat
    assert not ADVISES_COMMIT.search(flat), f"the lock refusal must not advise 'Commit'\n{flat}"
    assert not sha_reachable(run.mission.repo, next(iter(run.approved.values()))[0], run.mission.target_branch), "nothing may land on a refusal"


@pytest.mark.parametrize("arm", ["kill_mission_worktree"])
def test_5571_control_a_genuine_edit_on_top_of_the_lag_still_refuses_and_is_preserved(tmp_path: Path, arm: str) -> None:
    """Lag PLUS a real user edit is not a provably pure lag: the existing refusal stands and the edit survives."""
    run = Interrupted(tmp_path, arm)
    tracked = git_out(run.lagging, "ls-tree", "-r", "--name-only", run.pre_mission).splitlines()[0]
    (run.lagging / tracked).write_text("genuine user edit\n", encoding="utf-8")

    rc, flat = run.resume()

    assert rc != 0, f"a genuinely dirty checkout must keep refusing\n{flat}"
    assert "Do NOT stage or record" in flat, flat
    save, refresh, reapply = (flat.index(step) for step in ("Save your own edits outside the worktree first", "reset --hard HEAD", "re-apply"))
    assert save < refresh < flat.index("spec-kitty consolidate --resume", refresh) < reapply, f"save, refresh, resume, then re-apply\n{flat}"
    assert not ADVISES_COMMIT.search(flat), f"a lag plus an edit must not be told to Commit\n{flat}"
    assert (run.lagging / tracked).read_text(encoding="utf-8") == "genuine user edit\n", "the user's edit must survive the refusal"
    assert run.mission.rev(run.mission.target_branch) == run.pre_target, "a refusal moves nothing"


def test_5571_control_a_genuinely_dirty_coord_worktree_without_any_lag_refuses_with_the_generic_advice(tmp_path: Path) -> None:
    """No interruption at all: the generic commit/stash/revert advice is still the right (and only) remedy."""
    mission = build_coord_mission(tmp_path, wps=WPS, mid8="01M55715")
    coord = next(Path(line.split()[0]) for line in git_out(mission.repo, "worktree", "list").splitlines() if "coord" in line.split()[0])
    tracked = git_out(coord, "ls-files").splitlines()[0]
    (coord / tracked).write_text("genuine user edit\n", encoding="utf-8")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", "merge", "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode != 0, flat
    assert "Commit, stash, or revert" in flat, flat
    assert (coord / tracked).read_text(encoding="utf-8") == "genuine user edit\n"


@pytest.mark.parametrize("arm", ["kill_mission_worktree"])
def test_5571_control_the_revert_option_the_operator_may_take_by_hand_lands_all_code(tmp_path: Path, arm: str) -> None:
    """The operator who refreshes the lagging checkout to its own HEAD by hand reaches the same landing."""
    run = Interrupted(tmp_path, arm)
    git(run.lagging, "reset", "--hard", "HEAD")

    rc, flat = run.resume()

    assert rc == 0, flat
    run.assert_all_approved_code_landed(flat)


@pytest.mark.parametrize("arm", ["kill_coord", "kill_mission_worktree"])
def test_5571_control_the_advised_save_edit_sequence_then_resume_lands_all_code(tmp_path: Path, arm: str) -> None:
    """Lag + edit: run the commands the CLI PRINTED, verbatim and in the printed order (save, refresh, resume, re-apply)."""
    run = Interrupted(tmp_path, arm)
    tracked = git_out(run.lagging, "ls-tree", "-r", "--name-only", run.pre_mission).splitlines()[0]
    (run.lagging / tracked).write_text("genuine user edit\n", encoding="utf-8")
    deleted = [line.split("\t", 1)[1] for line in run.staged if line.startswith("D")]
    assert deleted, "fixture precondition: the lag deleted lane files"

    run.operator_clears_stale_locks()
    refused = run_terminus(run.mission, ["consolidate", "--resume", "--mission", run.mission.slug, "--yes"], env={"COLUMNS": "4000"})
    assert refused.returncode != 0
    commands = printed_commands(refused.stdout + refused.stderr)
    assert [command.split()[3] for command in commands] == ["diff", "reset", "apply"], f"save, refresh, re-apply\n{refused.stdout}{refused.stderr}"
    save, refresh, reapply = commands

    for command in (save, refresh):
        subprocess.run(command, shell=True, cwd=run.lagging, check=True, capture_output=True, text=True)
    assert all((run.lagging / path).exists() for path in deleted), "every lane file the lag had deleted is back on disk"
    assert git_out(run.lagging, "status", "--porcelain") == "", "the refreshed checkout is clean: the edit lives in the patch"

    result = run_terminus(run.mission, ["consolidate", "--resume", "--mission", run.mission.slug, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, flat
    run.assert_all_approved_code_landed(flat)

    # The patch was saved outside the worktree, so it outlives a worktree the consolidation removed;
    # the advice says to apply it in the checkout that now holds the files in that case.
    where = run.lagging if run.lagging.exists() else run.mission.repo
    subprocess.run(reapply.replace(f"-C {run.lagging} ", f"-C {where} "), shell=True, check=True, capture_output=True, text=True)
    assert (where / tracked).read_text(encoding="utf-8") == "genuine user edit\n", "the saved edit is re-applied after the resume"
