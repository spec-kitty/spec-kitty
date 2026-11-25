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
from specify_cli.consolidation.merge_attribute_guard import MERGE_PROBE_CONFIG_PINS
from specify_cli.review import wp_range
from specify_cli.review.context_block import BYTE_BUDGET, render_review_context, resolution_command
from specify_cli.review.wp_range import FileChange, RangeCommit, RangeGap, RangeSource, RangeStatus, WpReviewRange, resolve_wp_review_range
from tests.consolidation import characterization_support as cs
from tests.terminus.canceled_dependency_support import ACTOR, _commit_in
from tests.terminus.mixed_lane_support import transition

BASE = "a" * 40
TIP = "b" * 40
M1 = "c" * 40
M2 = "d" * 40
TARGET = "e" * 40
REQS = "CITED REQUIREMENTS:"
_LABEL = "RESOLUTION MERGE (operator-authored, review these bytes):"
#: WP12 binding DoD (b): the FR-010 guard's pinned merge config as ``-c`` flags, then no external diff driver or textconv.
_PINS = " ".join(f"-c {key}={value}" for key, value in MERGE_PROBE_CONFIG_PINS)
_SHOW = f"git {_PINS} --attr-source={TARGET} show --remerge-diff --no-ext-diff --no-textconv"
_ATTR_NOTE = (
    "  note: the resolution commands read .gitattributes from the target branch tip eeeeeeeeeeee and pin git's merge config,"
    " so a merge driver or a merge setting committed in the range, such as merge=union, cannot hide the resolution"
)
_UNPINNED_NOTE = (
    "  note: this git cannot neutralise attributes (--attr-source needs git >= 2.40): the resolution commands read"
    " .gitattributes from the checkout, so a merge driver committed in the range, such as merge=union, can hide the"
    " resolution; review the merges with git >= 2.40"
)

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
    attributes_source=TARGET,
)


def _range(**overrides: Any) -> WpReviewRange:
    return replace(_BASE_RANGE, **overrides)


# --------------------------------------------------------------------------- renderer (pure)


@pytest.mark.fast
def test_merges_render_one_labelled_line_each() -> None:
    lines = render_review_context(_range(merges=(M1, M2), remerge_available=True), ())

    diff_at = lines.index(f"  git diff {BASE}..{TIP} -- 'src/m2/**'")
    assert lines[diff_at + 1 : diff_at + 4] == [
        f"  {_LABEL} {_SHOW} {M1}",
        f"  {_LABEL} {_SHOW} {M2}",
        _ATTR_NOTE,
    ]
    assert lines[diff_at + 4] == REQS


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
    assert [line for line in with_merges if "RESOLUTION MERGE" not in line and line != _ATTR_NOTE] == without
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

    target = _git(mission.repo, "rev-parse", "main")
    assert found.attributes_source == target, "a failed merge listing still reads the trusted attribute source"
    lines = render_review_context(found, ())
    fallback = (
        f"  RESOLUTION MERGES: could not be listed; run git rev-list --merges --full-history {found.base}..{found.tip}"
        f" and review each with git {_PINS} --attr-source={target} show --remerge-diff --no-ext-diff --no-textconv <sha>"
    )
    diff_at = next(index for index, line in enumerate(lines) if line.startswith("  git diff "))
    assert lines[diff_at + 1] == fallback
    assert lines[diff_at + 2] == _ATTR_NOTE.replace("eeeeeeeeeeee", target[:12])
    assert lines[diff_at + 3] == REQS


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

    command = next(line for line in lines if line.startswith(f"  {_LABEL}"))
    target = _git(mission.repo, "rev-parse", "main")
    assert command == f"  {_LABEL} git {_PINS} --attr-source={target} show --remerge-diff --no-ext-diff --no-textconv {merge}"
    assert len(merge) == 40


