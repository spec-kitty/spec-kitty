"""Tests for mission and lane branch naming."""

import pytest

from specify_cli.lanes.branch_naming import (
    code_lane_branch_name,
    is_lane_branch,
    is_mission_branch,
    mission_branch_name,
    parse_mission_slug_from_branch,
    parse_lane_id_from_branch,
)

pytestmark = pytest.mark.fast


class TestMissionBranchName:
    def test_basic(self):
        assert mission_branch_name("057-feat") == "kitty/mission-057-feat"

    def test_with_hyphens(self):
        assert mission_branch_name("010-my-long-feature") == "kitty/mission-010-my-long-feature"


class TestLaneBranchName:
    def test_basic(self):
        assert code_lane_branch_name("057-feat", "lane-a") == "kitty/mission-057-feat-lane-a"

    def test_lane_b(self):
        assert code_lane_branch_name("057-feat", "lane-b") == "kitty/mission-057-feat-lane-b"


class TestIsMissionBranch:
    def test_mission_branch(self):
        assert is_mission_branch("kitty/mission-057-feat") is True

    def test_lane_branch_is_not_mission(self):
        assert is_mission_branch("kitty/mission-057-feat-lane-a") is False

    def test_regular_branch(self):
        assert is_mission_branch("main") is False
        assert is_mission_branch("057-feat") is False

    def test_partial_prefix(self):
        assert is_mission_branch("kitty/other-057") is False


class TestIsLaneBranch:
    def test_lane_branch(self):
        assert is_lane_branch("kitty/mission-057-feat-lane-a") is True
        assert is_lane_branch("kitty/mission-057-feat-lane-b") is True

    def test_mission_branch_is_not_lane(self):
        assert is_lane_branch("kitty/mission-057-feat") is False

    def test_regular_branch(self):
        assert is_lane_branch("main") is False


class TestParseFeatureSlug:
    def test_from_mission_branch(self):
        result = parse_mission_slug_from_branch("kitty/mission-057-feat")
        assert result is not None
        assert result.slug == "057-feat"
        assert result.mid8_token is None
        assert result.lane_id is None

    def test_from_lane_branch(self):
        result = parse_mission_slug_from_branch("kitty/mission-057-feat-lane-a")
        assert result is not None
        assert result.slug == "057-feat"
        assert result.lane_id == "lane-a"

    def test_from_regular_branch(self):
        assert parse_mission_slug_from_branch("main") is None

    def test_from_nonmission_feature_branch(self):
        assert parse_mission_slug_from_branch("057-feat") is None


class TestParseLaneId:
    def test_from_lane_branch(self):
        assert parse_lane_id_from_branch("kitty/mission-057-feat-lane-a") == "lane-a"

    def test_from_mission_branch(self):
        assert parse_lane_id_from_branch("kitty/mission-057-feat") is None

    def test_from_regular_branch(self):
        assert parse_lane_id_from_branch("main") is None
