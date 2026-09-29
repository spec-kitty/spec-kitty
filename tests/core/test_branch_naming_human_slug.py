"""Tests for human-slug + mid8 branch naming (WP02 / T012).

Covers:
- strip_numeric_prefix correctness (table-driven)
- mid8 extraction
- New branch constructor round-trip
- Collision: two missions with same human slug but different ULIDs -> distinct branches
- Legacy parse: NNN-slug forms still parse correctly
- parse_mission_slug_from_branch for both legacy and new forms
- is_legacy_branch helper
"""

from __future__ import annotations

import pytest

from specify_cli.lanes.branch_naming import (
    InvalidMissionIdentity,
    _mid8,
    code_lane_branch_name,
    is_legacy_branch,
    lane_branch_name,
    mission_branch_name,
    parse_mission_slug_from_branch,
    strip_numeric_prefix,
)


# ---------------------------------------------------------------------------
# strip_numeric_prefix — table-driven
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("083-foo", "foo"),
        ("001-bar-baz", "bar-baz"),
        ("999-x", "x"),
        ("foo", "foo"),  # no prefix — unchanged
        ("foo-bar", "foo-bar"),  # no prefix — unchanged
        ("08-foo", "08-foo"),  # only 2 digits — not stripped
        ("1234-foo", "1234-foo"),  # 4 digits — not stripped
        ("", ""),  # empty string — unchanged
        ("083-", "083-"),  # prefix but empty human slug after — unchanged (edge: strip only when non-empty remainder)
    ],
)
def test_strip_numeric_prefix(slug: str, expected: str) -> None:
    assert strip_numeric_prefix(slug) == expected


# ---------------------------------------------------------------------------
# mid8
# ---------------------------------------------------------------------------


def test_mid8_returns_first_8_chars() -> None:
    ulid = "01KNXQS9ATWWFXS3K5ZJ9E5008"
    assert _mid8(ulid) == "01KNXQS9"


def test_mid8_on_minimum_length() -> None:
    # ULID is 26 chars; mid8 needs at least 8
    assert _mid8("01234567ABCDEFGHIJKLMNOPQ") == "01234567"


def test_mid8_raises_on_too_short() -> None:
    """The typed ``InvalidMissionIdentity`` (a ``BranchIdentityUnresolved``
    subclass), raised at the source — never a bare ``ValueError`` (#5108)."""
    with pytest.raises(InvalidMissionIdentity, match="mission_id 'short' is invalid"):
        _mid8("short")


# ---------------------------------------------------------------------------
# New branch name constructor
# ---------------------------------------------------------------------------


def test_mission_branch_name_new_format() -> None:
    slug = "083-mission-id-canonical-identity-migration"
    ulid = "01KNXQS9ATWWFXS3K5ZJ9E5008"
    result = mission_branch_name(slug, mission_id=ulid)
    assert result == "kitty/mission-mission-id-canonical-identity-migration-01KNXQS9"


def test_mission_branch_name_does_not_double_existing_mid8_suffix() -> None:
    slug = "agent-profile-projection-plugin-production-01KV3NGS"
    ulid = "01KV3NGSDCJ272573TF6T6NWDW"
    result = mission_branch_name(slug, mission_id=ulid)
    assert result == "kitty/mission-agent-profile-projection-plugin-production-01KV3NGS"


def test_lane_branch_name_new_format() -> None:
    # Re-pinned to the created name; the identity-injected form
    # ("...-01KNXQS9-lane-a") pinned the #5108 defect. Lane naming takes no
    # mission_id: the slug carries no embedded mid8, so it composes
    # verbatim.
    slug = "083-mission-id-canonical-identity-migration"
    result = code_lane_branch_name(slug, "lane-a")
    assert result == "kitty/mission-083-mission-id-canonical-identity-migration-lane-a"


def test_lane_branch_name_does_not_double_existing_mid8_suffix() -> None:
    # Unchanged: the slug already embeds its own mid8, so the created name is
    # byte-identical whether or not an identity is supplied.
    slug = "agent-profile-projection-plugin-production-01KV3NGS"
    result = code_lane_branch_name(slug, "lane-a")
    assert result == "kitty/mission-agent-profile-projection-plugin-production-01KV3NGS-lane-a"