@pytest.mark.git_repo
def test_pinned_command_shows_a_union_hidden_resolution(tmp_path: Path) -> None:
    """A lane-committed ``merge=union`` hides the resolution from a plain ``--remerge-diff``; the printed command pins attributes to the range base."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _commit_in(repo, "src/pkg/a.py", "A = 1\n", "seed")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit_in(repo, "src/pkg/a.py", "A = 3\n", "side")
    _git(repo, "checkout", "-q", "main")
    _commit_in(repo, ".gitattributes", "src/pkg/a.py merge=union\n", "lane: union driver")
    _commit_in(repo, "src/pkg/a.py", "A = 2\n", "lane work")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge side", "side")
    merge = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "show", "HEAD:src/pkg/a.py") == "A = 2\nA = 3", "precondition: the union driver resolved the conflict"
    review_range = _range(base=base, tip=merge, merges=(merge,), remerge_available=True, attributes_source=base)

    command = next(line for line in render_review_context(review_range, ()) if line.startswith(f"  {_LABEL}"))
    argv = command.removeprefix(f"  {_LABEL} ").split()
    unpinned = [arg for arg in argv if not arg.startswith("--attr-source=")]

    assert argv != unpinned, "the printed command pins the attribute source"
    assert "src/pkg/a.py" in _git(repo, *argv[1:], "--format=", "--name-only")
    assert "src/pkg/a.py" not in _git(repo, *unpinned[1:], "--format=", "--name-only")


# --------------------------------------------------------------------------- WP12 binding DoD (a)-(d)


@pytest.mark.fast
def test_resolution_command_is_shaped_by_the_guards_pin_table() -> None:
    """(b): every ``MERGE_PROBE_CONFIG_PINS`` row is a ``-c`` flag, ``merge.renormalize=false`` included, then no ext-diff/textconv."""
    command = resolution_command(_range())

    assert command == _SHOW
    for key, value in MERGE_PROBE_CONFIG_PINS:
        assert f"-c {key}={value}" in command
    assert "-c merge.renormalize=false" in command
    assert command.endswith(" show --remerge-diff --no-ext-diff --no-textconv")


@pytest.mark.fast
def test_git_without_attr_source_prints_the_cannot_neutralise_line() -> None:
    """(a): on git < 2.40 the commands drop ``--attr-source`` and one line says the attributes cannot be neutralised."""
    lines = render_review_context(_range(merges=(M1,), attr_source_available=False), ())

    command = next(line for line in lines if line.startswith(f"  {_LABEL}"))
    assert "--attr-source" not in command
    assert command == f"  {_LABEL} git {_PINS} show --remerge-diff --no-ext-diff --no-textconv {M1}"
    assert lines[lines.index(command) + 1] == _UNPINNED_NOTE
    assert _ATTR_NOTE not in lines


@pytest.mark.fast
def test_unreadable_target_falls_back_to_the_range_base_and_says_so() -> None:
    lines = render_review_context(_range(merges=(M1,), attributes_source=None), ())

    assert f"--attr-source={BASE} " in next(line for line in lines if line.startswith(f"  {_LABEL}"))
    assert any("the range base aaaaaaaaaaaa (the target branch could not be read)" in line for line in lines)


@pytest.mark.fast
def test_unlisted_merges_on_git_without_remerge_diff_print_the_cannot_show_form() -> None:
    """(d): the merge listing failed AND this git lacks ``--remerge-diff``: no ``show --remerge-diff`` instruction."""
    lines = render_review_context(_range(listing_gap="merges", remerge_available=False), ())

    expected = (
        "  RESOLUTION MERGES: could not be listed, and this git cannot show a resolution (needs git >= 2.36); list them with"
        f" git rev-list --merges --full-history {BASE}..{TIP} and review each merge by hand"
    )
    diff_at = next(index for index, line in enumerate(lines) if line.startswith("  git diff "))
    assert lines[diff_at + 1] == expected
    assert lines[diff_at + 2] == REQS
    assert not any("--remerge-diff" in line for line in lines)


@pytest.mark.integration
@pytest.mark.git_repo
def test_failed_listing_probes_this_gits_abilities(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a)/(d): a failed merge listing still probes ``--remerge-diff`` and ``--attr-source`` support (WP01's probes)."""
    mission, _ = _lane_with_merges(tmp_path, mid8="01M7WM06", merges=(("docs/side.md", "A = 6\n"),))
    real_run_git = wp_range.run_git

    def _failing(repo_root: Path, *args: str, **kwargs: Any) -> Any:
        if "--merges" in args:
            raise GitCommandError(argv=args, cwd=repo_root, returncode=128, stderr="boom")
        return real_run_git(repo_root, *args, **kwargs)

    monkeypatch.setattr(wp_range, "run_git", _failing)
    monkeypatch.setattr(wp_range, "remerge_diff_available", lambda _repo: False)
    monkeypatch.setattr(wp_range, "check_attr_source_available", lambda _repo: False)
    found = _resolve(mission, monkeypatch)

    assert found.merges_unlisted and found.remerge_available is False and found.attr_source_available is False
    assert any(line.startswith("  RESOLUTION MERGES: could not be listed, and this git cannot show") for line in render_review_context(found, ()))


