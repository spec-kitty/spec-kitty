"""The review-context renderer (#7578, WP05 T023): golden blocks for ``contracts/review-context-block.md``.

``render_review_context`` is pure: a ``WpReviewRange`` and the cited requirements in, lines out.
Optional (``?``) contract lines render with the two-space item indent.
"""

from __future__ import annotations

import shlex
from dataclasses import replace
from typing import Any

import pytest

from specify_cli.requirement_mapping.text import CitedRequirement, Resolution
from specify_cli.review.context_block import BYTE_BUDGET, UNAVAILABLE_COMMAND_LINE, describe_gap, render_review_context, review_diff_command
from specify_cli.review.wp_range import FileChange, RangeCommit, RangeGap, RangeSource, RangeStatus, WpReviewRange

pytestmark = [pytest.mark.fast]

BASE = "a" * 40
TIP = "b" * 40
C1 = "1" * 40
C2 = "2" * 40
REQS = "CITED REQUIREMENTS:"


_BASE_RANGE = WpReviewRange(
    wp_id="WP02",
    base=BASE,
    tip=TIP,
    base_source=RangeSource.RECORDED_WINDOW,
    tip_source=RangeSource.RECORDED_SUBMISSION,
    gap=None,
    status=RangeStatus.RECORDED,
    commits=(RangeCommit(C1, "feat(WP02): first"), RangeCommit(C2, "feat(WP02): second")),
    files=(FileChange("src/m2/real.py", 2, 0), FileChange("src/m2/extra.py", 3, 1)),
    out_of_map=("docs/notes.md",),
    out_of_map_only_commits=1,
    owned_pathspecs=("src/m2/**",),
)


def _range(**overrides: Any) -> WpReviewRange:
    return replace(_BASE_RANGE, **overrides)


_CITED = (
    CitedRequirement("FR-001", Resolution.DECLARED, "FR-001 — Title: things work."),
    CitedRequirement("C-009", Resolution.NOT_DECLARED),
    CitedRequirement("other-mission#FR-002", Resolution.OTHER_MISSION),
    CitedRequirement("NFR-002", Resolution.AMBIGUOUS),
)
_CITED_LINES = [
    REQS,
    "  FR-001 — Title: things work.",
    "  C-009 — not declared in this Mission's spec",
    "  other-mission#FR-002 — cites another Mission (not resolved here)",
    "  NFR-002 — declared more than once in this Mission's spec; see spec.md",
]


def test_recorded_range_golden() -> None:
    assert render_review_context(_range(), _CITED) == [
        "REVIEW RANGE (WP02): aaaaaaaaaaaa..bbbbbbbbbbbb  [recorded]",
        "  base: aaaaaaaaaaaa (window open)",
        "  tip:  bbbbbbbbbbbb (for_review submission)",
        "IMPLEMENTATION COMMITS (2; = output of the git log command below):",
        "  111111111111 feat(WP02): first",
        "  222222222222 feat(WP02): second",
        "CHANGED FILES (owned files, +added -removed):",
        "  +3 -1  src/m2/extra.py",
        "  +2 -0  src/m2/real.py",
        "  OUTSIDE OWNED FILES (1 path(s) changed in the range; 1 commit(s) touch no owned file; review rationale required): docs/notes.md",
        "REVIEW COMMANDS:",
        f"  git log --oneline {BASE}..{TIP} -- 'src/m2/**'",
        f"  git diff {BASE}..{TIP} -- 'src/m2/**'",
        *_CITED_LINES,
    ]


def test_derived_range_with_a_gap_note_golden() -> None:
    derived = _range(
        base_source=RangeSource.CLAIM_BASE_REF,
        tip_source=RangeSource.EVENT_COMMIT,
        gap="not_recorded",
        status=RangeStatus.DERIVED,
    )

    lines = render_review_context(derived, ())

    assert lines[:4] == [
        "REVIEW RANGE (WP02): aaaaaaaaaaaa..bbbbbbbbbbbb  [derived]",
        "  base: aaaaaaaaaaaa (claim base ref)",
        "  note: recorded window not used: no window or submission stamp was recorded (not_recorded)",
        "  tip:  bbbbbbbbbbbb (for_review event commit)",
    ]
    assert lines[-2:] == [REQS, "  (none cited)"]


@pytest.mark.parametrize(
    ("source", "label"),
    [(RangeSource.OPENER_LANE_HEAD, "opener lane_head stamp"), (RangeSource.EVENT_COMMIT, "claim event commit")],
)
def test_every_base_source_has_its_own_label(source: RangeSource, label: str) -> None:
    lines = render_review_context(_range(base_source=source, status=RangeStatus.DERIVED, gap="not_on_lane"), ())

    assert lines[1] == f"  base: aaaaaaaaaaaa ({label})"
    assert lines[2] == "  note: recorded window not used: the recorded commit is not on the branch (not_on_lane)"


