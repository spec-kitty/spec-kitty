"""Lane cleanup is the last step of ``spec-kitty consolidate`` and reports, never raises (S5, #7280).

FR-031: the coordination triple comes down first, then each lane is ``removed``, ``kept`` or
``retained_by_policy``, then the consolidation record is cleared. FR-032 / NFR-004 / SC-005: a lane
the remover cannot remove after a verified landing is reported with its code and remedy, the record
is cleared and the run exits 0. FR-033: retention is named "retained by policy", distinct from
"kept". FR-034: a lane-tip ref outlives a lane branch that is already missing.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git. The post-gate steps that
model a race (a lane dirtied after the preflight, a lane branch deleted by hand) are injected with a
small driver that patches one executor seam and then runs the CLI unchanged (the same technique as
``tests/terminus/rollback_harness.run_hard_killed``). The injected dirt is an untracked file, which
behaves the same on Linux and Windows (NFR-008).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from tests.terminus.conftest import _SRC, CoordMission, blob_present_at, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_LANE_TIP_PREFIX = "refs/spec-kitty/lane-tip/"
_ON_LINUX = sys.platform.startswith("linux")

# The driver every injected run uses: ``PATCH`` (a Python snippet) runs after ``specify_cli`` is
# importable and before the CLI starts; the CLI itself is unchanged.
_DRIVER = """
import os, subprocess, sys
from pathlib import Path
import specify_cli
{patch}
sys.argv = ["spec-kitty", *sys.argv[1:]]
specify_cli.main()
"""


# -- shared helpers (also imported by the module and orchestrator-api test files) -----------------


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def ref_exists(repo: Path, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", ref], check=False).returncode == 0


def flat(result: subprocess.CompletedProcess[str]) -> str:
    return " ".join((result.stdout + result.stderr).split())


def output(result: subprocess.CompletedProcess[str]) -> str:
    return f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def lane_worktree(mission: CoordMission, lane_id: str) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-{lane_id}"


def lane_branch(mission: CoordMission, lane_id: str) -> str:
    return f"kitty/mission-{mission.slug}-{lane_id}"


def add_lane_worktrees(mission: CoordMission, lane_ids: Sequence[str]) -> None:
    """Check each lane branch out in its production worktree path (``.worktrees/<slug>-<lane>``)."""
    for lane_id in lane_ids:
        git(mission.repo, "worktree", "add", "-q", str(lane_worktree(mission, lane_id)), lane_branch(mission, lane_id))


def record_lane_tip(mission: CoordMission, lane_id: str) -> str:
    branch = lane_branch(mission, lane_id)
    sha = mission.rev(branch)
    git(mission.repo, "update-ref", f"{_LANE_TIP_PREFIX}{branch}", sha)
    return sha


def state_files(mission: CoordMission) -> list[Path]:
    return sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))


def run_patched(mission: CoordMission, args: Sequence[str], patch: str) -> subprocess.CompletedProcess[str]:
    """Run the REAL CLI like :func:`run_terminus`, with ``patch`` applied first."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC)
    env["HOME"] = str(mission.home)
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env.pop("VIRTUAL_ENV", None)
    env.pop("SPEC_KITTY_ORIGIN_CHECK", None)
    return subprocess.run(
        [sys.executable, "-c", _DRIVER.format(patch=patch), *args],
        cwd=str(mission.repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def after_gate(action: str) -> str:
    """A patch that runs ``action`` (Python, ``run`` in scope) right after the post-gate push phase."""
    indented = "\n".join(f"    {line}" for line in action.splitlines())
    return f"""
from specify_cli.consolidation import executor as _executor
_original_push = _executor._phase_push
def _phase_push(run):
    _original_push(run)
{indented}
_executor._phase_push = _phase_push
"""


def consolidate_args(mission: CoordMission, *extra: str) -> list[str]:
    return ["consolidate", "--mission", mission.slug, "--yes", *extra]


def lane_cleanup_block(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The lines of the "Lane cleanup" block, whitespace-collapsed (empty when it is absent)."""
    lines = result.stdout.splitlines()
    try:
        start = next(idx for idx, line in enumerate(lines) if line.strip() == "Lane cleanup")
    except StopIteration:
        return []
    block: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("    ") and not line.startswith("  "):
            break
        if not line.strip():
            break
        block.append(" ".join(line.split()))
    return block


def outcome_line(block: Sequence[str], lane_id: str) -> str:
    matches = [line for line in block if f" {lane_id} " in f" {line} "]
    assert matches, f"no lane cleanup line for {lane_id}: {block}"
    return matches[0]


# -- fixtures ------------------------------------------------------------------------------------


def _three_lane_mission(tmp_path: Path, mid8: str) -> CoordMission:
    return build_coord_mission(tmp_path, wps=("WP01", "WP02", "WP03"), mid8=mid8)


@pytest.fixture(scope="module")
def dirtied_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[CoordMission, subprocess.CompletedProcess[str]]:
    """lane-a and lane-b have worktrees; lane-b gains an untracked file AFTER the preflight and the gate."""
    mission = _three_lane_mission(tmp_path_factory.mktemp("dirtied"), "01M7280A")
    add_lane_worktrees(mission, ("lane-a", "lane-b"))
    dirt = lane_worktree(mission, "lane-b") / "operator-notes.txt"
    result = run_patched(mission, consolidate_args(mission), after_gate(f"Path({str(dirt)!r}).write_text('only copy\\n', encoding='utf-8')"))
    return mission, result


def test_dirtied_lane_after_preflight_kept_exit_0_record_cleared(dirtied_run: tuple[CoordMission, subprocess.CompletedProcess[str]]) -> None:
    mission, result = dirtied_run
    out = output(result)

    assert result.returncode == 0, f"a kept lane after a verified landing must not fail the run (NFR-004)\n{out}"
    assert "Traceback" not in out, out
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp02.py"), out
    assert state_files(mission) == [], f"the consolidation record must be cleared (FR-032)\n{out}"
    # The kept lane survives with the operator's file; its branch is kept with it.
    assert (lane_worktree(mission, "lane-b") / "operator-notes.txt").is_file(), out
    assert ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, 'lane-b')}"), out
    block = lane_cleanup_block(result)
    kept = outcome_line(block, "lane-b")
    assert kept.startswith("Kept"), block
    if _ON_LINUX:
        assert "MERGE_UNSAFE_WORKTREE_DIRTY" in kept, block
        assert "spec-kitty doctor workspaces --prune" in " ".join(block), block
        removed = outcome_line(block, "lane-a")
        assert removed.startswith("Removed"), block
        assert not lane_worktree(mission, "lane-a").exists(), out
        assert not ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, 'lane-a')}"), out
    # The coordination triple came down FIRST and completely (FR-031).
    assert not ref_exists(mission.repo, f"refs/heads/{mission.coord_branch}"), out


@pytest.fixture(scope="module")
def retained_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[CoordMission, subprocess.CompletedProcess[str]]:
    mission = _three_lane_mission(tmp_path_factory.mktemp("retained"), "01M7280B")
    add_lane_worktrees(mission, ("lane-a",))
    return mission, run_terminus(mission, consolidate_args(mission, "--keep-worktree", "--keep-branch"))


def test_retained_by_policy_distinct_from_kept(
    retained_run: tuple[CoordMission, subprocess.CompletedProcess[str]],
    dirtied_run: tuple[CoordMission, subprocess.CompletedProcess[str]],
) -> None:
    """FR-033 ratchet: the same fixture without retention (``dirtied_run``) removes its clean lane."""
    mission, result = retained_run
    out = output(result)

    assert result.returncode == 0, out
    assert state_files(mission) == [], out
    block = lane_cleanup_block(result)
    for lane_id in ("lane-a", "lane-b", "lane-c"):
        line = outcome_line(block, lane_id)
        assert line.startswith("Retained") and "retained by policy" in line, block
        assert not line.startswith("Kept"), block
        assert ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, lane_id)}"), out
    assert lane_worktree(mission, "lane-a").is_dir(), out

    paired_mission, paired = dirtied_run
    if _ON_LINUX:
        paired_line = outcome_line(lane_cleanup_block(paired), "lane-a")
        assert paired_line.startswith("Removed") and "retained by policy" not in paired_line, output(paired)
        assert not lane_worktree(paired_mission, "lane-a").exists(), output(paired)


def test_missing_branch_keeps_lane_tip_ref(tmp_path: Path) -> None:
    mission = _three_lane_mission(tmp_path, "01M7280C")
    tip = record_lane_tip(mission, "lane-a")
    removed_branch = lane_branch(mission, "lane-a")
    delete_by_hand = f"subprocess.run(['git', 'branch', '-D', {removed_branch!r}], check=True, capture_output=True)"
    result = run_patched(mission, consolidate_args(mission), after_gate(delete_by_hand))
    out = output(result)

    assert result.returncode == 0, out
    assert not ref_exists(mission.repo, f"refs/heads/{removed_branch}"), out
    assert ref_exists(mission.repo, f"{_LANE_TIP_PREFIX}{removed_branch}"), f"the last reference to the lane must survive (FR-034)\n{out}"
    assert git(mission.repo, "rev-parse", f"{_LANE_TIP_PREFIX}{removed_branch}") == tip
    # A branch this run DID delete has its tip ref cleared (only after the confirmed delete).
    assert not ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, 'lane-b')}"), out
    assert not ref_exists(mission.repo, f"{_LANE_TIP_PREFIX}{lane_branch(mission, 'lane-b')}"), out


def _kill_after_first_lane_leg() -> str:
    return """
from specify_cli.lanes import lane_tip as _lane_tip
_original_clear = _lane_tip.clear_tip
def clear_tip(repo_root, branch):
    _original_clear(repo_root, branch)
    probe = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + branch], cwd=repo_root, capture_output=True, check=False)
    if probe.returncode != 0:  # only a clear that follows this run's own lane branch delete
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(137)
_lane_tip.clear_tip = clear_tip
"""


def test_abort_after_partial_cleanup_never_restores_lane_branches(tmp_path: Path) -> None:
    mission = _three_lane_mission(tmp_path, "01M7280D")
    lane_tips = {lane_id: mission.rev(lane_branch(mission, lane_id)) for lane_id in ("lane-a", "lane-b", "lane-c")}
    killed = run_patched(mission, consolidate_args(mission), _kill_after_first_lane_leg())
    assert killed.returncode == 137, output(killed)
    deleted = [lane_id for lane_id in lane_tips if not ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, lane_id)}")]
    assert deleted, f"the kill must land after a lane branch was deleted\n{output(killed)}"
    landed = mission.rev(mission.target_branch)

    aborted = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--abort"])

    out = output(aborted)
    assert aborted.returncode == 0, out
    for lane_id in deleted:
        assert not ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, lane_id)}"), f"{lane_id} must not be recreated by --abort\n{out}"
    assert mission.rev(mission.target_branch) == landed, f"a verified landing is never rolled back\n{out}"
    assert state_files(mission) == [], out


def test_coord_teardown_refusal_exit_codes_unchanged(tmp_path: Path) -> None:
    """A coordination teardown refusal keeps exit 1 and leaves every lane in place as evidence (FR-031)."""
    mission = _three_lane_mission(tmp_path, "01M7280E")
    add_lane_worktrees(mission, ("lane-a",))
    coord_worktree = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    late_commit = (
        f"(Path({str(coord_worktree)!r}) / 'operator-scratch.txt').write_text('only copy\\n', encoding='utf-8')\n"
        f"subprocess.run(['git', '-C', {str(coord_worktree)!r}, 'add', 'operator-scratch.txt'], check=True)\n"
        f"subprocess.run(['git', '-C', {str(coord_worktree)!r}, 'commit', '-qm', 'operator scratch'], check=True)"
    )
    result = run_patched(mission, consolidate_args(mission), after_gate(late_commit))
    out = output(result)

    assert result.returncode == 1, out
    assert "coordination teardown incomplete" in flat(result) and "operator-scratch.txt" in flat(result), out
    assert ref_exists(mission.repo, f"refs/heads/{mission.coord_branch}"), out
    for lane_id in ("lane-a", "lane-b", "lane-c"):
        assert ref_exists(mission.repo, f"refs/heads/{lane_branch(mission, lane_id)}"), f"{lane_id} must stay as evidence\n{out}"
    assert lane_worktree(mission, "lane-a").is_dir(), out
    assert state_files(mission), f"the record survives a coordination refusal so --resume can finish\n{out}"


def lane_cleanup_json(result: subprocess.CompletedProcess[str]) -> list[dict[str, object]]:
    """``data.lane_cleanup`` of an orchestrator-api envelope (the last JSON line of stdout)."""
    lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert lines, output(result)
    envelope = json.loads(lines[-1])
    cleanup = envelope["data"]["lane_cleanup"]
    assert isinstance(cleanup, list)
    return cleanup