def test_lane_branch_name_without_numeric_prefix() -> None:
    # Re-pinned to the created name. Slug with no numeric prefix
    # and no embedded mid8 composes verbatim (lane naming takes no
    # mission_id).
    slug = "my-feature"
    result = code_lane_branch_name(slug, "lane-b")
    assert result == "kitty/mission-my-feature-lane-b"


def test_lane_branch_name_planning_lane_ignores_identity() -> None:
    # lane-planning returns the planning base branch, unaffected by identity.
    result = lane_branch_name("083-foo", "lane-planning", target_branch="main")
    assert result == "main"


def test_lane_branch_name_planning_with_explicit_base() -> None:
    result = lane_branch_name(
        "083-foo",
        "lane-planning",
        target_branch="release/3.x",
    )
    assert result == "release/3.x"


# ---------------------------------------------------------------------------
# Lane naming takes no identity (FR-002), closing the collision
# class by construction — the SAME (slug, lane_id) always composes the SAME
# branch; there is no longer a parameter that could make it diverge.
# ---------------------------------------------------------------------------


def test_lane_branch_name_is_identity_independent_by_construction() -> None:
    """No identity parameter exists to inject, so the branch is deterministic.

    Re-expresses the former "different ULIDs -> distinct branches" collision
    pin: that property no longer applies because lane naming no
    longer takes an identity at all.
    """
    slug = "083-foo-bar"
    assert code_lane_branch_name(slug, "lane-a") == code_lane_branch_name(slug, "lane-a") == "kitty/mission-083-foo-bar-lane-a"


# ---------------------------------------------------------------------------
# parse_mission_slug_from_branch — legacy forms
# ---------------------------------------------------------------------------


# Real branch names from the 080-* triple on main, paired with expected lane_id.
# Note: "080-wpstate-lane-consumer-strangler-fig-phase-2" embeds "lane-consumer" in the
# slug itself — the parser correctly classifies it as a non-lane mission branch (lane_id=None)
# because the suffix "phase-2" does not match the lane pattern "lane-[a-z]".
LEGACY_BRANCHES: list[tuple[str, str | None]] = [
    ("kitty/mission-080-browser-mediated-oauth-cli-auth", None),
    ("kitty/mission-080-ci-hardening-and-lint-cleanup", None),
    ("kitty/mission-feature-without-number", None),
    # "lane-consumer" is part of the slug, NOT a lane suffix — lane_id must be None
    ("kitty/mission-080-wpstate-lane-consumer-strangler-fig-phase-2", None),
    # These end with a real lane suffix
    ("kitty/mission-080-browser-mediated-oauth-cli-auth-lane-a", "lane-a"),
    ("kitty/mission-082-stealth-gated-saas-sync-hardening-lane-b", "lane-b"),
    ("kitty/mission-feature-without-number-lane-a", "lane-a"),
]


@pytest.mark.parametrize("branch,expected_lane_id", LEGACY_BRANCHES)
def test_parse_legacy_branch(branch: str, expected_lane_id: str | None) -> None:
    result = parse_mission_slug_from_branch(branch)
    assert result is not None, f"Failed to parse legacy branch: {branch}"
    slug, mid8_val, lane_id = result
    assert slug  # non-empty
    assert mid8_val is None  # legacy: no mid8
    assert lane_id == expected_lane_id, f"Expected lane_id={expected_lane_id!r} for {branch!r}, got {lane_id!r}"


# ---------------------------------------------------------------------------
# parse_mission_slug_from_branch — new forms
# ---------------------------------------------------------------------------


def test_parse_new_branch_without_lane() -> None:
    branch = "kitty/mission-mission-id-canonical-identity-migration-01KNXQS9"
    result = parse_mission_slug_from_branch(branch)
    assert result is not None
    slug, mid8_val, lane_id = result
    assert slug == "mission-id-canonical-identity-migration"
    assert mid8_val == "01KNXQS9"
    assert lane_id is None


def test_parse_new_branch_with_lane() -> None:
    branch = "kitty/mission-mission-id-canonical-identity-migration-01KNXQS9-lane-a"
    result = parse_mission_slug_from_branch(branch)
    assert result is not None
    slug, mid8_val, lane_id = result
    assert slug == "mission-id-canonical-identity-migration"
    assert mid8_val == "01KNXQS9"
    assert lane_id == "lane-a"


