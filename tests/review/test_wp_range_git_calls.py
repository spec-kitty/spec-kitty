"""NFR-002: the review range costs a constant number of git processes, independent of the range size (#7578).

Every git process is counted once, at the one level all callers share: ``subprocess.Popen`` (``run``,
``check_output`` and ``kernel.git.run_git`` all start their process through it). The recorded-range
Mission is built with 1 and with 200 implementation commits in the work package's window (the 200
spread over 60 owned files, plus out-of-map commits in both), so a per-commit or per-file call would
change the count.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.review.wp_range import RangeStatus, WpReviewRange, resolve_wp_review_range
from tests.consolidation import characterization_support as cs
from tests.integration import single_branch_window_support as sb
from tests.integration.review.review_range_fixtures import strip_single_branch_stamps
from tests.terminus.canceled_dependency_support import ACTOR, _commit_in
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BUDGET = 10
_OWNED_FILES = 60
_OUT_OF_MAP = ("docs/a.md", "docs/b.md", "tools/c.cfg")
_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")


def _submitted_lane(tmp_path: Path, *, commits: int, mid8: str) -> cs.ShapeMission:
    """One code lane, WP01 claimed, *commits* owned commits over up to 60 files, out-of-map commits, submitted."""
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01",))
    tree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    for step in range(commits):
        _commit_in(tree, f"src/pkg/f{step % _OWNED_FILES:02d}.py", f"STEP = {step}\n", f"feat({mission.slug}): step {step}")
    for path in _OUT_OF_MAP:
        _commit_in(tree, path, "outside\n", f"chore: {path} outside the owned files")
    transition(mission, "WP01", "for_review", actor=ACTOR, subtasks_complete=True)
    mission.lane_branches["WP01"] = branch
    return cs._from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))


@pytest.fixture(scope="module")
def lanes_by_size(tmp_path_factory: pytest.TempPathFactory) -> dict[int, cs.ShapeMission]:
    root = tmp_path_factory.mktemp("wp-range-calls")
    return {
        1: _submitted_lane(root / "one", commits=1, mid8="01M77C01"),
        200: _submitted_lane(root / "many", commits=200, mid8="01M77C02"),
    }


@pytest.fixture
def git_processes(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    seen: list[list[str]] = []
    real_popen: Callable[..., Any] = subprocess.Popen

    def _spy(args: Any, *rest: Any, **kwargs: Any) -> Any:
        argv = [str(arg) for arg in args] if isinstance(args, (list, tuple)) else [str(args)]
        if argv and (argv[0] == "git" or argv[0].endswith("/git")):
            seen.append(argv)
        return real_popen(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _spy)
    yield seen


def _measure(seen: list[list[str]], resolve: Callable[[], WpReviewRange]) -> tuple[WpReviewRange, list[list[str]]]:
    seen.clear()
    found = resolve()
    return found, list(seen)


def _resolve_lane(mission: cs.ShapeMission) -> WpReviewRange:
    return resolve_wp_review_range(mission.repo, mission.slug, "WP01", owned_files=["src/**"])


def _has(calls: list[list[str]], *words: str) -> bool:
    return any(all(word in argv for word in words) for argv in calls)


def test_recorded_range_costs_a_constant_number_of_git_processes(
    lanes_by_size: dict[int, cs.ShapeMission], git_processes: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    counts: dict[int, int] = {}
    files: dict[int, int] = {}
    for size, mission in lanes_by_size.items():
        with cs.mission_environment(mission):
            found, calls = _measure(git_processes, lambda m=mission: _resolve_lane(m))
        assert found.status is RangeStatus.RECORDED, f"precondition ({size} commits): a recorded range"
        assert len(found.commits) == size
        assert len(found.out_of_map) == len(_OUT_OF_MAP)
        # Non-vacuity: the spy saw the listing calls themselves.
        assert _has(calls, "log"), calls
        assert _has(calls, "diff", "--numstat"), calls
        counts[size] = len(calls)
        files[size] = len(found.files)

    assert files[200] >= 50, "the large window must spread over many owned files, so a per-file call would show"
    assert counts[1] <= _BUDGET and counts[200] <= _BUDGET, counts
    assert counts[1] == counts[200], f"the cost must not depend on the range size: {counts}"


def test_derived_pre_stamp_commit_to_target_range_stays_within_budget(tmp_path: Path, git_processes: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug = sb.build_template(tmp_path / "template", commit_to_target=True)
    copy = tmp_path / "copy" / "repo"
    shutil.copytree(repo, copy, symlinks=True)
    monkeypatch.chdir(copy)
    for key, value in sb.cli_env(tmp_path / "copy").items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            monkeypatch.setenv(key, value)
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    m = sb.Mission(copy, slug, tmp_path / "copy")
    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.submit(m, "WP01")
    # The Mission's events predate the window stamps (recorded before #7578).
    strip_single_branch_stamps(copy, copy / "kitty-specs" / slug, "WP01")

    found, calls = _measure(git_processes, lambda: resolve_wp_review_range(copy, slug, "WP01", owned_files=["src/m1/**"]))

    assert found.status is RangeStatus.DERIVED, "precondition: a pre-stamp commit-to-target range is derived"
    assert _has(calls, "log", "--format=%H", "--no-show-signature"), calls
    assert len(calls) <= _BUDGET, calls