@pytest.mark.integration
@pytest.mark.git_repo
def test_old_git_range_renders_unpinned_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) through the resolver: ``check_attr_source_available`` false reaches the block as the cannot-neutralise line."""
    mission, (merge,) = _lane_with_merges(tmp_path, mid8="01M7WM07", merges=(("docs/side.md", "A = 7  # resolved by hand\n"),))
    monkeypatch.setattr(wp_range, "check_attr_source_available", lambda _repo: False)

    found = _resolve(mission, monkeypatch)

    assert found.attr_source_available is False
    lines = render_review_context(found, ())
    assert f"  {_LABEL} git {_PINS} show --remerge-diff --no-ext-diff --no-textconv {merge}" in lines
    assert _UNPINNED_NOTE in lines


@pytest.mark.integration
@pytest.mark.git_repo
def test_union_committed_before_the_window_base_is_neutralised_by_the_target_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(c): ``merge=union`` committed on the lane BEFORE the window opened is in the range base; the printed command must
    read attributes from the pre-run target tip, so running it lists the union-hidden path."""
    mission, manifest = cs._bootstrap_one_lane_coord(tmp_path, mid8="01M7WM08", wps=("WP01",))
    tree, branch = allocate_lane_worktree(mission.repo, mission.slug, "WP01", manifest)
    _commit_in(tree, "src/pkg/a.py", "A = 1\n", "seed a.py on the lane")
    _commit_in(tree, ".gitattributes", "src/pkg/a.py merge=union\n", "lane: union driver, before the window opens")
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _git(tree, "checkout", "-q", "-b", "side")
    _commit_in(tree, "src/pkg/a.py", "A = 3\n", "side")
    _git(tree, "checkout", "-q", branch)
    _commit_in(tree, "src/pkg/a.py", "A = 2\n", f"feat({mission.slug}): a")
    _git(tree, "merge", "-q", "--no-ff", "-m", "Merge side", "side")
    merge = _git(tree, "rev-parse", "HEAD")
    assert _git(tree, "show", "HEAD:src/pkg/a.py") == "A = 2\nA = 3", "precondition: the union driver resolved the conflict"
    transition(mission, "WP01", "for_review", actor=ACTOR, subtasks_complete=True)
    mission.lane_branches["WP01"] = branch
    shaped = cs._from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))

    found = _resolve(shaped, monkeypatch)

    target = _git(mission.repo, "rev-parse", "main")
    assert found.merges == (merge,)
    assert _git(mission.repo, "cat-file", "-p", f"{found.base}:.gitattributes") == "src/pkg/a.py merge=union", "precondition: the base holds the union"
    assert found.attributes_source == target
    command = next(line for line in render_review_context(found, ()) if line.startswith(f"  {_LABEL}"))
    argv = command.removeprefix(f"  {_LABEL} ").split()
    assert f"--attr-source={target}" in argv
    assert "src/pkg/a.py" in _git(mission.repo, *argv[1:], "--format=", "--name-only")
    from_base = [f"--attr-source={found.base}" if arg.startswith("--attr-source=") else arg for arg in argv]
    assert "src/pkg/a.py" not in _git(mission.repo, *from_base[1:], "--format=", "--name-only"), "control: the range base hides it"