def test_parse_new_branch_slug_with_hyphens() -> None:
    # Multi-part slug
    branch = "kitty/mission-foo-bar-baz-01KNXQS9-lane-b"
    result = parse_mission_slug_from_branch(branch)
    assert result is not None
    slug, mid8_val, lane_id = result
    assert slug == "foo-bar-baz"
    assert mid8_val == "01KNXQS9"
    assert lane_id == "lane-b"


def test_parse_unknown_branch_returns_none() -> None:
    result = parse_mission_slug_from_branch("feature/some-other-branch")
    assert result is None


def test_parse_non_kitty_prefix_returns_none() -> None:
    result = parse_mission_slug_from_branch("main")
    assert result is None


# ---------------------------------------------------------------------------
# is_legacy_branch
# ---------------------------------------------------------------------------


def test_is_legacy_branch_with_numeric_prefix() -> None:
    assert is_legacy_branch("kitty/mission-080-browser-mediated-oauth-cli-auth") is True
    assert is_legacy_branch("kitty/mission-080-foo-lane-a") is True
    assert is_legacy_branch("kitty/mission-feature-without-number") is True
    assert is_legacy_branch("kitty/mission-feature-without-number-lane-a") is True


def test_is_legacy_branch_new_form() -> None:
    assert is_legacy_branch("kitty/mission-foo-bar-01KNXQS9") is False
    assert is_legacy_branch("kitty/mission-foo-bar-01KNXQS9-lane-a") is False


def test_is_legacy_branch_non_kitty() -> None:
    assert is_legacy_branch("main") is False
    assert is_legacy_branch("feature/something") is False


# ---------------------------------------------------------------------------
# Round-trip: construct then parse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "lane"),
    [
        ("083-foo-bar", "lane-a"),
        ("001-simple", "lane-b"),
        ("my-feature", "lane-c"),
    ],
)
def test_round_trip_construct_then_parse(slug: str, lane: str) -> None:
    """Lane naming takes no identity, so a bare slug round-trips with no
    ``mid8_token`` (that case is covered separately, below, for an
    already-embedded slug)."""
    branch = code_lane_branch_name(slug, lane)
    result = parse_mission_slug_from_branch(branch)
    assert result is not None
    parsed_slug, parsed_mid8, parsed_lane = result
    assert parsed_mid8 is None
    assert parsed_lane == lane
    assert parsed_slug == slug


def test_round_trip_construct_then_parse_embedded_mid8() -> None:
    """A slug that already embeds a mid8 tail round-trips it (no injection)."""
    slug = "foo-01KV3NGS"
    branch = code_lane_branch_name(slug, "lane-a")
    result = parse_mission_slug_from_branch(branch)
    assert result is not None
    assert result.slug == "foo"
    assert result.mid8_token == "01KV3NGS"
    assert result.lane_id == "lane-a"


# ---------------------------------------------------------------------------
# Pathological case: slug already ends with a *different* mid8-shaped token
# ---------------------------------------------------------------------------


def test_mission_branch_name_does_not_strip_different_mid8_suffix() -> None:
    """Slug ending with a mid8-shaped token that differs from the mission's own mid8.

    When the slug already contains a different mid8-shaped suffix (e.g. an
    earlier mission's mid8 embedded in the human slug), ``_human_slug_for_mid8_branch``
    must NOT strip it — the deduplication guard only removes the suffix when it
    matches the *current* mission_id's mid8.  The result is a branch name with
    both the embedded token and the own mid8, i.e. a double-append.  This is the
    documented behavior, not a bug.
    """
    slug = "my-feature-AAAA1111"
    ulid = "01KV3NGSDCJ272573TF6T6NWDW"  # mid8 = 01KV3NGS
    result = mission_branch_name(slug, mission_id=ulid)
    # "AAAA1111" != "01KV3NGS" so it is NOT stripped; own mid8 is appended normally.
    assert result == "kitty/mission-my-feature-AAAA1111-01KV3NGS"


def test_lane_branch_name_embedded_mid8_shaped_token_preserved() -> None:
    """Re-pinned to the created name.

    Lane naming takes no identity, so there is no "own mid8" to append or
    mismatch against; the slug's own mid8-shaped tail is preserved verbatim,
    exactly once (the double-append this test used to pin is now impossible).
    """
    slug = "my-feature-AAAA1111"
    result = code_lane_branch_name(slug, "lane-a")
    assert result == "kitty/mission-my-feature-AAAA1111-lane-a"