def test_moved_past_golden() -> None:
    lines = render_review_context(_range(moved_past=3), (), branch="main")

    assert lines[2:4] == ["  tip:  bbbbbbbbbbbb (for_review submission)", "  note: main has moved 3 commit(s) past the submitted tip"]
    assert "  note: the branch has moved 3 commit(s) past the submitted tip" in render_review_context(_range(moved_past=3), ())


def test_unavailable_golden() -> None:
    unavailable = WpReviewRange.unavailable("WP02", "no_submission", ("src/m2/**",))

    assert render_review_context(unavailable, _CITED[:2]) == [
        "REVIEW RANGE (WP02): unavailable — the work package has no for_review submission (no_submission)",
        "REVIEW COMMANDS:",
        "  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)",
        REQS,
        "  FR-001 — Title: things work.",
        "  C-009 — not declared in this Mission's spec",
    ]
    assert UNAVAILABLE_COMMAND_LINE.startswith("  (no deterministic range")


def test_unknown_gap_renders_its_value() -> None:
    lines = render_review_context(WpReviewRange.unavailable("WP02", "something_new"), ())

    assert lines[0] == "REVIEW RANGE (WP02): unavailable — something_new"


def test_no_owned_files_is_unscoped_and_has_no_outside_line_golden() -> None:
    """Re-pin (#7578, DIRECTIVE_041): the unscoped commands now carry the commit list's own pathspecs (``.`` plus the bookkeeping excludes)."""
    bookkeeping = (":(exclude)kitty-specs/m/status.*", ":(exclude).kittify/*")
    unscoped = _range(owned_pathspecs=(), out_of_map=(), out_of_map_only_commits=0, bookkeeping_pathspecs=bookkeeping)

    lines = render_review_context(unscoped, ())

    assert lines[:4] == [
        "REVIEW RANGE (WP02): aaaaaaaaaaaa..bbbbbbbbbbbb  [recorded]",
        "  base: aaaaaaaaaaaa (window open)",
        "  scope: unscoped (no owned_files declared)",
        "  tip:  bbbbbbbbbbbb (for_review submission)",
    ]
    assert not [line for line in lines if "OUTSIDE OWNED FILES" in line]
    scope = "-- . ':(exclude)kitty-specs/m/status.*' ':(exclude).kittify/*'"
    assert f"  git log --oneline {BASE}..{TIP} {scope}" in lines
    assert f"  git diff {BASE}..{TIP} {scope}" in lines


def test_binary_file_golden() -> None:
    lines = render_review_context(_range(files=(FileChange("src/m2/blob.bin", None, None),)), ())

    assert "  +- --  src/m2/blob.bin" in lines


def test_declared_text_without_its_id_prefix_gets_one() -> None:
    lines = render_review_context(_range(), (CitedRequirement("FR-003", Resolution.DECLARED, "bare text"),))

    assert lines[-1] == "  FR-003 — bare text"


# --------------------------------------------------------------------------- describe_gap


@pytest.mark.parametrize(
    ("gap", "expected"),
    [
        (RangeGap.NOT_RECORDED, "no window or submission stamp was recorded (not_recorded)"),
        (RangeGap.LANE_BRANCH_MISSING, "the lane branch was missing when the window opened (lane_branch_missing)"),
        (RangeGap.CAPTURE_FAILED, "the window capture failed (capture_failed)"),
        (RangeGap.NOT_ON_LANE, "the recorded commit is not on the branch (not_on_lane)"),
        (RangeGap.NO_SUBMISSION, "the work package has no for_review submission (no_submission)"),
        (RangeGap.UNRESOLVABLE_SHA, "no commit could be resolved for an end of the range (unresolvable_sha)"),
        (RangeGap.STATUS_UNREADABLE, "the status surface could not be read (status_unreadable)"),
    ],
)
def test_describe_gap_words_every_range_gap_and_keeps_its_value(gap: RangeGap, expected: str) -> None:
    assert describe_gap(gap) == expected
    assert describe_gap(gap.value) == expected


def test_describe_gap_passes_an_unknown_value_through_and_names_a_missing_one() -> None:
    assert describe_gap("some_future_gap") == "some_future_gap"
    assert describe_gap(None) == "unknown"
    assert describe_gap("") == "unknown"


# --------------------------------------------------------------------------- budget, order, determinism


