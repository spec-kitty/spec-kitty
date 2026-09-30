"""Tests for the additive lane-worktree-dir parsers (FR-008).

``parse_lane_worktree_dir`` and ``lane_id_for_worktree_dir`` are slug-free and
slug-confirmed discovery parsers respectively, built on the single
``_LANE_ID_RE`` grammar fragment. Every input here is a literal directory-name
or branch-name string — never composed via ``worktree_dir_name`` or any other
code under test (Test Strategy: "never compose an input with... any other
code under test").
"""

from __future__ import annotations

import pytest

from specify_cli.lanes.branch_naming import (
    BranchParseResult,
    is_lane_branch,
    lane_id_for_worktree_dir,
    parse_lane_id_from_branch,
    parse_lane_worktree_dir,
    parse_mission_slug_from_branch,
)


class TestParseLaneWorktreeDir:
    """parse_lane_worktree_dir over the three grammars plus negatives."""

    @pytest.mark.parametrize(
        ("dir_name", "expected"),
        [
            # legacy NNN-slug
            ("057-foo-lane-a", ("057-foo", "lane-a")),
            # plain legacy slug
            ("foo-lane-a", ("foo", "lane-a")),
            # mid8-suffixed slug
            ("foo-01KV6510-lane-a", ("foo-01KV6510", "lane-a")),
            # NNN-slug plus mid8 (the core/vcs/detection.py grammar need)
            ("057-foo-01KV6510-lane-a", ("057-foo-01KV6510", "lane-a")),
            # multi-letter lane id
            ("foo-lane-aa", ("foo", "lane-aa")),
            # slug itself contains "-lane-"
            ("lane-mgmt-lane-a", ("lane-mgmt", "lane-a")),
        ],
    )
    def test_positive_grammars(self, dir_name: str, expected: tuple[str, str]) -> None:
        assert parse_lane_worktree_dir(dir_name) == expected

    @pytest.mark.parametrize(
        "dir_name",
        [
            "foo",  # no lane suffix at all
            "foo-lane-",  # empty lane-id tail
            "foo-lane-A",  # uppercase not accepted by the lane-id grammar
            "foo-lane-1",  # digit not accepted by the lane-id grammar
        ],
    )
    def test_negative_literals_return_none(self, dir_name: str) -> None:
        assert parse_lane_worktree_dir(dir_name) is None


class TestLaneIdForWorktreeDir:
    """lane_id_for_worktree_dir confirms by recomposition, not prefix."""

    @pytest.mark.parametrize(
        ("dir_name", "mission_slug", "expected"),
        [
            ("057-foo-lane-a", "057-foo", "lane-a"),
            ("foo-01KV6510-lane-b", "foo-01KV6510", "lane-b"),
        ],
    )
    def test_positive_recomposition(self, dir_name: str, mission_slug: str, expected: str) -> None:
        assert lane_id_for_worktree_dir(dir_name, mission_slug) == expected

    def test_rejects_same_prefix_impostor(self) -> None:
        """named behaviour change: recognition by recomposition, not prefix.

        ``057-foobar-lane-a`` must NOT be reported as ``057-foo``'s lane
        worktree, even though its directory name starts with the same prefix.
        """
        assert lane_id_for_worktree_dir("057-foobar-lane-a", "057-foo") is None

    def test_rejects_slug_mismatch_beyond_prefix(self) -> None:
        assert lane_id_for_worktree_dir("foobar-lane-a", "foo") is None


class TestIsLaneBranchPlainLegacy:
    """is_lane_branch accepts the plain-legacy grammar (FR-008 item 3)."""

    def test_plain_legacy_lane_branch_is_recognized(self) -> None:
        assert is_lane_branch("kitty/mission-foo-lane-a") is True

    def test_multi_letter_lane_id_still_recognized(self) -> None:
        assert is_lane_branch("kitty/mission-057-foo-lane-aa") is True


class TestBranchParsersWidenedGrammar:
    """The rebuilt regexes widen the branch
    parsers (``parse_mission_slug_from_branch``, ``parse_lane_id_from_branch``)
    too, not just the directory parsers -- explicit group-index-drift coverage
    for a multi-letter lane id and a slug containing ``lane``.
    """

    def test_plain_legacy_multi_letter_lane_id(self) -> None:
        """named behaviour change: on HEAD, `kitty/mission-foo-lane-ab` parsed
        as slug `foo-lane-ab` (no lane recognized, single-letter-only grammar).
        Widened, it parses as slug `foo`, lane `lane-ab`."""
        assert parse_mission_slug_from_branch("kitty/mission-foo-lane-ab") == BranchParseResult(slug="foo", mid8_token=None, lane_id="lane-ab")
        assert parse_lane_id_from_branch("kitty/mission-foo-lane-ab") == "lane-ab"

    def test_legacy_nnn_multi_letter_lane_id(self) -> None:
        assert parse_mission_slug_from_branch("kitty/mission-057-foo-lane-ab") == BranchParseResult(slug="057-foo", mid8_token=None, lane_id="lane-ab")
        assert parse_lane_id_from_branch("kitty/mission-057-foo-lane-ab") == "lane-ab"

    def test_new_mid8_multi_letter_lane_id(self) -> None:
        assert parse_mission_slug_from_branch("kitty/mission-foo-01KV6510-lane-ab") == BranchParseResult(slug="foo", mid8_token="01KV6510", lane_id="lane-ab")
        assert parse_lane_id_from_branch("kitty/mission-foo-01KV6510-lane-ab") == "lane-ab"

    def test_slug_containing_lane_parses_correctly(self) -> None:
        """`kitty/mission-lane-mgmt-lane-a` -> slug `lane-mgmt`, lane `lane-a`:
        the slug's own embedded `lane-mgmt` token is not mistaken for the
        lane-id suffix, because the match anchors on the rightmost
        `-lane-[a-z]+` occurrence."""
        assert parse_mission_slug_from_branch("kitty/mission-lane-mgmt-lane-a") == BranchParseResult(slug="lane-mgmt", mid8_token=None, lane_id="lane-a")
        assert parse_lane_id_from_branch("kitty/mission-lane-mgmt-lane-a") == "lane-a"
