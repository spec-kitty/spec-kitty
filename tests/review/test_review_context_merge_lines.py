"""FR-007 (approved-lane-resolution-route): the review context points the reviewer at each merge's own resolution.

Contract ``contracts/review-context-merges.md``: ``resolve_wp_review_range`` lists every merge commit of
``base..tip`` (``rev-list --merges --full-history``, no pathspec), and ``render_review_context`` prints one
command line per merge after the REVIEW COMMANDS lines, or a cannot-show line on a git without
``--remerge-diff``. A range with no merges renders as before. Commands only, never patch text (C-001).
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from kernel.git import GitCommandError
from runtime.next.prompt_builder import _review_command_lines
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.review import wp_range
from specify_cli.review.context_block import BYTE_BUDGET, render_review_context
from specify_cli.review.wp_range import FileChange, RangeCommit, RangeGap, RangeSource, RangeStatus, WpReviewRange, resolve_wp_review_range
from tests.consolidation import characterization_support as cs
from tests.terminus.canceled_dependency_support import ACTOR, _commit_in
from tests.terminus.mixed_lane_support import transition

BASE = "a" * 40
TIP = "b" * 40
M1 = "c" * 40
M2 = "d" * 40
REQS = "CITED REQUIREMENTS:"
_LABEL = "RESOLUTION MERGE (operator-authored, review these bytes):"

_BASE_RANGE = WpReviewRange(
    wp_id="WP02",
    base=BASE,
    tip=TIP,
    base_source=RangeSource.RECORDED_WINDOW,
    tip_source=RangeSource.RECORDED_SUBMISSION,
    gap=None,
    status=RangeStatus.RECORDED,
    commits=(RangeCommit("1" * 40, "feat(WP02): first"),),
    files=(FileChange("src/m2/real.py", 2, 0),),
    owned_pathspecs=("src/m2/**",),
)


def _range(**overrides: Any) -> WpReviewRange:
    return replace(_BASE_RANGE, **overrides)


# --------------------------------------------------------------------------- renderer (pure)


@pytest.mark.fast
def test_merges_render_one_labelled_line_each() -> None:
    lines = render_review_context(_range(merges=(M1, M2), remerge_available=True), ())

    diff_at = lines.index(f"  git diff {BASE}..{TIP} -- 'src/m2/**'")
    assert lines[diff_at + 1 : diff_at + 3] == [
        f"  {_LABEL} git show --remerge-diff {M1}",
        f"  {_LABEL} git show --remerge-diff {M2}",
    ]
    assert lines[diff_at + 3] == REQS


@pytest.mark.fast
def test_merges_without_remerge_support_render_the_cannot_show_line() -> None:
    lines = render_review_context(_range(merges=(M1, M2), remerge_available=False), ())

    expected = [f"  RESOLUTION MERGE {sha[:12]}: this git cannot show the resolution (needs git >= 2.36); review the merge by hand" for sha in (M1, M2)]
    diff_at = next(index for index, line in enumerate(lines) if line.startswith("  git diff "))
    assert lines[diff_at + 1 : diff_at + 3] == expected
    assert not any("--remerge-diff" in line for line in lines)


@pytest.mark.fast
def test_no_merges_renders_unchanged() -> None:
    assert render_review_context(_range(), ()) == [
        "REVIEW RANGE (WP02): aaaaaaaaaaaa..bbbbbbbbbbbb  [recorded]",
        "  base: aaaaaaaaaaaa (window open)",
        "  tip:  bbbbbbbbbbbb (for_review submission)",
        "IMPLEMENTATION COMMITS (1; = output of the git log command below):",
        "  111111111111 feat(WP02): first",
        "CHANGED FILES (owned files, +added -removed):",
        "  +2 -0  src/m2/real.py",
        "REVIEW COMMANDS:",
        f"  git log --oneline {BASE}..{TIP} -- 'src/m2/**'",
        f"  git diff {BASE}..{TIP} -- 'src/m2/**'",
        REQS,
        "  (none cited)",
    ]
    for variant in (_range(remerge_available=False), _range(status=RangeStatus.DERIVED, base_source=RangeSource.CLAIM_BASE_REF)):
        assert not any("RESOLUTION MERGE" in line for line in render_review_context(variant, ()))


@pytest.mark.fast
def test_merge_lines_do_not_consume_the_byte_budget() -> None:
    commits = tuple(RangeCommit(f"{index:040x}", f"feat(WP02): step {index} " + "x" * 60) for index in range(200))
    crowded = _range(commits=commits)
    without = render_review_context(crowded, ())
    merges = tuple(f"{index:040x}"[::-1] for index in range(30))
    with_merges = render_review_context(replace(crowded, merges=merges), ())

    merge_lines = [line for line in with_merges if "RESOLUTION MERGE" in line]
    assert len(merge_lines) == len(merges)
    assert [line for line in with_merges if "RESOLUTION MERGE" not in line] == without
    assert any(line.startswith("  … ") for line in without), "precondition: the commit list fills the budget"
    budgeted = with_merges[: with_merges.index("REVIEW COMMANDS:")]
    assert sum(len(line.encode("utf-8")) + 1 for line in budgeted) <= BYTE_BUDGET


@pytest.mark.fast
def test_unavailable_range_prints_no_merge_line() -> None:
    unavailable = WpReviewRange.unavailable("WP02", RangeGap.STATUS_UNREADABLE)

    assert unavailable.merges == ()
    assert not any("RESOLUTION MERGE" in line for line in render_review_context(unavailable, ()))


# --------------------------------------------------------------------------- range (real git)

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _merge_side(tree: Path, lane_branch: str, side: str, side_path: str, *, resolution: str | None) -> str:
    """Merge a side branch touching only *side_path* into the lane; *resolution* hand-edits an owned file in the merge."""
    _git(tree, "checkout", "-q", "-b", side)
    _commit_in(tree, side_path, f"{side}\n", f"chore: {side}")
    _git(tree, "checkout", "-q", lane_branch)
    _git(tree, "merge", "-q", "--no-ff", "--no-commit", side)
    if resolution is not None:
        (tree / "src/pkg/a.py").write_text(resolution, encoding="utf-8")
        _git(tree, "add", "src/pkg/a.py")
    _git(tree, "commit", "-q", "-m", f"Merge {side}")
    return _git(tree, "rev-parse", "HEAD")


def _lane_with_merges(tmp_path: Path, *, mid8: str, merges: tuple[tuple[str, str | None], ...]) -> tuple[cs.ShapeMission, list[str]]:
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01",))
    tree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, "src/pkg/a.py", "A = 1\n", f"feat({mission.slug}): a")
    shas = [_merge_side(tree, branch, f"side-{index}", side_path, resolution=resolution) for index, (side_path, resolution) in enumerate(merges)]
    transition(mission, "WP01", "for_review", actor=ACTOR, subtasks_complete=True)
    mission.lane_branches["WP01"] = branch
    return cs._from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",)), shas


def _resolve(mission: cs.ShapeMission, monkeypatch: pytest.MonkeyPatch) -> WpReviewRange:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    with cs.mission_environment(mission):
        return resolve_wp_review_range(mission.repo, mission.slug, "WP01", owned_files=["src/**"])


@pytest.mark.integration
@pytest.mark.git_repo
def test_range_lists_a_hand_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, (merge,) = _lane_with_merges(tmp_path, mid8="01M7WM01", merges=(("docs/side.md", "A = 2  # resolved by hand\n"),))

    found = _resolve(mission, monkeypatch)

    assert found.status is RangeStatus.RECORDED
    assert found.merges == (merge,)
    assert found.remerge_available is True


@pytest.mark.integration
@pytest.mark.git_repo
def test_merge_with_no_owned_change_is_still_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, (clean, resolved) = _lane_with_merges(tmp_path, mid8="01M7WM02", merges=(("docs/clean.md", None), ("docs/other.md", "A = 3  # resolved by hand\n")))

    found = _resolve(mission, monkeypatch)

    assert clean not in {commit.sha for commit in found.commits}, "precondition: simplification drops the clean merge from the commit list"
    assert found.merges == (clean, resolved)


@pytest.mark.integration
@pytest.mark.git_repo
def test_range_without_merges_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, _ = _lane_with_merges(tmp_path, mid8="01M7WM03", merges=())

    found = _resolve(mission, monkeypatch)

    assert found.status is RangeStatus.RECORDED
    assert found.merges == ()
    assert found.listing_gap is None


@pytest.mark.integration
@pytest.mark.git_repo
def test_merge_listing_failure_is_fail_soft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, _ = _lane_with_merges(tmp_path, mid8="01M7WM04", merges=(("docs/side.md", "A = 4\n"),))
    real_run_git = wp_range.run_git

    def _failing(repo_root: Path, *args: str, **kwargs: Any) -> Any:
        if "--merges" in args:
            raise GitCommandError(argv=args, cwd=repo_root, returncode=128, stderr="boom")
        return real_run_git(repo_root, *args, **kwargs)

    monkeypatch.setattr(wp_range, "run_git", _failing)
    found = _resolve(mission, monkeypatch)

    assert found.base is not None and found.tip is not None
    assert found.merges == ()
    assert found.listing_gap == "merges"

    lines = render_review_context(found, ())
    fallback = (
        f"  RESOLUTION MERGES: could not be listed; run git rev-list --merges --full-history {found.base}..{found.tip}"
        " and review each with git show --remerge-diff <sha>"
    )
    diff_at = next(index for index, line in enumerate(lines) if line.startswith("  git diff "))
    assert lines[diff_at + 1] == fallback
    assert lines[diff_at + 2] == REQS


@pytest.mark.integration
@pytest.mark.git_repo
def test_next_review_prompt_prints_the_hand_merge_resolution_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ATDD (US5): the ``spec-kitty next`` review prompt (render site 1) carries the RESOLUTION MERGE command for a hand merge."""
    mission, (merge,) = _lane_with_merges(tmp_path, mid8="01M7WM05", merges=(("docs/side.md", "A = 5  # resolved by hand\n"),))
    workspace: Any = SimpleNamespace(lane_id="lane-a", context=None, branch_name=mission.lane_branches["WP01"])
    wp_meta: Any = SimpleNamespace(owned_files=["src/**"], requirement_refs=[])
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)

    with cs.mission_environment(mission):
        lines = _review_command_lines(mission.repo, mission.slug, "WP01", wp_meta, workspace, None)

    assert f"  {_LABEL} git show --remerge-diff {merge}" in lines
    assert len(merge) == 40