def _many(n_commits: int, n_files: int, n_outside: int = 0) -> WpReviewRange:
    return _range(
        commits=tuple(RangeCommit(f"{index:040x}", f"feat(WP02): change number {index}") for index in range(n_commits)),
        files=tuple(FileChange(f"src/m2/file_{index:04d}.py", index, 0) for index in range(n_files)),
        out_of_map=tuple(f"docs/outside_{index:04d}.md" for index in range(n_outside)),
    )


def _budgeted(lines: list[str]) -> int:
    """The bytes NFR-001 budgets: the block before CITED REQUIREMENTS, without the REVIEW COMMANDS lines (ruling Q11)."""
    commands = lines.index("REVIEW COMMANDS:")
    budgeted = lines[:commands] + lines[commands + 3 : lines.index(REQS)]
    return len("".join(f"{line}\n" for line in budgeted).encode("utf-8"))


def test_large_range_stays_within_the_budget_with_exact_more_counts() -> None:
    lines = render_review_context(_many(500, 500, 50), _CITED)

    assert _budgeted(lines) <= BYTE_BUDGET
    assert lines[0].startswith("REVIEW RANGE (WP02)")
    assert "IMPLEMENTATION COMMITS (500; = output of the git log command below):" in lines
    assert "REVIEW COMMANDS:" in lines and lines[-len(_CITED_LINES) :] == _CITED_LINES
    commit_items = lines[
        lines.index("IMPLEMENTATION COMMITS (500; = output of the git log command below):") + 1 : lines.index("CHANGED FILES (owned files, +added -removed):")
    ]
    shown = len(commit_items) - 1
    assert commit_items[-1] == f"  … {500 - shown} more (see git log command)"
    files = lines[lines.index("CHANGED FILES (owned files, +added -removed):") + 1 : lines.index("REVIEW COMMANDS:")]
    shown_files = len([line for line in files if line.startswith("  +")])
    file_more = [line for line in files if line.startswith("  … ")]
    # The commit list fills first: what it leaves is less than one more commit line, so at most a
    # file line fits after it (the exact count depends on the fixed lines' byte lengths).
    assert shown_files <= 1, "the commit list used the whole budget first"
    assert file_more == [f"  … {500 - shown_files} more files"]
    outside = [line for line in files if "OUTSIDE OWNED FILES" in line]
    assert outside and outside[0].endswith("… 50 more")


def test_files_are_filled_after_commits_until_the_budget() -> None:
    lines = render_review_context(_many(3, 500), ())

    assert _budgeted(lines) <= BYTE_BUDGET
    files = lines[lines.index("CHANGED FILES (owned files, +added -removed):") + 1 : lines.index("REVIEW COMMANDS:")]
    shown = len([line for line in files if line.startswith("  +")])
    assert 0 < shown < 500
    assert f"  … {500 - shown} more files" in files


def test_outside_paths_are_cut_with_a_count_when_the_list_is_long() -> None:
    lines = render_review_context(_many(1, 1, 400), ())

    assert _budgeted(lines) <= BYTE_BUDGET
    outside = next(line for line in lines if "OUTSIDE OWNED FILES" in line)
    shown = outside.split("): ", 1)[1].split(", ")
    assert shown[-1] == f"… {400 - (len(shown) - 1)} more"


def test_outside_line_counts_paths_and_owned_free_commits_separately() -> None:
    """Out-of-map paths changed by mixed commits count as paths, not as commits that touch no owned file."""
    mixed = _range(out_of_map=("docs/a.md", "docs/b.md"), out_of_map_only_commits=0)

    outside = next(line for line in render_review_context(mixed, ()) if "OUTSIDE OWNED FILES" in line)

    assert outside == "  OUTSIDE OWNED FILES (2 path(s) changed in the range; 0 commit(s) touch no owned file; review rationale required): docs/a.md, docs/b.md"


def test_commits_keep_input_order_and_files_and_paths_are_sorted() -> None:
    commits = (RangeCommit(C2, "second-oldest? no: oldest"), RangeCommit(C1, "newer"))
    unsorted = _range(commits=commits, files=(FileChange("z.py", 1, 0), FileChange("a.py", 1, 0)), out_of_map=("z.md", "a.md"))

    lines = render_review_context(unsorted, ())

    assert [line for line in lines if line.startswith("  2222") or line.startswith("  1111")] == [
        "  222222222222 second-oldest? no: oldest",
        "  111111111111 newer",
    ]
    assert [line for line in lines if line.startswith("  +1 -0")] == ["  +1 -0  a.py", "  +1 -0  z.py"]
    assert next(line for line in lines if "OUTSIDE" in line).endswith("): a.md, z.md")


def test_rendering_is_deterministic() -> None:
    assert render_review_context(_many(40, 40, 5), _CITED) == render_review_context(_many(40, 40, 5), _CITED)


