"""#7726: the bulk-edit review gate refuses a range it cannot judge (``review_range_refusal``)
and names the commits it did not judge (``_note_unjudged_commits``)."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from specify_cli.bulk_edit.gate import (
    BULK_EDIT_REVIEW_RANGE_EMPTY,
    BULK_EDIT_REVIEW_RANGE_UNAVAILABLE,
    review_range_refusal,
)
from specify_cli.cli.commands.agent.workflow import _note_unjudged_commits
from specify_cli.review.wp_range import RangeSource, RangeStatus, WpReviewRange

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BASE = "a" * 40
_TIP = "b" * 40


def _refusal(
    *,
    base: str | None = _BASE,
    tip: str | None = _TIP,
    gap: str | None = None,
    commit_count: int = 1,
    listing_gap: str | None = None,
) -> str | None:
    refusal: str | None = review_range_refusal(
        wp_id="WP01",
        mission_slug="m-01M7",
        base=base,
        tip=tip,
        gap=gap,
        commit_count=commit_count,
        listing_gap=listing_gap,
    )
    return refusal


def test_a_range_with_commits_is_judgeable() -> None:
    assert _refusal() is None
    assert _refusal(listing_gap="numstat") is None  # only a failed commit listing matters to the gate


def test_no_submission_asks_for_the_hand_off_to_review() -> None:
    message = _refusal(base=None, tip=None, gap="no_submission")
    assert message is not None
    assert message.startswith(BULK_EDIT_REVIEW_RANGE_UNAVAILABLE)
    assert "gap: no_submission" in message
    assert "spec-kitty agent tasks move-task WP01 --to for_review --mission m-01M7" in message


def test_an_unreadable_status_surface_points_at_the_status_command() -> None:
    message = _refusal(base=None, tip=None, gap="status_unreadable")
    assert message is not None and BULK_EDIT_REVIEW_RANGE_UNAVAILABLE in message
    assert "spec-kitty agent tasks status --mission m-01M7" in message


@pytest.mark.parametrize("gap", ["not_recorded", "unresolvable_sha", "lane_branch_missing", None])
def test_an_unresolvable_end_asks_for_a_fetch_never_a_local_branch(gap: str | None) -> None:
    message = _refusal(base=None, tip=None, gap=gap)
    assert message is not None and BULK_EDIT_REVIEW_RANGE_UNAVAILABLE in message
    assert f"gap: {gap or 'unknown'}" in message
    assert "Fetch the commits" in message
    assert "kitty/mission" not in message and "git branch" not in message


def test_a_failed_commit_listing_is_unavailable_not_empty() -> None:
    message = _refusal(commit_count=0, listing_gap="commits, numstat")
    assert message is not None
    assert message.startswith(BULK_EDIT_REVIEW_RANGE_UNAVAILABLE)
    assert "could not be listed" in message


@pytest.mark.parametrize(("base", "commit_count"), [(_TIP, 1), (_BASE, 0)])
def test_an_empty_range_is_refused(base: str, commit_count: int) -> None:
    message = _refusal(base=base, commit_count=commit_count)
    assert message is not None
    assert message.startswith(BULK_EDIT_REVIEW_RANGE_EMPTY)
    assert "--to for_review" in message


def _range(*, moved_past: int = 0, tip_off_branch: bool = False) -> WpReviewRange:
    return WpReviewRange(
        wp_id="WP01",
        base=_BASE,
        tip=_TIP,
        base_source=RangeSource.RECORDED_WINDOW,
        tip_source=RangeSource.RECORDED_SUBMISSION,
        gap=None,
        status=RangeStatus.RECORDED,
        moved_past=moved_past,
        tip_off_branch=tip_off_branch,
    )


def _notes(review_range: WpReviewRange) -> str:
    buffer = StringIO()
    _note_unjudged_commits(review_range, "WP01", "m-01M7", Console(file=buffer, width=400, no_color=True))
    return " ".join(buffer.getvalue().split())


def test_no_note_when_the_branch_is_at_the_submitted_tip() -> None:
    assert _notes(_range()) == ""


def test_commits_past_the_submission_are_named_as_unjudged() -> None:
    notes = _notes(_range(moved_past=2))
    assert "moved 2 commit(s) past WP01's submitted tip" in notes
    assert "move-task WP01 --to for_review --mission m-01M7" in notes


def test_a_rewritten_branch_is_named_as_unjudged() -> None:
    notes = _notes(_range(moved_past=3, tip_off_branch=True))
    assert "no longer on its branch" in notes
    assert "moved 3" not in notes