def test_commands_carry_full_shas_and_labels_twelve_characters() -> None:
    lines = render_review_context(_range(), ())

    commands = [line for line in lines if line.startswith("  git ")]
    assert all(f"{BASE}..{TIP}" in line for line in commands)
    labels = [line for line in lines if not line.startswith("  git ")]
    assert not [line for line in labels if BASE in line or TIP in line or C1 in line]
    assert "  111111111111 feat(WP02): first" in lines


def test_pathspecs_are_quoted_so_the_printed_command_survives_a_shell() -> None:
    specs = ("src/my dir/**", ":(exclude)kitty-specs/m/tasks/**", "it's.py")

    lines = render_review_context(_range(owned_pathspecs=specs), ())

    command = next(line for line in lines if line.startswith("  git diff "))
    argv = shlex.split(command)
    assert argv[argv.index("--") + 1 :] == list(specs)


def test_requirement_text_is_held_to_the_contract_cap() -> None:
    from specify_cli.requirement_mapping.text import TEXT_LIMIT, TRUNCATION_MARKER

    long_text = "FR-009 — " + "x" * 2000
    already_capped = long_text[:TEXT_LIMIT] + TRUNCATION_MARKER

    over = render_review_context(_range(), (CitedRequirement("FR-009", Resolution.DECLARED, long_text),))[-1]
    kept = render_review_context(_range(), (CitedRequirement("FR-009", Resolution.DECLARED, already_capped),))[-1]

    assert over == f"  {already_capped}"
    assert kept == f"  {already_capped}"


_MANY_SPECS = tuple(f"src/package_{index:03d}/module_with_a_long_name.py" for index in range(120))


def test_many_owned_pathspecs_never_print_a_zero_more_tail() -> None:
    """NFR-001 regression (#7578): with 120 owned files the command lines alone pass 4,096 bytes; an empty list prints no tail."""
    specs = _MANY_SPECS
    many = _range(owned_pathspecs=specs, commits=(), files=(), out_of_map=(), out_of_map_only_commits=0)

    lines = render_review_context(many, ())

    assert not [line for line in lines if "… 0 more" in line], lines
    assert "IMPLEMENTATION COMMITS (0; = output of the git log command below):" in lines
    command = next(line for line in lines if line.startswith("  git log "))
    assert shlex.split(command)[shlex.split(command).index("--") + 1 :] == list(specs)


def test_a_hidden_list_names_how_many_it_hides_never_zero() -> None:
    """Ruling Q11: long command lines take no budget, so only a list that does not fit is hidden, by a non-zero count."""
    lines = render_review_context(replace(_many(500, 500), owned_pathspecs=_MANY_SPECS), ())

    tails = [line for line in lines if line.startswith("  … ")]
    assert len(tails) == 2 and all(" 0 more" not in line for line in tails), tails


def test_many_owned_files_still_list_a_single_commit() -> None:
    """Ruling Q11: the command lines are exempt from the 4,096-byte budget, so a 1-commit list is shown, never hidden."""
    one = _range(owned_pathspecs=_MANY_SPECS, commits=(RangeCommit(C1, "feat(WP02): first"),))

    lines = render_review_context(one, ())

    assert "  111111111111 feat(WP02): first" in lines
    assert [line for line in lines if line.startswith("  +")] == ["  +3 -1  src/m2/extra.py", "  +2 -0  src/m2/real.py"]
    assert not [line for line in lines if line.startswith("  … ")], lines
    assert next(line for line in lines if "OUTSIDE OWNED FILES" in line).endswith("): docs/notes.md")
    command = next(line for line in lines if line.startswith("  git log "))
    assert shlex.split(command)[shlex.split(command).index("--") + 1 :] == list(_MANY_SPECS)


def test_review_diff_command_is_the_blocks_git_diff_line() -> None:
    """Q13 (#7590): one command string, printed by the block and carried by the review prompt's topology payload."""
    review_range = _range()
    block = render_review_context(review_range, ())

    assert review_diff_command(review_range) == f"git diff {BASE}..{TIP} -- 'src/m2/**'"
    assert f"  {review_diff_command(review_range)}" in block


def test_review_diff_command_of_an_unavailable_range_names_the_gap_and_points_at_the_notice() -> None:
    unavailable = WpReviewRange.unavailable("WP02", "no_submission", ("src/m2/**",))

    command = review_diff_command(unavailable)

    assert command == "unavailable: the work package has no for_review submission (no_submission); see REVIEW RANGE"
    assert render_review_context(unavailable, ())[0].endswith(describe_gap("no_submission"))
    assert ".." not in command
